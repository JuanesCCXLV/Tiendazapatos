import json
import os
import threading
import time
import pika
from bson import ObjectId
from database import get_db

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")
EXCHANGE_NAME = "tienda.saga"
QUEUE_NAME = "cola_ventas"


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
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", 
        durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(payload).encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent
            )
        )
        print(f"[RabbitMQ - Ventas] Evento publicado: '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[RabbitMQ - Ventas] Error al publicar '{routing_key}': {e}")


def procesar_evento(routing_key: str, data: dict):
    print(f"[RabbitMQ - Ventas] Recibido evento: '{routing_key}' con data: {data}")
    id_venta = data.get("id_venta")
    if not id_venta:
        return

    try:
        filtro = {"_id": ObjectId(id_venta)}
    except Exception:
        filtro = {"_id": id_venta}

    db = get_db()

    # 1. Éxito global de la SAGA: Pago exitoso
    if routing_key == "pago.exitoso":
        db.ventas.update_one(
            filtro,
            {"$set": {"estado": "CONFIRMADA"}}
        )
        print(f"[SAGA Ventas] Transacción distribuida EXITOSA. Venta {id_venta} -> CONFIRMADA")

    # 2. Fallo en Stock: Venta cancelada
    elif routing_key == "stock.rechazado":
        motivo = data.get("motivo", "Stock no disponible")
        db.ventas.update_one(
            filtro,
            {"$set": {"estado": "CANCELADA", "motivo_cancelacion": motivo}}
        )
        print(f"[SAGA Ventas] Venta {id_venta} -> CANCELADA. Motivo: {motivo}")

    # 3. Fallo en Pago: Venta cancelada (el stock fue compensado por zapatos-service)
    elif routing_key == "pago.fallido":
        motivo = data.get("motivo", "Fallo al procesar el pago")
        db.ventas.update_one(
            filtro,
            {"$set": {"estado": "CANCELADA", "motivo_cancelacion": motivo}}
        )
        print(f"[SAGA Ventas] Venta {id_venta} -> CANCELADA por fallo en pago. Motivo: {motivo}")


def iniciar_consumidor():
    def _worker():
        while True:
            try:
                print("[Ventas] Intentando conectar a RabbitMQ...")
                params = get_connection_params()
                connection = None
                for _ in range(30):
                    try:
                        connection = pika.BlockingConnection(params)
                        break
                    except Exception:
                        time.sleep(2)

                if not connection:
                    print("[Ventas] No se pudo conectar a RabbitMQ tras varios intentos. Reintentando...")
                    time.sleep(5)
                    continue

                channel = connection.channel()
                channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
                channel.queue_declare(queue=QUEUE_NAME, durable=True)

                # Escucha eventos que concluyen la venta
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="pago.exitoso")
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="stock.rechazado")
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="pago.fallido")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_evento(method.routing_key, data)
                    except Exception as e:
                        print(f"[Ventas Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
                print(f"[Ventas] Consumidor escuchando en cola '{QUEUE_NAME}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Ventas] Conexión caída de RabbitMQ: {e}. Reconectando en 5 segundos...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
