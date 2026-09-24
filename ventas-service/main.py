from fastapi import FastAPI, Depends, HTTPException
from pymongo.database import Database
import httpx
from datetime import datetime

from database import get_db
from schemas import VentaCreate, VentaResponse, VentaDetalleResponse

app = FastAPI(
    title="Servicio de Ventas",
    description="Microservicio encargado de administrar las ventas de la tienda",
    version="1.0.0"
)

@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Ventas funcionando"
    }

@app.post("/ventas", response_model=VentaResponse)
def crear_venta(
    venta: VentaCreate,
    db: Database = Depends(get_db)
):
    try:
        res_cliente = httpx.get(
            f"http://clientes-service:8001/clientes/{venta.id_cliente}",
            timeout=5.0
        )
        if res_cliente.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Cliente no valido o no existe"
            )

        res_zapato = httpx.get(
            f"http://zapatos-service:8002/zapatos/{venta.id_zapato}",
            timeout=5.0
        )
        if res_zapato.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Zapato no valido o no existe"
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Error de conexion con los otros servicios"
        )

    nueva_venta = {
        "id_cliente": venta.id_cliente,
        "id_zapato": venta.id_zapato,
        "fecha": datetime.utcnow()
    }

    resultado = db.ventas.insert_one(nueva_venta)
    
    return {
        "id": str(resultado.inserted_id),
        "id_cliente": nueva_venta["id_cliente"],
        "id_zapato": nueva_venta["id_zapato"],
        "fecha": nueva_venta["fecha"]
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
            "fecha": v["fecha"],
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
