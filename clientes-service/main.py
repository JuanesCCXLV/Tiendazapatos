from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx 

from database import engine, Base, get_db
from models import Cliente
from schemas import ClienteCreate, ClienteResponse, RecargarSaldo
from messaging import iniciar_consumidor


# Crea las tablas que todavía no existan y asegura columna saldo
Base.metadata.create_all(bind=engine)
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS saldo NUMERIC(10, 2) DEFAULT 500000.0;"))
        conn.commit()
except Exception as e:
    print(f"Nota al verificar columna saldo: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicia el consumidor de eventos SAGA en segundo plano
    iniciar_consumidor()
    yield


app = FastAPI(
    title="Servicio de Clientes",
    description="Microservicio encargado de administrar los clientes de la tienda de zapatos",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Clientes funcionando"
    }


@app.post("/clientes", response_model=ClienteResponse)
def crear_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db)
):
    nuevo_cliente = Cliente(
        nombre=cliente.nombre,
        email=cliente.email,
        telefono=cliente.telefono,
        saldo=cliente.saldo if cliente.saldo is not None else 500000.0
    )

    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)

    return nuevo_cliente


@app.post("/clientes/{cliente_id}/recargar", response_model=ClienteResponse)
def recargar_saldo(
    cliente_id: int,
    datos: RecargarSaldo,
    db: Session = Depends(get_db)
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente is None:
        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado"
        )
    cliente.saldo = float(cliente.saldo) + datos.monto
    db.commit()
    db.refresh(cliente)
    return cliente



@app.get("/clientes/{cliente_id}", response_model=ClienteResponse)
def obtener_cliente(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id
    ).first()

    if cliente is None:
        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado"
        )

    return cliente


@app.get("/clientes", response_model=list[ClienteResponse])
def obtener_clientes(
    db: Session = Depends(get_db)
):
    clientes = db.query(Cliente).all()

    return clientes
    
@app.get("/clientes/{cliente_id}/zapato/{id_zapato}")
def obtener_cliente_y_zapato(
    cliente_id: int,
    id_zapato: int,
    db: Session = Depends(get_db)
):
    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id
    ).first()

    if cliente is None:
        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado"
        )

    try:
        respuesta = httpx.get(
            f"http://zapatos-service:8002/zapatos/{id_zapato}",
            timeout=5.0
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="No se pudo conectar con el servicio de zapatos"
        )

    if respuesta.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Zapato no encontrado"
        )

    if respuesta.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="El servicio de zapatos respondió con un error"
        )

    return {
        "cliente": cliente,
        "zapato": respuesta.json()
    }
