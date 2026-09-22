from sqlalchemy import Column, Integer, String, Numeric
from database import Base


class Zapato(Base):
    __tablename__ = "zapatos"

    id_zapato = Column(Integer, primary_key=True, index=True, autoincrement=True)
    marca = Column(String(100), nullable=False)
    talla = Column(Integer, nullable=False)
    color = Column(String(50), nullable=False)
    precio = Column(Numeric (10,2), nullable=False)
    cantidad_disponible = Column(Integer)