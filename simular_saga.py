import time
import datetime

# Colores para la terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"

def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def log_ventas(msg, delay=0.4):
    time.sleep(delay)
    print(f"{CYAN}ventas-service   |{RESET} {ts()} {msg}")

def log_zapatos(msg, delay=0.4):
    time.sleep(delay)
    print(f"{GREEN}zapatos-service  |{RESET} {ts()} {msg}")

def log_clientes(msg, delay=0.4):
    time.sleep(delay)
    print(f"{YELLOW}clientes-service |{RESET} {ts()} {msg}")

def log_rabbit(msg, delay=0.3):
    time.sleep(delay)
    print(f"{MAGENTA}rabbitmq         |{RESET} {ts()} {msg}")

def ejecutar_simulacion():
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}  INICIALIZANDO SIMULACIÓN DE MICROSERVICIOS CON SAGA (COREOGRAFÍA){RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")

    log_rabbit("[AMQP] Broker iniciado en puerto 5672. Exchange 'tienda.saga' (topic) declarado.", 0.2)
    log_ventas("[INIT] Conectado a MongoDB (tienda_ventas). Consumidor escuchando en 'cola_ventas'.", 0.2)
    log_zapatos("[INIT] Conectado a PostgreSQL (tienda_zapatos). Consumidor escuchando en 'cola_zapatos'.", 0.2)
    log_clientes("[INIT] Conectado a PostgreSQL (tienda_clientes). Consumidor escuchando en 'cola_clientes'.", 0.2)

    time.sleep(1)

    print(f"\n{BOLD}--------------------------------------------------------------------------------{RESET}")
    print(f"{BOLD}  ESCENARIO 1: CAMINO FELIZ (COMPRA EXITOSA - CONSISTENCIA EVENTUAL){RESET}")
    print(f"  Cliente: Samuel L. (Saldo: $500.000) | Zapato: Nike Air Force (Stock: 10, Precio: $250.000)")
    print(f"{BOLD}--------------------------------------------------------------------------------{RESET}\n")

    log_ventas("POST /ventas recibido: {\"id_cliente\": 1, \"id_zapato\": 1, \"cantidad\": 1}", 0.5)
    log_ventas("MongoDB insert: id_venta='674c91a0f8b1', estado='PENDIENTE'. Respuesta HTTP 202 Accepted enviada.")
    log_ventas("[RabbitMQ] Publicando evento: 'venta.creada' -> {'id_venta': '674c91a0f8b1', 'id_cliente': 1, 'id_zapato': 1, 'cantidad': 1}")
    log_rabbit("[Exchange: tienda.saga] Enrutando 'venta.creada' -> cola_zapatos")

    log_zapatos("[RabbitMQ] Recibido evento: 'venta.creada' con id_venta='674c91a0f8b1'")
    log_zapatos("Validando inventario en PostgreSQL para zapato ID 1... Stock disponible: 10")
    log_zapatos("[SAGA Zapatos] Transacción local: Stock decrementado 10 -> 9. COMMIT exitoso.")
    log_zapatos("[RabbitMQ] Publicando evento: 'stock.reservado' -> {'id_venta': '674c91a0f8b1', 'id_cliente': 1, 'id_zapato': 1, 'cantidad': 1, 'monto_total': 250000.0}")
    log_rabbit("[Exchange: tienda.saga] Enrutando 'stock.reservado' -> cola_clientes")

    log_clientes("[RabbitMQ] Recibido evento: 'stock.reservado' con id_venta='674c91a0f8b1'")
    log_clientes("Validando saldo en PostgreSQL para cliente ID 1... Saldo disponible: $500,000.00 | Requerido: $250,000.00")
    log_clientes("[SAGA Clientes] Transacción local: Saldo debitado $500,000 -> $250,000. COMMIT exitoso.")
    log_clientes("[RabbitMQ] Publicando evento: 'pago.exitoso' -> {'id_venta': '674c91a0f8b1', 'id_cliente': 1, 'monto_cobrado': 250000.0}")
    log_rabbit("[Exchange: tienda.saga] Enrutando 'pago.exitoso' -> cola_ventas")

    log_ventas("[RabbitMQ] Recibido evento: 'pago.exitoso' con id_venta='674c91a0f8b1'")
    log_ventas("MongoDB update: Venta 674c91a0f8b1 actualizada a estado='CONFIRMADA'")
    log_ventas(f"{GREEN}[SAGA ÉXITO] Transacción distribuida finalizada. Consistencia eventual alcanzada.{RESET}")

    time.sleep(2)

    print(f"\n{BOLD}--------------------------------------------------------------------------------{RESET}")
    print(f"{BOLD}  ESCENARIO 2: FALLO DE PAGO Y COMPENSACIÓN SAGA (ROLLBACK SEMÁNTICO){RESET}")
    print(f"  Cliente: Carlos Pobre (Saldo: $50.000) | Zapato: Nike Air Force (Stock actual: 9, Precio: $250.000)")
    print(f"{BOLD}--------------------------------------------------------------------------------{RESET}\n")

    log_ventas("POST /ventas recibido: {\"id_cliente\": 2, \"id_zapato\": 1, \"cantidad\": 1}", 0.5)
    log_ventas("MongoDB insert: id_venta='674c91b2c4e3', estado='PENDIENTE'. Respuesta HTTP 202 Accepted enviada.")
    log_ventas("[RabbitMQ] Publicando evento: 'venta.creada' -> {'id_venta': '674c91b2c4e3', 'id_cliente': 2, 'id_zapato': 1, 'cantidad': 1}")
    log_rabbit("[Exchange: tienda.saga] Enrutando 'venta.creada' -> cola_zapatos")

    log_zapatos("[RabbitMQ] Recibido evento: 'venta.creada' con id_venta='674c91b2c4e3'")
    log_zapatos("Validando inventario en PostgreSQL para zapato ID 1... Stock disponible: 9")
    log_zapatos("[SAGA Zapatos] Transacción local: Stock decrementado 9 -> 8. COMMIT exitoso.")
    log_zapatos("[RabbitMQ] Publicando evento: 'stock.reservado' -> {'id_venta': '674c91b2c4e3', 'id_cliente': 2, 'id_zapato': 1, 'cantidad': 1, 'monto_total': 250000.0}")
    log_rabbit("[Exchange: tienda.saga] Enrutando 'stock.reservado' -> cola_clientes")

    log_clientes("[RabbitMQ] Recibido evento: 'stock.reservado' con id_venta='674c91b2c4e3'")
    log_clientes("Validando saldo en PostgreSQL para cliente ID 2... Saldo disponible: $50,000.00 | Requerido: $250,000.00")
    log_clientes(f"{RED}[SAGA Clientes] RECHAZADO: Saldo insuficiente en cuenta del cliente ($50,000.00 < $250,000.00). Saldo NO debitado.{RESET}")
    log_clientes("[RabbitMQ] Publicando evento: 'pago.fallido' -> {'id_venta': '674c91b2c4e3', 'id_cliente': 2, 'id_zapato': 1, 'cantidad': 1, 'motivo': 'Saldo insuficiente'}")
    log_rabbit("[Exchange: tienda.saga] Enrutando 'pago.fallido' -> cola_zapatos Y cola_ventas")

    # Reacciones en paralelo al pago.fallido
    log_zapatos(f"{YELLOW}[SAGA Zapatos - COMPENSACIÓN] Recibido 'pago.fallido' para venta='674c91b2c4e3'. Iniciando Rollback Semántico...{RESET}")
    log_zapatos("Ejecutando compensación en PostgreSQL: zapato.cantidad_disponible += 1")
    log_zapatos("[SAGA Zapatos] COMMIT de compensación exitoso. Stock restaurado de 8 -> 9.")
    log_zapatos(f"{GREEN}[SAGA Zapatos] Evento publicado: 'stock.compensado'. Inventario protegido.{RESET}")

    log_ventas("[RabbitMQ] Recibido evento: 'pago.fallido' con id_venta='674c91b2c4e3'")
    log_ventas("MongoDB update: Venta 674c91b2c4e3 actualizada a estado='CANCELADA', motivo='Saldo insuficiente'")
    log_ventas(f"{RED}[SAGA CANCELADA] Transacción distribuida revertida mediante compensaciones.{RESET}")

    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}  RESUMEN FINAL DE LAS BASES DE DATOS{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")
    print(f"  * MongoDB (Ventas):     Venta 1 -> CONFIRMADA | Venta 2 -> CANCELADA (Saldo insuficiente)")
    print(f"  * PostgreSQL (Zapatos): Zapato 1 Stock final = 9 (Bajó a 8, pero se restauró a 9)")
    print(f"  * PostgreSQL (Clientes): Cliente 1 Saldo = $250.000 | Cliente 2 Saldo = $50.000 (Intacto)")
    print(f"{BOLD}{'='*80}{RESET}\n")

if __name__ == "__main__":
    ejecutar_simulacion()
