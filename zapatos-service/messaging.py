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
EXCHANGE_NAME = "tienda.saga"
QUEUE_NAME = "cola_zapatos"


def get_connection_params():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=300
    )


def publicar_evento(routing_key: str, payload: dict):
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
        print(f"[RabbitMQ - Zapatos] Evento publicado: '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[RabbitMQ - Zapatos] Error al publicar '{routing_key}': {e}")


def procesar_evento(routing_key: str, data: dict):
    print(f"[RabbitMQ - Zapatos] Recibido evento: '{routing_key}' con data: {data}")

    # 1. PASO ADELANTE: Reserva de Stock
    if routing_key == "venta.creada":
        id_venta = data.get("id_venta")
        id_cliente = data.get("id_cliente")
        id_zapato = data.get("id_zapato")
        cantidad = data.get("cantidad", 1)

        db = SessionLocal()
        try:
            zapato = db.query(Zapato).filter(Zapato.id_zapato == id_zapato).first()

            if not zapato:
                motivo = f"Zapato con ID {id_zapato} no existe"
                print(f"[SAGA Zapatos] Rechazado: {motivo}")
                publicar_evento("stock.rechazado", {
                    "id_venta": id_venta,
                    "motivo": motivo
                })
                return

            if (zapato.cantidad_disponible or 0) < cantidad:
                motivo = f"Stock insuficiente (Disponible: {zapato.cantidad_disponible}, Requerido: {cantidad})"
                print(f"[SAGA Zapatos] Rechazado: {motivo}")
                publicar_evento("stock.rechazado", {
                    "id_venta": id_venta,
                    "motivo": motivo
                })
                return

            # Transacción local: descontar stock
            zapato.cantidad_disponible -= cantidad
            db.commit()

            monto_total = float(zapato.precio) * cantidad
            print(f"[SAGA Zapatos] Stock reservado para venta {id_venta}. Quedan {zapato.cantidad_disponible} unidades.")

            publicar_evento("stock.reservado", {
                "id_venta": id_venta,
                "id_cliente": id_cliente,
                "id_zapato": id_zapato,
                "cantidad": cantidad,
                "monto_total": monto_total
            })
        except Exception as e:
            db.rollback()
            print(f"[SAGA Zapatos] Error interno al reservar stock: {e}")
            publicar_evento("stock.rechazado", {
                "id_venta": id_venta,
                "motivo": f"Error interno en servicio de zapatos: {str(e)}"
            })
        finally:
            db.close()

    # 2. PASO DE COMPENSACIÓN (ROLLBACK SEMÁNTICO): Pago falló, devolver stock
    elif routing_key == "pago.fallido":
        id_venta = data.get("id_venta")
        id_zapato = data.get("id_zapato")
        cantidad = data.get("cantidad", 1)
        motivo = data.get("motivo", "Desconocido")

        print(f"[SAGA Zapatos - COMPENSACIÓN] Iniciando compensación para venta {id_venta} debido a: {motivo}")
        db = SessionLocal()
        try:
            zapato = db.query(Zapato).filter(Zapato.id_zapato == id_zapato).first()
            if zapato:
                # Transacción compensatoria
                zapato.cantidad_disponible = (zapato.cantidad_disponible or 0) + cantidad
                db.commit()
                print(f"[SAGA Zapatos - COMPENSACIÓN] Exitoso: Se devolvieron {cantidad} unidades al zapato {id_zapato}. Stock actual: {zapato.cantidad_disponible}")
                publicar_evento("stock.compensado", {
                    "id_venta": id_venta,
                    "id_zapato": id_zapato,
                    "cantidad_devuelta": cantidad
                })
        except Exception as e:
            db.rollback()
            print(f"[SAGA Zapatos - COMPENSACIÓN ERROR]: {e}")
        finally:
            db.close()


def iniciar_consumidor():
    def _worker():
        while True:
            try:
                print("[Zapatos] Intentando conectar a RabbitMQ...")
                params = get_connection_params()
                connection = None
                for _ in range(30):
                    try:
                        connection = pika.BlockingConnection(params)
                        break
                    except Exception:
                        time.sleep(2)

                if not connection:
                    print("[Zapatos] No se pudo conectar a RabbitMQ tras varios intentos. Reintentando...")
                    time.sleep(5)
                    continue

                channel = connection.channel()
                channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
                channel.queue_declare(queue=QUEUE_NAME, durable=True)

                # Escuchar venta creada (para reservar stock)
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="venta.creada")
                # Escuchar pago fallido (para compensar / devolver stock)
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="pago.fallido")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_evento(method.routing_key, data)
                    except Exception as e:
                        print(f"[Zapatos Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
                print(f"[Zapatos] Consumidor escuchando en cola '{QUEUE_NAME}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Zapatos] Conexión caída de RabbitMQ: {e}. Reconectando en 5 segundos...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
