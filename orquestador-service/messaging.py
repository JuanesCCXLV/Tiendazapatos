import json
import os
import threading
import time
import pika
from state_machine import saga_store, SagaStatus

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin123")

EXCHANGE_NAME = "tienda.saga.orquestada"
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


def despachar_comando(routing_key: str, payload: dict):
    """
    Envía un COMANDO DIRECTO desde el Orquestador hacia la cola específica del participante.
    Patrón Comando-Respuesta sobre RabbitMQ.
    """
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
        print(f"[ORQUESTADOR -> COMANDO] Despachado '{routing_key}' con payload: {payload}")
        connection.close()
    except Exception as e:
        print(f"[ORQUESTADOR Error] No se pudo despachar el comando '{routing_key}': {e}")


def procesar_respuesta(routing_key: str, data: dict):
    """
    Núcleo del Orquestador: máquina de estados que reacciona a las respuestas de los participantes.
    Decide el siguiente paso a ejecutar o activa el Rollback Semántico si ocurre un fallo.
    """
    id_saga = data.get("id_saga")
    saga = saga_store.obtener_saga(id_saga)

    if not saga:
        print(f"[ORQUESTADOR Warning] Respuesta recibida para SAGA desconocida: {id_saga}")
        return

    print(f"\n[ORQUESTADOR] <<< Respuesta recibida: '{routing_key}' | SAGA: {id_saga} | Estado actual: {saga.estado.value}")

    # =========================================================================
    # 1. RESPUESTA DE ZAPATOS
    # =========================================================================
    if routing_key == "respuesta.zapatos.reservado":
        # Reserva exitosa de stock
        saga.precio_unitario = float(data.get("precio_unitario", 0.0))
        saga.monto_total = float(data.get("monto_total", 0.0))
        saga.estado = SagaStatus.STOCK_RESERVADO
        saga.registrar_evento("STOCK_RESERVADO_OK", f"Stock reservado ({saga.cantidad} un). Monto total calculado: ${saga.monto_total:,.2f}")

        # Avanzar el flujo: Orquestador despacha comando de cobro a Clientes
        print(f"[ORQUESTADOR -> MÁQUINA DE ESTADOS] Avanzando SAGA: Despachando comando de pago a Clientes...")
        saga.estado = SagaStatus.PROCESANDO_PAGO
        despachar_comando("comando.clientes.cobrar", {
            "id_saga": id_saga,
            "id_cliente": saga.id_cliente,
            "monto": saga.monto_total
        })

    elif routing_key == "respuesta.zapatos.fallo":
        # Fallo en stock: No hay nada que compensar aún
        motivo = data.get("motivo", "Stock insuficiente")
        saga.error = motivo
        saga.registrar_evento("STOCK_FALLIDO", motivo, exito=False)
        print(f"[ORQUESTADOR -> FALLO TEMPRANO] Zapatos no pudo reservar. Cancelando SAGA...")
        saga.estado = SagaStatus.CANCELADA
        despachar_comando("comando.ventas.cancelar", {
            "id_saga": id_saga,
            "id_cliente": saga.id_cliente,
            "id_zapato": saga.id_zapato,
            "cantidad": saga.cantidad,
            "motivo": motivo
        })

    # =========================================================================
    # 2. RESPUESTA DE CLIENTES
    # =========================================================================
    elif routing_key == "respuesta.clientes.cobrado":
        # Cobro exitoso
        saga.estado = SagaStatus.PAGO_EXITOSO
        saga.registrar_evento("PAGO_OK", f"Cobro exitoso de ${saga.monto_total:,.2f} al cliente {saga.id_cliente}")

        # Avanzar el flujo: Orquestador despacha comando de confirmación a Ventas
        print(f"[ORQUESTADOR -> MÁQUINA DE ESTADOS] Pago confirmado. Despachando confirmación de venta a Ventas...")
        saga.estado = SagaStatus.CONFIRMANDO_VENTA
        despachar_comando("comando.ventas.confirmar", {
            "id_saga": id_saga,
            "id_cliente": saga.id_cliente,
            "id_zapato": saga.id_zapato,
            "cantidad": saga.cantidad,
            "monto_total": saga.monto_total
        })

    elif routing_key == "respuesta.clientes.fallo":
        # ¡¡¡FALLO EN EL PAGO (ROLLBACK SEMÁNTICO - COMPENSACIÓN)!!!
        motivo = data.get("motivo", "Saldo insuficiente")
        saga.error = motivo
        saga.registrar_evento("PAGO_FALLIDO", f"Rechazado por Clientes: {motivo}", exito=False)

        print(f"\n{'='*75}")
        print(f"[ORQUESTADOR -> ACTIVANDO ROLLBACK SEMÁNTICO]")
        print(f"El pago falló por '{motivo}'.")
        print(f"Revisando historial: El stock ya fue reservado en Zapatos.")
        print(f"Despachando comando de compensación: 'comando.zapatos.liberar'")
        print(f"{'='*75}\n")

        saga.estado = SagaStatus.COMPENSANDO_STOCK
        saga.registrar_evento("COMPENSACION_INICIADA", f"Ordenando a Zapatos liberar {saga.cantidad} unidades")
        despachar_comando("comando.zapatos.liberar", {
            "id_saga": id_saga,
            "id_zapato": saga.id_zapato,
            "cantidad": saga.cantidad,
            "motivo": motivo
        })

    # =========================================================================
    # 3. RESPUESTAS DE COMPENSACIÓN Y FINALIZACIÓN
    # =========================================================================
    elif routing_key == "respuesta.zapatos.liberado":
        # Confirmación de que el inventario fue restaurado
        stock_actual = data.get("stock_actual")
        saga.estado = SagaStatus.STOCK_COMPENSADO
        saga.registrar_evento("STOCK_COMPENSADO_OK", f"Zapatos confirmó reposición de stock. Stock actual: {stock_actual}")

        print(f"[ORQUESTADOR] Inventario protegido exitosamente. Notificando cancelación final a Ventas...")
        saga.estado = SagaStatus.CANCELANDO_VENTA
        despachar_comando("comando.ventas.cancelar", {
            "id_saga": id_saga,
            "id_cliente": saga.id_cliente,
            "id_zapato": saga.id_zapato,
            "cantidad": saga.cantidad,
            "motivo": saga.error or "Cancelada por compensación SAGA"
        })

    elif routing_key == "respuesta.ventas.confirmada":
        # SAGA FINALIZADA CON ÉXITO
        saga.estado = SagaStatus.COMPLETADA
        saga.registrar_evento("SAGA_COMPLETADA", "Venta registrada como CONFIRMADA. Transacción distribuida finalizada con éxito.")
        print(f"\n[ORQUESTADOR -> ÉXITO GLOBAL] >>> SAGA {id_saga} COMPLETADA EXITOSAMENTE <<<\n")

    elif routing_key == "respuesta.ventas.cancelada":
        # SAGA FINALIZADA CON ROLLBACK
        saga.estado = SagaStatus.CANCELADA
        saga.registrar_evento("SAGA_CANCELADA", f"Venta registrada como CANCELADA. Rollback semántico concluido.")
        print(f"\n[ORQUESTADOR -> ROLLBACK COMPLETO] >>> SAGA {id_saga} CANCELADA Y COMPENSADA <<<\n")


def iniciar_consumidor_orquestador():
    """Escucha la cola exclusiva donde todos los microservicios envían sus respuestas al Orquestador."""
    def _worker():
        while True:
            try:
                print("[Orquestador] Conectando a RabbitMQ para escuchar respuestas de los servicios...")
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
                channel.queue_declare(queue=QUEUE_RESPUESTAS_ORQUESTADOR, durable=True)

                # Escuchar todas las respuestas dirigidas al orquestador
                channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_RESPUESTAS_ORQUESTADOR, routing_key="respuesta.#")

                def callback(ch, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        procesar_respuesta(method.routing_key, data)
                    except Exception as e:
                        print(f"[Orquestador Callback Error]: {e}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_RESPUESTAS_ORQUESTADOR, on_message_callback=callback)
                print(f"[Orquestador] Consumidor de respuestas activo en cola '{QUEUE_RESPUESTAS_ORQUESTADOR}'...")
                channel.start_consuming()

            except Exception as e:
                print(f"[Orquestador] Conexión AMQP perdida: {e}. Reconectando en 5s...")
                time.sleep(5)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
