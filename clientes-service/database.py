from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os


# Carga las variables del archivo .env
load_dotenv()

# Obtiene la URL de conexión desde la variable de entorno
DATABASE_URL = os.getenv("DATABASE_URL")

# Crea la conexión con PostgreSQL
engine = create_engine(DATABASE_URL)

# Crea las sesiones para trabajar con la base de datos
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Clase base para nuestros modelos
Base = declarative_base()


# Dependencia que utilizará FastAPI para acceder a la BD
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
