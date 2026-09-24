from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class VentaCreate(BaseModel):
    id_cliente: int
    id_zapato: int

class VentaResponse(BaseModel):
    id: str
    id_cliente: int
    id_zapato: int
    fecha: datetime

class VentaDetalleResponse(BaseModel):
    id: str
    fecha: datetime
    cliente: Dict[str, Any]
    zapato: Dict[str, Any]
