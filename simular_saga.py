import time
import datetime

# Colores ANSI para resaltar cada microservicio en la terminal
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log_orquestador(msg, delay=0.45):
    time.sleep(delay)
    print(f"{BLUE}{BOLD}orquestador-service |{RESET} {ts()} {msg}")


def log_zapatos(msg, delay=0.4):
    time.sleep(delay)
    print(f"{GREEN}zapatos-service     |{RESET} {ts()} {msg}")


def log_clientes(msg, delay=0.4):
    time.sleep(delay)
    print(f"{YELLOW}clientes-service    |{RESET} {ts()} {msg}")


def log_ventas(msg, delay=0.4):
    time.sleep(delay)
    print(f"{CYAN}ventas-service      |{RESET} {ts()} {msg}")


def log_rabbit(msg, delay=0.25):
    time.sleep(delay)
    print(f"{MAGENTA}rabbitmq            |{RESET} {ts()} {msg}")


def ejecutar_simulacion():
    print(f"\n{BOLD}{'='*86}{RESET}")
    print(f"{BOLD}   DEMOSTRACIÓN EN VIVO: SAGA ORQUESTADA (DIRECTOR CENTRAL + MÁQUINA DE ESTADOS){RESET}")
    print(f"{BOLD}   Patrón Comando-Respuesta sobre RabbitMQ | Database per Service (Polyglot){RESET}")
    print(f"{BOLD}{'='*86}{RESET}\n")

    log_rabbit("[Broker AMQP] Exchange 'tienda.saga.orquestada' activo. Colas de comandos declaradas.", 0.2)
    log_orquestador("[INIT] Máquina de estados iniciada. Escuchando respuestas en 'cola_orquestador_respuestas'.", 0.2)
    log_zapatos("[INIT] Conectado a PostgreSQL (tienda_zapatos). Escuchando comandos en 'cola_comandos_zapatos'.", 0.2)
    log_clientes("[INIT] Conectado a PostgreSQL (tienda_clientes). Escuchando comandos en 'cola_comandos_clientes'.", 0.2)
    log_ventas("[INIT] Conectado a MongoDB (tienda_ventas). Escuchando comandos en 'cola_comandos_ventas'.", 0.2)

    time.sleep(1)

    # =========================================================================
    # DIAPOSITIVA 5: ESCENARIO 1 - CAMINO FELIZ CON ORQUESTADOR
    # =========================================================================
    print(f"\n{BOLD}{'='*86}{RESET}")
    print(f"{BOLD}  [DIAPOSITIVA 5] CASO PRÁCTICO - ESCENARIO 1: CAMINO FELIZ CON ORQUESTADOR{RESET}")
    print(f"  Cliente: Samuel L. (Saldo: $500.000) | Zapato: Nike Air Force (Stock: 10, Precio: $250.000)")
    print(f"  Flujo: Orquestador coordina reserva en Zapatos -> cobro en Clientes -> confirmación en Ventas")
    print(f"{BOLD}{'='*86}{RESET}\n")

    log_orquestador("POST /saga/comprar recibido: {\"id_cliente\": 1, \"id_zapato\": 1, \"cantidad\": 1}", 0.5)
    log_orquestador("Máquina de Estados: Creando SAGA 'saga-8a100a00bc'. Estado inicial: INICIADA.")
    log_orquestador("HTTP 202 Accepted retornado al cliente: {\"id_saga\": \"saga-8a100a00bc\", \"estado\": \"INICIADA\"}")

    # Paso 1: Orquestador -> Zapatos
    log_orquestador("Paso 1 -> Despachando COMANDO a Zapatos: 'comando.zapatos.reservar' (id_zapato=1, cant=1)")
    log_orquestador("Máquina de Estados: Transición -> RESERVANDO_STOCK")
    log_rabbit("[Exchange] Enrutando COMANDO 'comando.zapatos.reservar' -> cola_comandos_zapatos")

    log_zapatos("[RabbitMQ] Comando recibido: 'comando.zapatos.reservar' para SAGA 'saga-8a100a00bc'")
    log_zapatos("Consultando inventario en PostgreSQL: Zapato ID 1 ('Nike Air Force'). Stock actual: 10")
    log_zapatos("[COMMIT LOCAL] Descontando stock de 10 a 9 unidades en PostgreSQL. Commit exitoso.")
    log_zapatos("Enviando RESPUESTA directa al Orquestador: 'respuesta.zapatos.reservado' -> {'status': 'OK', 'precio_unitario': 250000.0, 'monto_total': 250000.0}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.zapatos.reservado' -> cola_orquestador_respuestas")

    # Paso 2: Orquestador recibe respuesta y avanza a Clientes
    log_orquestador("[RESPUESTA RECIBIDA] Zapatos reporta 'OK'. Stock reservado exitosamente.")
    log_orquestador("Máquina de Estados: Registro de auditoría actualizado. Transición -> STOCK_RESERVADO.")
    log_orquestador("Paso 2 -> Despachando COMANDO a Clientes: 'comando.clientes.cobrar' (id_cliente=1, monto=$250.000)")
    log_orquestador("Máquina de Estados: Transición -> PROCESANDO_PAGO")
    log_rabbit("[Exchange] Enrutando COMANDO 'comando.clientes.cobrar' -> cola_comandos_clientes")

    log_clientes("[RabbitMQ] Comando recibido: 'comando.clientes.cobrar' para SAGA 'saga-8a100a00bc'")
    log_clientes("Consultando saldo en PostgreSQL: Cliente ID 1 ('Samuel L.'). Saldo disponible: $500.000 | Requerido: $250.000")
    log_clientes("[COMMIT LOCAL] Debitando fondos en PostgreSQL: $500.000 -> $250.000. Commit exitoso.")
    log_clientes("Enviando RESPUESTA directa al Orquestador: 'respuesta.clientes.cobrado' -> {'status': 'OK', 'monto_cobrado': 250000.0}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.clientes.cobrado' -> cola_orquestador_respuestas")

    # Paso 3: Orquestador recibe cobro y manda confirmar orden en Ventas
    log_orquestador("[RESPUESTA RECIBIDA] Clientes reporta 'OK'. Pago debitado exitosamente.")
    log_orquestador("Máquina de Estados: Transición -> PAGO_EXITOSO.")
    log_orquestador("Paso 3 -> Despachando COMANDO a Ventas: 'comando.ventas.confirmar' (Marcar venta como CONFIRMADA)")
    log_orquestador("Máquina de Estados: Transición -> CONFIRMANDO_VENTA")
    log_rabbit("[Exchange] Enrutando COMANDO 'comando.ventas.confirmar' -> cola_comandos_ventas")

    log_ventas("[RabbitMQ] Comando recibido: 'comando.ventas.confirmar' para SAGA 'saga-8a100a00bc'")
    log_ventas("Insertando/Actualizando pedido en MongoDB (tienda_ventas): Venta CONFIRMADA.")
    log_ventas("Enviando RESPUESTA al Orquestador: 'respuesta.ventas.confirmada' -> {'status': 'OK'}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.ventas.confirmada' -> cola_orquestador_respuestas")

    log_orquestador("[RESPUESTA RECIBIDA] Ventas reporta 'OK'.")
    log_orquestador(f"{GREEN}[SAGA COMPLETADA] Máquina de Estados: Transición final -> COMPLETADA. Transacción distribuida exitosa.{RESET}")

    time.sleep(2)

    # =========================================================================
    # DIAPOSITIVA 6: ESCENARIO 2 - FALLO Y COMPENSACIÓN CON ORQUESTADOR
    # =========================================================================
    print(f"\n{BOLD}{'='*86}{RESET}")
    print(f"{BOLD}  [DIAPOSITIVA 6] CASO PRÁCTICO - ESCENARIO 2: FALLO Y COMPENSACIÓN (ROLLBACK SEMÁNTICO){RESET}")
    print(f"  Cliente: Carlos Pobre (Saldo: $50.000) | Zapato: Nike Air Force (Stock actual: 9, Precio: $250.000)")
    print(f"  Flujo: Orquestador reserva stock (9->8) -> Clientes rechaza por saldo -> Orquestador revierte stock (8->9)")
    print(f"{BOLD}{'='*86}{RESET}\n")

    log_orquestador("POST /saga/comprar recibido: {\"id_cliente\": 2, \"id_zapato\": 1, \"cantidad\": 1}", 0.5)
    log_orquestador("Máquina de Estados: Creando SAGA 'saga-9b211b11cd'. Estado inicial: INICIADA.")
    log_orquestador("HTTP 202 Accepted retornado al cliente.")

    # Paso 1: Reserva de stock
    log_orquestador("Paso 1 -> Despachando COMANDO a Zapatos: 'comando.zapatos.reservar' (id_zapato=1, cant=1)")
    log_orquestador("Máquina de Estados: Transición -> RESERVANDO_STOCK")
    log_rabbit("[Exchange] Enrutando COMANDO 'comando.zapatos.reservar' -> cola_comandos_zapatos")

    log_zapatos("[RabbitMQ] Comando recibido: 'comando.zapatos.reservar' para SAGA 'saga-9b211b11cd'")
    log_zapatos("Consultando inventario en PostgreSQL: Zapato ID 1. Stock actual: 9")
    log_zapatos("[COMMIT LOCAL] Descontando stock de 9 a 8 unidades en PostgreSQL. Commit exitoso.")
    log_zapatos("Enviando RESPUESTA al Orquestador: 'respuesta.zapatos.reservado' -> {'status': 'OK', 'precio_unitario': 250000.0, 'monto_total': 250000.0}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.zapatos.reservado' -> cola_orquestador_respuestas")

    # Paso 2: Intento de cobro
    log_orquestador("[RESPUESTA RECIBIDA] Zapatos reporta 'OK'. Stock reservado (9 -> 8).")
    log_orquestador("Máquina de Estados: Historial registrado [Paso 1: Zapatos RESERVADO]. Transición -> STOCK_RESERVADO.")
    log_orquestador("Paso 2 -> Despachando COMANDO a Clientes: 'comando.clientes.cobrar' (id_cliente=2, monto=$250.000)")
    log_orquestador("Máquina de Estados: Transición -> PROCESANDO_PAGO")
    log_rabbit("[Exchange] Enrutando COMANDO 'comando.clientes.cobrar' -> cola_comandos_clientes")

    log_clientes("[RabbitMQ] Comando recibido: 'comando.clientes.cobrar' para SAGA 'saga-9b211b11cd'")
    log_clientes("Consultando saldo en PostgreSQL: Cliente ID 2 ('Carlos Pobre'). Saldo disponible: $50.000 | Requerido: $250.000")
    log_clientes(f"{RED}[RECHAZADO] Saldo insuficiente en cuenta: $50.000 < $250.000. Fondos NO debitados.{RESET}")
    log_clientes("Enviando RESPUESTA de error al Orquestador: 'respuesta.clientes.fallo' -> {'status': 'ERROR', 'motivo': 'Saldo insuficiente'}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.clientes.fallo' -> cola_orquestador_respuestas")

    # Paso 3: El Orquestador toma el control del Rollback Semántico
    log_orquestador(f"{RED}[RESPUESTA RECIBIDA] Clientes reporta 'ERROR': Saldo insuficiente.{RESET}")
    log_orquestador(f"{YELLOW}[CONTROL CENTRAL DE ROLLBACK] El Orquestador detiene el avance y activa la reversa.{RESET}")
    log_orquestador("Consultando historial de auditoría: 'Paso 1: Zapatos fue ejecutado exitosamente'.")
    log_orquestador("Generando COMANDO COMPENSATORIO INVERSO -> 'comando.zapatos.liberar' (Restituir 1 unidad al stock)")
    log_orquestador("Máquina de Estados: Transición -> COMPENSANDO_STOCK")
    log_rabbit("[Exchange] Enrutando COMANDO DE COMPENSACIÓN 'comando.zapatos.liberar' -> cola_comandos_zapatos")

    log_zapatos(f"{YELLOW}[COMPENSACIÓN EN PROCESO] Comando compensatorio recibido: 'comando.zapatos.liberar'{RESET}")
    log_zapatos("Ejecutando Rollback Semántico en PostgreSQL: zapato.cantidad_disponible = 8 + 1")
    log_zapatos("[COMMIT COMPENSACIÓN] Stock restaurado exitosamente en PostgreSQL: 8 -> 9 unidades.")
    log_zapatos("Enviando RESPUESTA de compensación al Orquestador: 'respuesta.zapatos.liberado' -> {'status': 'COMPENSADO', 'stock_actual': 9}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.zapatos.liberado' -> cola_orquestador_respuestas")

    # Paso 4: Cierre de la SAGA en Ventas
    log_orquestador("[RESPUESTA RECIBIDA] Zapatos confirmó compensación exitosa. Inventario a salvo.")
    log_orquestador("Máquina de Estados: Transición -> STOCK_COMPENSADO.")
    log_orquestador("Despachando COMANDO final a Ventas: 'comando.ventas.cancelar' (Motivo: Saldo insuficiente)")
    log_orquestador("Máquina de Estados: Transición -> CANCELANDO_VENTA")
    log_rabbit("[Exchange] Enrutando COMANDO 'comando.ventas.cancelar' -> cola_comandos_ventas")

    log_ventas("[RabbitMQ] Comando recibido: 'comando.ventas.cancelar'")
    log_ventas("Actualizando pedido en MongoDB: Venta CANCELADA (Motivo: Saldo insuficiente).")
    log_ventas("Enviando RESPUESTA al Orquestador: 'respuesta.ventas.cancelada' -> {'status': 'OK'}")
    log_rabbit("[Exchange] Enrutando RESPUESTA 'respuesta.ventas.cancelada' -> cola_orquestador_respuestas")

    log_orquestador(f"{RED}[SAGA CANCELADA] Máquina de Estados: Transición final -> CANCELADA.{RESET}")
    log_orquestador(f"{GREEN}[CONSISTENCIA GARANTIZADA] La transacción fue revertida en orden inverso y el sistema está íntegro.{RESET}")

    # Resumen
    print(f"\n{BOLD}{'='*86}{RESET}")
    print(f"{BOLD}  ESTADO FINAL EN LAS BASES DE DATOS TRAS LA ORQUESTACIÓN{RESET}")
    print(f"{BOLD}{'='*86}{RESET}")
    print(f"  * {BOLD}Orquestador SAGA:{RESET}  SAGA 1: COMPLETADA (100%) | SAGA 2: CANCELADA (Compensada al 100%)")
    print(f"  * {BOLD}PostgreSQL (Zapatos):{RESET}  Stock Zapato 1 = 9 unidades (Bajó a 8 por Carlos, pero el Orquestador lo devolvió a 9)")
    print(f"  * {BOLD}PostgreSQL (Clientes):{RESET} Saldo Samuel = $250.000 | Saldo Carlos Pobre = $50.000 (Sin cobro)")
    print(f"  * {BOLD}MongoDB (Ventas):{RESET}      Pedido 1: CONFIRMADA | Pedido 2: CANCELADA (Saldo insuficiente)")
    print(f"{BOLD}{'='*86}{RESET}\n")


if __name__ == "__main__":
    ejecutar_simulacion()
