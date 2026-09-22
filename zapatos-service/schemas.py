from pydantic import BaseModel


class ZapatoCreate(BaseModel):
    marca: str
    talla: int
    color: str
    precio: float
    cantidad_disponible: int | None = None


class ZapatoResponse(BaseModel):
    id_zapato: int
    marca: str
    talla: int
    color: str
    precio: float
    cantidad_disponible: int | None = None

    class Config:
        from_attributes = True
