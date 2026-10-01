from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from pymongo.database import Database
from bson import ObjectId
import httpx
from datetime import datetime

from database import get_db
from schemas import VentaCreate, VentaResponse, VentaDetalleResponse
from messaging import iniciar_consumidor, publicar_evento


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicia el consumidor de eventos SAGA en segundo plano
    iniciar_consumidor()
    yield


app = FastAPI(
    title="Servicio de Ventas",
    description="Microservicio encargado de administrar las ventas mediante el patrón SAGA Coreografía",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Ventas funcionando con SAGA Choreography"
    }


@app.post("/ventas", response_model=VentaResponse, status_code=status.HTTP_202_ACCEPTED)
def crear_venta(
    venta: VentaCreate,
    db: Database = Depends(get_db)
):
    """
    Inicia una transacción distribuida (SAGA).
    Crea la venta en estado PENDIENTE y emite el evento 'venta.creada' hacia RabbitMQ.
    """
    nueva_venta = {
        "id_cliente": venta.id_cliente,
        "id_zapato": venta.id_zapato,
        "cantidad": venta.cantidad if venta.cantidad else 1,
        "estado": "PENDIENTE",
        "motivo_cancelacion": None,
        "fecha": datetime.utcnow()
    }

    resultado = db.ventas.insert_one(nueva_venta)
    id_venta_str = str(resultado.inserted_id)

    # Publicar el primer evento de la Coreografía SAGA
    publicar_evento("venta.creada", {
        "id_venta": id_venta_str,
        "id_cliente": nueva_venta["id_cliente"],
        "id_zapato": nueva_venta["id_zapato"],
        "cantidad": nueva_venta["cantidad"]
    })

    return {
        "id": id_venta_str,
        "id_cliente": nueva_venta["id_cliente"],
        "id_zapato": nueva_venta["id_zapato"],
        "cantidad": nueva_venta["cantidad"],
        "estado": nueva_venta["estado"],
        "motivo_cancelacion": nueva_venta["motivo_cancelacion"],
        "fecha": nueva_venta["fecha"]
    }


@app.get("/ventas/{id_venta}", response_model=VentaDetalleResponse)
def obtener_venta(
    id_venta: str,
    db: Database = Depends(get_db)
):
    try:
        oid = ObjectId(id_venta)
        venta = db.ventas.find_one({"_id": oid})
    except Exception:
        venta = db.ventas.find_one({"_id": id_venta})

    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    venta_formateada = {
        "id": str(venta["_id"]),
        "fecha": venta["fecha"],
        "cantidad": venta.get("cantidad", 1),
        "estado": venta.get("estado", "DESCONOCIDO"),
        "motivo_cancelacion": venta.get("motivo_cancelacion"),
        "cliente": {},
        "zapato": {}
    }

    try:
        res_cliente = httpx.get(
            f"http://clientes-service:8001/clientes/{venta['id_cliente']}",
            timeout=5.0
        )
        if res_cliente.status_code == 200:
            venta_formateada["cliente"] = res_cliente.json()

        res_zapato = httpx.get(
            f"http://zapatos-service:8002/zapatos/{venta['id_zapato']}",
            timeout=5.0
        )
        if res_zapato.status_code == 200:
            venta_formateada["zapato"] = res_zapato.json()
    except httpx.RequestError:
        pass

    return venta_formateada


@app.get("/ventas", response_model=list[VentaDetalleResponse])
def obtener_ventas(
    db: Database = Depends(get_db)
):
    ventas = list(db.ventas.find())
    resultado_final = []

    for v in ventas:
        venta_formateada = {
            "id": str(v["_id"]),
            "fecha": v["fecha"],
            "cantidad": v.get("cantidad", 1),
            "estado": v.get("estado", "DESCONOCIDO"),
            "motivo_cancelacion": v.get("motivo_cancelacion"),
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
