from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from database import engine, Base, get_db, SessionLocal
from models import Cliente
from schemas import ClienteCreate, ClienteResponse
from messaging import iniciar_consumidor


# Crea las tablas que todavía no existan
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Servicio de Clientes (SAGA Orquestada)",
    description="Microservicio de clientes: ejecuta comandos directos de cobro instruidos por el Orquestador",
    version="2.0.0"
)


def seed_clientes_demo():
    """Siembra los clientes de prueba para los escenarios de la SAGA si la tabla está vacía."""
    db = SessionLocal()
    try:
        count = db.query(Cliente).count()
        if count == 0:
            c1 = Cliente(id=1, nombre="Samuel L.", email="samuel@ejemplo.com", telefono="3000000000", saldo=500000.0)
            c2 = Cliente(id=2, nombre="Carlos Pobre", email="carlos@ejemplo.com", telefono="3111111111", saldo=50000.0)
            db.add_all([c1, c2])
            db.commit()
            print("[Clientes SEED] Clientes de prueba sembrados: Samuel ($500.000) y Carlos ($50.000)")
    except Exception as e:
        db.rollback()
        print(f"[Clientes SEED Error]: {e}")
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    seed_clientes_demo()
    iniciar_consumidor()


@app.get("/")
def inicio():
    return {
        "mensaje": "Servicio de Clientes funcionando en modo SAGA Orquestada",
        "rol_saga": "Participante: atiende comando 'comando.clientes.cobrar' y responde al Orquestador"
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
        saldo=cliente.saldo or 0.0
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
    return db.query(Cliente).all()


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
