import json
import os
import threading
import time
import pika
from database import SessionLocal
from models import Cliente

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")

EXCHANGE_NAME = "tienda.saga.orquestada"
QUEUE_COMANDOS_CLIENTES = "cola_comandos_clientes"
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
    """Envía la respuesta directa del microservicio hacia el Orquestador central."""
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
        print(f"[Clientes -> Orquestador] Respuesta enviada: '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[Clientes Error] No se pudo responder al orquestador: {e}")


def procesar_comando(routing_key: str, data: dict):
    """
    En SAGA Orquestada, el servicio NO toma decisiones globales.
    Solo ejecuta el comando específico instruido por el Orquestador y le responde el resultado.
    """
    id_saga = data.get("id_saga")
    print(f"\n[Clientes-Service] >>> Comando recibido del Orquestador: '{routing_key}' para SAGA: {id_saga}")

    if routing_key == "comando.clientes.cobrar":
        id_cliente = data.get("id_cliente")
        monto = float(data.get("monto", 0.0))

        db = SessionLocal()
        try:
            cliente = db.query(Cliente).filter(Cliente.id == id_cliente).first()

            if not cliente:
                motivo = f"Cliente con ID {id_cliente} no existe en la base de datos"
                print(f"[Clientes-Service] Fallo de comando: {motivo}")
                responder_al_orquestador("respuesta.clientes.fallo", {
                    "id_saga": id_saga,
                    "id_cliente": id_cliente,
                    "status": "ERROR",
                    "motivo": motivo
                })
                return

            saldo_actual = float(cliente.saldo)
            print(f"[Clientes-Service] Verificando saldo en PostgreSQL: Cliente ID {id_cliente} ('{cliente.nombre}') | Saldo actual: ${saldo_actual:,.2f} | Monto a cobrar: ${monto:,.2f}")

            if saldo_actual < monto:
                motivo = f"Saldo insuficiente (${saldo_actual:,.2f} disponibles < ${monto:,.2f} requeridos)"
                print(f"[Clientes-Service] [RECHAZADO] {motivo}. Fondos intactos.")
                responder_al_orquestador("respuesta.clientes.fallo", {
                    "id_saga": id_saga,
                    "id_cliente": id_cliente,
                    "status": "ERROR",
                    "motivo": motivo,
                    "saldo_actual": saldo_actual,
                    "monto_requerido": monto
                })
                return

            # Transacción local de débito
            cliente.saldo = saldo_actual - monto
            db.commit()
            print(f"[Clientes-Service] [COMMIT LOCAL] Saldo debitado exitosamente. Nuevo saldo: ${float(cliente.saldo):,.2f}")

            responder_al_orquestador("respuesta.clientes.cobrado", {
                "id_saga": id_saga,
                "id_cliente": id_cliente,
                "status": "OK",
                "monto_cobrado": monto,
                "nuevo_saldo": float(cliente.saldo)
            })

        except Exception as e:
            db.rollback()
            print(f"[Clientes-Service Error]: {e}")
            responder_al_orquestador("respuesta.clientes.fallo", {
                "id_saga": id_saga,
                "id_cliente": id_cliente,
                "status": "ERROR",
                "motivo": f"Error interno en DB Clientes: {str(e)}"
            })
        finally:
            db.close()


def iniciar_consumidor():
    """Escucha la cola exclusiva de comandos asignados al microservicio de Clientes."""
    def _worker():
        while True:
            try:
                print("[Clientes] Conectando a RabbitMQ para escuchar comandos del Orquestador...")
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
                channel.queue_declare(queue=QUEUE_COMANDOS_CLIENTES, durable=True)

                # Suscribirse a comandos dirigidos a clientes
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_COMANDOS_CLIENTES, routing_key="comando.clientes.*")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_comando(method.routing_key, data)
                    except Exception as e:
                        print(f"[Clientes Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_COMANDOS_CLIENTES, on_message_callback=callback)
                print(f"[Clientes] Consumidor de comandos listo en cola '{QUEUE_COMANDOS_CLIENTES}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Clientes] Conexión AMQP perdida: {e}. Reconectando en 5s...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
