from sqlalchemy import Column, Integer, String, Numeric
from database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    telefono = Column(String(20))
    saldo = Column(Numeric(10, 2), default=500000.0, nullable=False)

