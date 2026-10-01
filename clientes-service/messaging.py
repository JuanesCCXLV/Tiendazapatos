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
EXCHANGE_NAME = "tienda.saga"
QUEUE_NAME = "cola_clientes"


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
        print(f"[RabbitMQ - Clientes] Evento publicado: '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[RabbitMQ - Clientes] Error al publicar '{routing_key}': {e}")


def procesar_evento(routing_key: str, data: dict):
    print(f"[RabbitMQ - Clientes] Recibido evento: '{routing_key}' con data: {data}")
    if routing_key == "stock.reservado":
        id_venta = data.get("id_venta")
        id_cliente = data.get("id_cliente")
        id_zapato = data.get("id_zapato")
        cantidad = data.get("cantidad", 1)
        monto_total = float(data.get("monto_total", 0.0))

        db = SessionLocal()
        try:
            cliente = db.query(Cliente).filter(Cliente.id == id_cliente).first()

            if not cliente:
                motivo = f"Cliente con ID {id_cliente} no existe"
                print(f"[SAGA Clientes] Rechazado: {motivo}")
                publicar_evento("pago.fallido", {
                    "id_venta": id_venta,
                    "id_cliente": id_cliente,
                    "id_zapato": id_zapato,
                    "cantidad": cantidad,
                    "motivo": motivo
                })
                return

            if float(cliente.saldo) < monto_total:
                motivo = f"Saldo insuficiente. Saldo disponible: ${float(cliente.saldo):.2f}, Requerido: ${monto_total:.2f}"
                print(f"[SAGA Clientes] Rechazado: {motivo}")
                publicar_evento("pago.fallido", {
                    "id_venta": id_venta,
                    "id_cliente": id_cliente,
                    "id_zapato": id_zapato,
                    "cantidad": cantidad,
                    "motivo": motivo
                })
                return

            # Transacción local exitosa: debitar saldo
            cliente.saldo = float(cliente.saldo) - monto_total
            db.commit()
            print(f"[SAGA Clientes] Pago debitado exitosamente. Nuevo saldo de cliente {cliente.id}: ${float(cliente.saldo):.2f}")

            publicar_evento("pago.exitoso", {
                "id_venta": id_venta,
                "id_cliente": id_cliente,
                "id_zapato": id_zapato,
                "cantidad": cantidad,
                "monto_cobrado": monto_total
            })
        except Exception as e:
            db.rollback()
            print(f"[SAGA Clientes] Error interno al procesar pago: {e}")
            publicar_evento("pago.fallido", {
                "id_venta": id_venta,
                "id_cliente": id_cliente,
                "id_zapato": id_zapato,
                "cantidad": cantidad,
                "motivo": f"Error interno en servicio de clientes: {str(e)}"
            })
        finally:
            db.close()


def iniciar_consumidor():
    def _worker():
        while True:
            try:
                print("[Clientes] Intentando conectar a RabbitMQ...")
                # Reintentos con espera
                params = get_connection_params()
                connection = None
                for _ in range(30):
                    try:
                        connection = pika.BlockingConnection(params)
                        break
                    except Exception:
                        time.sleep(2)

                if not connection:
                    print("[Clientes] No se pudo conectar a RabbitMQ tras varios intentos. Reintentando...")
                    time.sleep(5)
                    continue

                channel = connection.channel()
                channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
                channel.queue_declare(queue=QUEUE_NAME, durable=True)

                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="stock.reservado")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_evento(method.routing_key, data)
                    except Exception as e:
                        print(f"[Clientes Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
                print(f"[Clientes] Consumidor escuchando en cola '{QUEUE_NAME}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Clientes] Conexión caída de RabbitMQ: {e}. Reconectando en 5 segundos...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
