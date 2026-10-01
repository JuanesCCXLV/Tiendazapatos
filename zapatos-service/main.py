from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import engine, Base, get_db, SessionLocal
from models import Zapato
from schemas import ZapatoCreate, ZapatoResponse
from messaging import iniciar_consumidor


# Crea las tablas que todavía no existan
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Servicio de Zapatos (SAGA Orquestada)",
    description="Microservicio de inventario de calzado: ejecuta comandos directos de reserva y liberación (compensación)",
    version="2.0.0"
)


def seed_zapatos_demo():
    """Siembra zapatos de prueba si la base de datos está vacía."""
    db = SessionLocal()
    try:
        count = db.query(Zapato).count()
        if count == 0:
            z1 = Zapato(
                id_zapato=1,
                marca="Nike Air Force",
                talla=40,
                color="Blanco",
                precio=250000.0,
                cantidad_disponible=10
            )
            db.add(z1)
            db.commit()
            print("[Zapatos SEED] Zapato de prueba sembrado: Nike Air Force (Stock: 10, Precio: $250.000)")
    except Exception as e:
        db.rollback()
        print(f"[Zapatos SEED Error]: {e}")
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    seed_zapatos_demo()
    iniciar_consumidor()


@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Zapatos funcionando en modo SAGA Orquestada",
        "rol_saga": "Participante: atiende comandos 'comando.zapatos.reservar' y 'comando.zapatos.liberar'"
    }


@app.post("/zapatos", response_model=ZapatoResponse)
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
    return db.query(Zapato).all()
