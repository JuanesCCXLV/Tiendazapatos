from fastapi import FastAPI, Depends, HTTPException
from pymongo.database import Database
import httpx
from datetime import datetime

from database import get_db
from schemas import VentaCreate, VentaResponse, VentaDetalleResponse
from messaging import iniciar_consumidor

app = FastAPI(
    title="Servicio de Ventas (SAGA Orquestada)",
    description="Microservicio de Ventas: registra órdenes y recibe comandos del Orquestador para confirmar o cancelar",
    version="2.0.0"
)


@app.on_event("startup")
def startup_event():
    iniciar_consumidor()


@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Ventas funcionando en modo SAGA Orquestada",
        "rol_saga": "Participante: recibe comandos de confirmación o cancelación del Orquestador"
    }


@app.post("/ventas", response_model=VentaResponse)
def crear_venta(
    venta: VentaCreate,
    db: Database = Depends(get_db)
):
    """
    Crea una venta inicial en estado PENDIENTE.
    (Para coordinar la transacción completa bajo la máquina de estados,
    se recomienda usar el endpoint del Orquestador: POST http://localhost:8004/saga/comprar)
    """
    nueva_venta = {
        "id_cliente": venta.id_cliente,
        "id_zapato": venta.id_zapato,
        "cantidad": venta.cantidad or 1,
        "fecha": datetime.utcnow(),
        "estado": "PENDIENTE",
        "motivo_cancelacion": None,
        "id_saga": None
    }

    resultado = db.ventas.insert_one(nueva_venta)

    return {
        "id": str(resultado.inserted_id),
        "id_cliente": nueva_venta["id_cliente"],
        "id_zapato": nueva_venta["id_zapato"],
        "cantidad": nueva_venta["cantidad"],
        "fecha": nueva_venta["fecha"],
        "estado": nueva_venta["estado"],
        "motivo_cancelacion": None,
        "id_saga": None
    }


@app.get("/ventas", response_model=list[VentaDetalleResponse])
def obtener_ventas(
    db: Database = Depends(get_db)
):
    ventas = list(db.ventas.find())
    resultado_final = []

    for v in ventas:
        venta_formateada = {
            "id": str(v["_id"]),
            "fecha": v.get("fecha", datetime.utcnow()),
            "estado": v.get("estado", "CONFIRMADA"),
            "motivo_cancelacion": v.get("motivo_cancelacion"),
            "id_saga": v.get("id_saga"),
            "cliente": {},
            "zapato": {}
        }

        try:
            res_cliente = httpx.get(
                f"http://clientes-service:8001/clientes/{v['id_cliente']}",
                timeout=5.0
            )
            if res_cliente.status_code == 200:
                venta_formateada["cliente"] = res_cliente.json()

            res_zapato = httpx.get(
                f"http://zapatos-service:8002/zapatos/{v['id_zapato']}",
                timeout=5.0
            )
            if res_zapato.status_code == 200:
                venta_formateada["zapato"] = res_zapato.json()

        except httpx.RequestError:
            pass

        resultado_final.append(venta_formateada)

    return resultado_final
