import json
import os
import threading
import time
from datetime import datetime
import pika
from bson import ObjectId
from database import get_db

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")

EXCHANGE_NAME = "tienda.saga.orquestada"
QUEUE_COMANDOS_VENTAS = "cola_comandos_ventas"
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
    """Envía confirmación de la orden procesada de vuelta al Orquestador."""
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
        print(f"[Ventas -> Orquestador] Respuesta enviada: '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[Ventas Error] No se pudo responder al orquestador: {e}")


def procesar_comando(routing_key: str, data: dict):
    """
    Procesa comandos dirigidos a ventas-service instruidos por el Orquestador:
    - comando.ventas.confirmar: Marca la venta como CONFIRMADA en MongoDB.
    - comando.ventas.cancelar: Marca la venta como CANCELADA en MongoDB con motivo.
    """
    id_saga = data.get("id_saga")
    print(f"\n[Ventas-Service] >>> Comando recibido del Orquestador: '{routing_key}' para SAGA: {id_saga}")

    db = get_db()
    id_cliente = data.get("id_cliente")
    id_zapato = data.get("id_zapato")
    cantidad = data.get("cantidad", 1)

    if routing_key == "comando.ventas.confirmar":
        # Buscar venta por id_saga o registrar una nueva si no existía previa
        venta_existente = db.ventas.find_one({"id_saga": id_saga})
        if venta_existente:
            db.ventas.update_one(
                {"_id": venta_existente["_id"]},
                {"$set": {"estado": "CONFIRMADA", "fecha_confirmacion": datetime.utcnow()}}
            )
            id_venta_str = str(venta_existente["_id"])
        else:
            nueva_venta = {
                "id_saga": id_saga,
                "id_cliente": id_cliente,
                "id_zapato": id_zapato,
                "cantidad": cantidad,
                "fecha": datetime.utcnow(),
                "estado": "CONFIRMADA",
                "motivo_cancelacion": None
            }
            res = db.ventas.insert_one(nueva_venta)
            id_venta_str = str(res.inserted_id)

        print(f"[Ventas-Service] [ORDEN CONFIRMADA] Venta {id_venta_str} guardada en MongoDB con estado='CONFIRMADA'")
        responder_al_orquestador("respuesta.ventas.confirmada", {
            "id_saga": id_saga,
            "id_venta": id_venta_str,
            "status": "OK"
        })

    elif routing_key == "comando.ventas.cancelar":
        motivo = data.get("motivo", "Cancelada por fallo en la SAGA")
        venta_existente = db.ventas.find_one({"id_saga": id_saga})
        if venta_existente:
            db.ventas.update_one(
                {"_id": venta_existente["_id"]},
                {"$set": {"estado": "CANCELADA", "motivo_cancelacion": motivo, "fecha_cancelacion": datetime.utcnow()}}
            )
            id_venta_str = str(venta_existente["_id"])
        else:
            nueva_venta = {
                "id_saga": id_saga,
                "id_cliente": id_cliente,
                "id_zapato": id_zapato,
                "cantidad": cantidad,
                "fecha": datetime.utcnow(),
                "estado": "CANCELADA",
                "motivo_cancelacion": motivo
            }
            res = db.ventas.insert_one(nueva_venta)
            id_venta_str = str(res.inserted_id)

        print(f"[Ventas-Service] [ORDEN CANCELADA] Venta {id_venta_str} guardada en MongoDB con estado='CANCELADA' (Motivo: {motivo})")
        responder_al_orquestador("respuesta.ventas.cancelada", {
            "id_saga": id_saga,
            "id_venta": id_venta_str,
            "status": "OK",
            "motivo": motivo
        })


def iniciar_consumidor():
    """Escucha la cola de comandos exclusiva de Ventas."""
    def _worker():
        while True:
            try:
                print("[Ventas] Conectando a RabbitMQ para escuchar comandos del Orquestador...")
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
                channel.queue_declare(queue=QUEUE_COMANDOS_VENTAS, durable=True)

                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_COMANDOS_VENTAS, routing_key="comando.ventas.*")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_comando(method.routing_key, data)
                    except Exception as e:
                        print(f"[Ventas Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_COMANDOS_VENTAS, on_message_callback=callback)
                print(f"[Ventas] Consumidor de comandos listo en cola '{QUEUE_COMANDOS_VENTAS}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Ventas] Conexión AMQP perdida: {e}. Reconectando en 5s...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
