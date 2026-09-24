# Tienda de Zapatos - Arquitectura de Microservicios

Este proyecto es una demostración práctica de la arquitectura de **Microservicios utilizando el patrón "Database per Service" (Base de datos por servicio)** y persistencia políglota. Está desarrollado en Python con **FastAPI** y dockerizado para su fácil despliegue.

## Arquitectura

El sistema se compone de tres microservicios completamente independientes. Cada servicio expone su propia API y encapsula su base de datos privada:

1. **Clientes Service** (`localhost:8001`) 
   - Base de datos: **PostgreSQL** (`clientes-db`).
   - Propósito: Manejo estricto relacional de los datos de los usuarios.
2. **Zapatos Service** (`localhost:8002`)
   - Base de datos: **PostgreSQL** (`zapatos-db`).
   - Propósito: Control estricto relacional del inventario del calzado.
3. **Ventas Service** (`localhost:8003`)
   - Base de datos: **MongoDB** (`ventas-db`).
   - Propósito: Base de datos documental (NoSQL) para almacenar recibos y transacciones ágilmente. Se comunica por peticiones HTTP internas con los otros nodos para validar la existencia de clientes y zapatos (Composición por API).

---

## Cómo Ejecutar el Proyecto

Asegúrate de tener Docker y Docker Compose instalados en tu computadora. En la terminal, dirígete a la carpeta raíz (donde se encuentra `docker-compose.yml`) y levanta todo el ecosistema con:

```bash
docker compose up --build
```
> *Nota:* La primera vez puede tardar unos minutos descargando las imágenes oficiales de Python, PostgreSQL y MongoDB.

---

## Flujo Funcional (Paso a Paso en Postman o cURL)

Para probar correctamente la integración, la base de datos empezará en blanco. Deberás seguir este orden lógico para completar una venta:

### Paso 1: Crea un Zapato nuevo en el inventario
Contacta únicamente a la API de zapatos para crear calzado.

* **URL:** `POST http://localhost:8002/zapatos`
* **Cuerpo (JSON raw):**
```json
{
  "marca": "Nike Air Force",
  "talla": 39.5,
  "color": "Blanco",
  "precio": 250000.0,
  "cantidad_disponible": 15
}
```
*Si fue exitoso, te devolverá el JSON comprobando la inserción. (Supongamos que le asignan el ID `1`).*

### Paso 2: Registra a un nuevo Cliente
Contacta únicamente a la API de clientes.

* **URL:** `POST http://localhost:8001/clientes`
* **Cuerpo (JSON raw):**
```json
{
  "nombre": "Samuel L.",
  "email": "samuel@ejemplo.com",
  "telefono": "3000000000"
}
```
*Si fue exitoso, devuelve al cliente. (Supongamos que le asignan el ID `1`).*

### Paso 3: Genera la Venta
Contacta a la API de ventas. Este servicio intentará comunicarse en secreto de fondo con el servicio de clientes y con el de zapatos para validar que el `id` 1 de cada uno sí es real. 

* **URL:** `POST http://localhost:8003/ventas`
* **Cuerpo (JSON raw):**
*(Simulando que el cliente 1 compró el zapato 1)*
```json
{
  "id_cliente": 1,
  "id_zapato": 1
}
```
*Si un `id` fuera falso o inventado, el servicio de ventas interceptaría el fallo HTTP y te respondería un Status 400. Al ser correcto, MongoDB inyectará la venta y generará un ObjectID automático alfanumérico.*

### Paso 4: Visualiza las Ventas Consolidadas
Realiza una petición de lectura sobre el servicio de ventas. Este consultará a MongoDB, pero a su vez lanzará múltiples peticiones Get HTTP paralelas a clientes y zapatos para inyectar su información (Composición de API) en el JSON final.

* **URL:** `GET http://localhost:8003/ventas`
* **Respuesta Esperada:**
```json
[
  {
    "id": "64bcdeea0f23a88a100a00bc",
    "fecha": "2026-09-23T23:45:10.053000",
    "cliente": {
      "id": 1,
      "email": "samuel@ejemplo.com",
      "telefono": "3000000000",
      "nombre": "Samuel L."
    },
    "zapato": {
      "id_zapato": 1,
      "precio": 250000.0,
      "color": "Blanco",
      "cantidad_disponible": 15,
      "marca": "Nike Air Force",
      "talla": 39.5
    }
  }
]
```

## Re-documentación Automática (Swagger)
FastAPI auto-documenta todos los endpoints. Para explorar y testear en interfaz gráfica (sin usar Postman), puedes abrir directamente tu navegador en:

- Zapatos Docs: [http://localhost:8002/docs](http://localhost:8002/docs)
- Clientes Docs: [http://localhost:8001/docs](http://localhost:8001/docs)
- Ventas Docs: [http://localhost:8003/docs](http://localhost:8003/docs)
