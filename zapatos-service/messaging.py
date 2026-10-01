import json
import os
import threading
import time
import pika
from database import SessionLocal
from models import Zapato

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")

EXCHANGE_NAME = "tienda.saga.orquestada"
QUEUE_COMANDOS_ZAPATOS = "cola_comandos_zapatos"
QUEUE_RESPUESTAS_ORQUESTADOR = "cola_orquestador_respuestas"


def get_connection_params():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=300
    )


def responder_al_orquestador(routing_key: str, payload: dict):
    """Envía la respuesta directa del microservicio de zapatos al Orquestador central."""
    try:
        connection = pika.BlockingConnection(get_connection_params())
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(payload).encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent
            )
        )
        print(f"[Zapatos -> Orquestador] Respuesta enviada: '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[Zapatos Error] No se pudo responder al orquestador: {e}")


def procesar_comando(routing_key: str, data: dict):
    """
    Procesa comandos dirigidos exclusivamente a zapatos-service:
    - comando.zapatos.reservar: Reserva inventario restando cantidad_disponible.
    - comando.zapatos.liberar: Compensación semántica (rollback), restaura el stock.
    """
    id_saga = data.get("id_saga")
    print(f"\n[Zapatos-Service] >>> Comando recibido del Orquestador: '{routing_key}' para SAGA: {id_saga}")

    # 1. COMANDO DIRECTO: RESERVAR INVENTARIO
    if routing_key == "comando.zapatos.reservar":
        id_zapato = data.get("id_zapato")
        cantidad = data.get("cantidad", 1)

        db = SessionLocal()
        try:
            zapato = db.query(Zapato).filter(Zapato.id_zapato == id_zapato).first()

            if not zapato:
                motivo = f"Zapato ID {id_zapato} no existe"
                print(f"[Zapatos-Service] Error: {motivo}")
                responder_al_orquestador("respuesta.zapatos.fallo", {
                    "id_saga": id_saga,
                    "status": "ERROR",
                    "motivo": motivo
                })
                return

            stock_actual = zapato.cantidad_disponible or 0
            print(f"[Zapatos-Service] Validando stock en PostgreSQL: Zapato ID {id_zapato} ('{zapato.marca}') | Stock actual: {stock_actual} | Solicitado: {cantidad}")

            if stock_actual < cantidad:
                motivo = f"Stock insuficiente (Disponible: {stock_actual}, Solicitado: {cantidad})"
                print(f"[Zapatos-Service] [RECHAZADO] {motivo}")
                responder_al_orquestador("respuesta.zapatos.fallo", {
                    "id_saga": id_saga,
                    "status": "ERROR",
                    "motivo": motivo
                })
                return

            # Transacción local: decrementa inventario y hace commit
            zapato.cantidad_disponible = stock_actual - cantidad
            db.commit()

            precio_unitario = float(zapato.precio)
            monto_total = precio_unitario * cantidad
            print(f"[Zapatos-Service] [COMMIT LOCAL] Stock reservado: {stock_actual} -> {zapato.cantidad_disponible} unidades. Total: ${monto_total:,.2f}")

            responder_al_orquestador("respuesta.zapatos.reservado", {
                "id_saga": id_saga,
                "status": "OK",
                "id_zapato": id_zapato,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "monto_total": monto_total,
                "stock_restante": zapato.cantidad_disponible
            })

        except Exception as e:
            db.rollback()
            print(f"[Zapatos-Service Error]: {e}")
            responder_al_orquestador("respuesta.zapatos.fallo", {
                "id_saga": id_saga,
                "status": "ERROR",
                "motivo": f"Error interno en DB Zapatos: {str(e)}"
            })
        finally:
            db.close()

    # 2. COMANDO DE COMPENSACIÓN (ROLLBACK SEMÁNTICO): LIBERAR STOCK
    elif routing_key in ["comando.zapatos.liberar", "comando.zapatos.cancelar"]:
        id_zapato = data.get("id_zapato")
        cantidad = data.get("cantidad", 1)
        motivo = data.get("motivo", "Compensación ordenada por el Orquestador")

        print(f"[Zapatos-Service] [COMPENSACIÓN SEMÁNTICA INICIADA] Orden del Orquestador para revertir reserva. Motivo: {motivo}")
        db = SessionLocal()
        try:
            zapato = db.query(Zapato).filter(Zapato.id_zapato == id_zapato).first()
            if zapato:
                stock_previo = zapato.cantidad_disponible or 0
                zapato.cantidad_disponible = stock_previo + cantidad
                db.commit()
                print(f"[Zapatos-Service] [COMMIT COMPENSACIÓN] Stock restaurado en PostgreSQL: {stock_previo} -> {zapato.cantidad_disponible} unidades.")
                responder_al_orquestador("respuesta.zapatos.liberado", {
                    "id_saga": id_saga,
                    "status": "COMPENSADO",
                    "id_zapato": id_zapato,
                    "stock_actual": zapato.cantidad_disponible
                })
            else:
                print(f"[Zapatos-Service Error]: Zapato {id_zapato} no encontrado para compensar")
        except Exception as e:
            db.rollback()
            print(f"[Zapatos-Service Error Compensación]: {e}")
        finally:
            db.close()


def iniciar_consumidor():
    """Escucha la cola de comandos exclusiva de Zapatos."""
    def _worker():
        while True:
            try:
                print("[Zapatos] Conectando a RabbitMQ para escuchar comandos del Orquestador...")
                params = get_connection_params()
                connection = None
                for _ in range(30):
                    try:
                        connection = pika.BlockingConnection(params)
                        break
                    except Exception:
                        time.sleep(2)

                if not connection:
                    time.sleep(5)
                    continue

                channel = connection.channel()
                channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
                channel.queue_declare(queue=QUEUE_COMANDOS_ZAPATOS, durable=True)

                # Suscribirse a todos los comandos dirigidos a zapatos
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_COMANDOS_ZAPATOS, routing_key="comando.zapatos.*")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_comando(method.routing_key, data)
                    except Exception as e:
                        print(f"[Zapatos Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_COMANDOS_ZAPATOS, on_message_callback=callback)
                print(f"[Zapatos] Consumidor de comandos listo en cola '{QUEUE_COMANDOS_ZAPATOS}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Zapatos] Conexión AMQP perdida: {e}. Reconectando en 5s...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
