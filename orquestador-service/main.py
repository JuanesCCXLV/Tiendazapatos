import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from state_machine import saga_store, SagaStatus
from messaging import despachar_comando, iniciar_consumidor_orquestador


app = FastAPI(
    title="Orquestador SAGA - Tienda de Zapatos",
    description="Director central de la transacción distribuida (Saga Orquestada con RabbitMQ)",
    version="2.0.0"
)


class CompraRequest(BaseModel):
    id_cliente: int
    id_zapato: int
    cantidad: Optional[int] = 1


@app.on_event("startup")
def startup_event():
    iniciar_consumidor_orquestador()


@app.get("/")
def inicio():
    return {
        "servicio": "Orquestador SAGA Central",
        "descripcion": "Coordina las transacciones distribuidas mediante comandos y respuestas directas",
        "endpoints": {
            "iniciar_compra": "POST /saga/comprar",
            "consultar_saga": "GET /saga/{id_saga}",
            "listar_sagas": "GET /saga"
        }
    }


@app.post("/saga/comprar", status_code=202)
def iniciar_saga_compra(req: CompraRequest):
    """
    Punto de entrada de la SAGA Orquestada:
    1. Genera un ID único para la transacción distribuida.
    2. Registra la SAGA en la máquina de estados del Orquestador.
    3. Despacha el primer comando ('comando.zapatos.reservar') al servicio de Zapatos.
    4. Responde inmediatamente 202 Accepted (asincronía / consistencia eventual).
    """
    id_saga = f"saga-{uuid.uuid4().hex[:12]}"
    cantidad = req.cantidad if req.cantidad and req.cantidad > 0 else 1

    # 1. Registrar en la máquina de estados
    saga = saga_store.crear_saga(
        id_saga=id_saga,
        id_cliente=req.id_cliente,
        id_zapato=req.id_zapato,
        cantidad=cantidad
    )

    # 2. Despachar el primer comando hacia Zapatos
    saga.estado = SagaStatus.RESERVANDO_STOCK
    saga.registrar_evento("DESPACHAR_COMANDO_RESERVA", f"Despachando comando.zapatos.reservar para zapato {req.id_zapato}")

    despachar_comando("comando.zapatos.reservar", {
        "id_saga": id_saga,
        "id_cliente": req.id_cliente,
        "id_zapato": req.id_zapato,
        "cantidad": cantidad
    })

    return {
        "id_saga": id_saga,
        "estado": saga.estado.value,
        "mensaje": "SAGA iniciada. El Orquestador central está coordinando la transacción.",
        "detalle": {
            "cliente_id": req.id_cliente,
            "zapato_id": req.id_zapato,
            "cantidad": cantidad
        }
    }


@app.get("/saga/{id_saga}")
def consultar_saga(id_saga: str):
    """Permite auditar el estado exacto, pasos ejecutados y compensaciones de una SAGA."""
    saga = saga_store.obtener_saga(id_saga)
    if not saga:
        raise HTTPException(status_code=404, detail="SAGA no encontrada")
    return saga.to_dict()


@app.get("/saga")
def listar_sagas():
    """Lista todas las SAGAs gestionadas por este orquestador."""
    return saga_store.listar_sagas()
