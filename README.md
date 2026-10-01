# Tienda de Zapatos — Patrón SAGA por Orquestación

Implementación de una arquitectura de **Microservicios con el patrón SAGA por Orquestación**, persistencia políglota (**Database per Service**) y bus de mensajería asíncrona orientado a **Comandos y Respuestas sobre RabbitMQ**.

---

## 🏛️ Arquitectura del Sistema

El ecosistema cuenta con un **Orquestador Central** (`orquestador-service`) que actúa como director de orquesta coordinando las transacciones mediante una **Máquina de Estados Finita**:

1. **Orquestador Service (`localhost:8004`)**
   - **Rol:** Director central de la SAGA. Mantiene la máquina de estados, el registro de auditoría (*Saga Log*) y orquesta las compensaciones (Rollback Semántico).
2. **Zapatos Service (`localhost:8002`)**
   - **Base de datos:** **PostgreSQL** (`zapatos-db`).
   - **Rol:** Atiende `comando.zapatos.reservar` (reserva de inventario) y la compensación `comando.zapatos.liberar` (restitución de inventario).
3. **Clientes Service (`localhost:8001`)**
   - **Base de datos:** **PostgreSQL** (`clientes-db`).
   - **Rol:** Atiende `comando.clientes.cobrar` (débito de saldo). Valida fondos y responde éxito o rechazo por saldo insuficiente.
4. **Ventas Service (`localhost:8003`)**
   - **Base de datos:** **MongoDB** (`ventas-db`).
   - **Rol:** Atiende `comando.ventas.confirmar` y `comando.ventas.cancelar` para almacenar el recibo documental con su estado final.
5. **RabbitMQ (`localhost:5672` / UI: `localhost:15672`)**
   - **Rol:** Bus AMQP para el desacoplamiento mediante colas dedicadas de comandos y respuestas directas.

---

## 🚀 Cómo Ejecutar el Proyecto

### Opción A: Demostración Rápida en Terminal (Sin Docker)
Para exponer o validar el flujo inmediatamente con animación de logs en consola:

```bash
python simular_saga.py
```

### Opción B: Despliegue Completo con Docker Compose
Asegúrate de tener Docker instalado y ejecuta:

```bash
docker compose up --build
```

---

## 🧪 Pruebas Paso a Paso con cURL / Postman / Swagger

### Escenario 1: Camino Feliz (Compra Exitosa de Samuel)
Samuel (ID: 1) cuenta con $500.000 de saldo y compra el zapato Nike Air Force (ID: 1) de $250.000:

* **URL:** `POST http://localhost:8004/saga/comprar`
* **Body:**
```json
{
  "id_cliente": 1,
  "id_zapato": 1,
  "cantidad": 1
}
```
* **Respuesta Inmediata (HTTP 202 Accepted):**
```json
{
  "id_saga": "saga-8a100a00bc",
  "estado": "INICIADA",
  "mensaje": "SAGA iniciada. El Orquestador central está coordinando la transacción."
}
```

* **Consultar Estado de la Transacción:**
`GET http://localhost:8004/saga/saga-8a100a00bc`
Verás el estado en `COMPLETADA` y el historial cronológico de cada paso.

---

### Escenario 2: Fallo de Pago y Rollback Semántico (Carlos Pobre)
Carlos (ID: 2) cuenta con únicamente $50.000 de saldo e intenta comprar un zapato de $250.000:

* **URL:** `POST http://localhost:8004/saga/comprar`
* **Body:**
```json
{
  "id_cliente": 2,
  "id_zapato": 1,
  "cantidad": 1
}
```
* **Flujo Automático del Orquestador:**
  1. Envía comando de reserva a Zapatos -> Zapatos descuenta stock de 9 a 8.
  2. Envía comando de cobro a Clientes -> Clientes rechaza por fondos insuficientes.
  3. **Rollback Semántico:** El Orquestador detecta el fallo, revisa que Zapatos ya había reservado, y despacha `comando.zapatos.liberar`.
  4. Zapatos repone el stock de 8 a 9.
  5. Ventas marca el pedido como `CANCELADA` (Motivo: Saldo insuficiente).
  6. SAGA concluye en estado `CANCELADA` con inventario a salvo y total consistencia.

---

## 📚 Documentación y Material de Exposición

* 📖 **Diagramas y Arquitectura Técnica:** [docs/arquitectura.md](file:///B:/Projects/Ejemplo_DSIII/Tiendazapatos/docs/arquitectura.md)
* 🎤 **Guía de Diapositivas y Qué Decir en la Exposición:** [docs/presentacion_orquestada.md](file:///B:/Projects/Ejemplo_DSIII/Tiendazapatos/docs/presentacion_orquestada.md)

---

## 🌐 Interfaces Gráficas y Documentación Interactiva

- **Orquestador API Docs:** [http://localhost:8004/docs](http://localhost:8004/docs)
- **Ventas API Docs:** [http://localhost:8003/docs](http://localhost:8003/docs)
- **Zapatos API Docs:** [http://localhost:8002/docs](http://localhost:8002/docs)
- **Clientes API Docs:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **RabbitMQ Dashboard:** [http://localhost:15672](http://localhost:15672) *(admin / admin123)*
