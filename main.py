from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Cliente
from schemas import ClienteCreate, ClienteResponse


# Crea las tablas que todavía no existan
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Servicio de Clientes",
    description="Microservicio encargado de administrar los clientes de la tienda de zapatos",
    version="1.0.0"
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
        telefono=cliente.telefono
    )

    db.add(nuevo_cliente)
    db.commit()
    db.refresh(nuevo_cliente)

    return nuevo_cliente


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
