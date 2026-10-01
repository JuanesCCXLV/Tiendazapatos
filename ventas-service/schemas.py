from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class VentaCreate(BaseModel):
    id_cliente: int
    id_zapato: int
    cantidad: Optional[int] = 1

class VentaResponse(BaseModel):
    id: str
    id_cliente: int
    id_zapato: int
    cantidad: int
    estado: str
    motivo_cancelacion: Optional[str] = None
    fecha: datetime

class VentaDetalleResponse(BaseModel):
    id: str
    fecha: datetime
    cantidad: int
    estado: str
    motivo_cancelacion: Optional[str] = None
    cliente: Dict[str, Any]
    zapato: Dict[str, Any]

