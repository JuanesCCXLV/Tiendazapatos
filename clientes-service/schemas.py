from pydantic import BaseModel, EmailStr
from typing import Optional


class ClienteCreate(BaseModel):
    nombre: str
    email: EmailStr
    telefono: str
    saldo: Optional[float] = 0.0


class ClienteResponse(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    telefono: str
    saldo: float

    class Config:
        from_attributes = True
