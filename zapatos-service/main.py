from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Zapato
from schemas import ZapatoCreate, ZapatoResponse


# Crea las tablas que todavía no existan
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Servicio de Zapatos",
    description="Microservicio encargado de administrar los zapatos",
    version="1.0.0"
)


@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Zapatos funcionando"
    }


@app.post("/zapatos", response_model= ZapatoResponse)
def crear_zapato(
    zapato: ZapatoCreate,
    db: Session = Depends(get_db)
):
    nuevo_zapato = Zapato(
        marca=zapato.marca,
        talla=zapato.talla,
        color=zapato.color,
        precio=zapato.precio,
        cantidad_disponible=zapato.cantidad_disponible
    )

    db.add(nuevo_zapato)
    db.commit()
    db.refresh(nuevo_zapato)

    return nuevo_zapato


@app.get("/zapatos/{id_zapato}", response_model=ZapatoResponse)
def obtener_zapato(
    id_zapato: int,
    db: Session = Depends(get_db)
):
    zapato = db.query(Zapato).filter(
        Zapato.id_zapato == id_zapato
    ).first()

    if zapato is None:
        raise HTTPException(
            status_code=404,
            detail="Zapato no encontrado"
        )

    return zapato


@app.get("/zapatos", response_model=list[ZapatoResponse])
def obtener_zapatos(
    db: Session = Depends(get_db)
):
    zapatos = db.query(Zapato).all()

    return zapatos
