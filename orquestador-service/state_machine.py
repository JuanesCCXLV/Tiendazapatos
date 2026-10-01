from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
import threading


class SagaStatus(str, Enum):
    INICIADA = "INICIADA"
    RESERVANDO_STOCK = "RESERVANDO_STOCK"
    STOCK_RESERVADO = "STOCK_RESERVADO"
    PROCESANDO_PAGO = "PROCESANDO_PAGO"
    PAGO_EXITOSO = "PAGO_EXITOSO"
    CONFIRMANDO_VENTA = "CONFIRMANDO_VENTA"
    COMPLETADA = "COMPLETADA"
    
    # Estados de Rollback Semántico (Compensación)
    COMPENSANDO_STOCK = "COMPENSANDO_STOCK"
    STOCK_COMPENSADO = "STOCK_COMPENSADO"
    CANCELANDO_VENTA = "CANCELANDO_VENTA"
    CANCELADA = "CANCELADA"


class SagaInstance:
    def __init__(self, id_saga: str, id_cliente: int, id_zapato: int, cantidad: int):
        self.id_saga = id_saga
        self.id_cliente = id_cliente
        self.id_zapato = id_zapato
        self.cantidad = cantidad
        self.estado = SagaStatus.INICIADA
        self.monto_total = 0.0
        self.precio_unitario = 0.0
        self.error: Optional[str] = None
        self.historial: List[Dict[str, Any]] = []
        self.creado_en = datetime.utcnow()
        self.actualizado_en = datetime.utcnow()

    def registrar_evento(self, accion: str, detalle: str, exito: bool = True):
        self.historial.append({
            "timestamp": datetime.utcnow().isoformat(),
            "estado": self.estado.value,
            "accion": accion,
            "detalle": detalle,
            "exito": exito
        })
        self.actualizado_en = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id_saga": self.id_saga,
            "id_cliente": self.id_cliente,
            "id_zapato": self.id_zapato,
            "cantidad": self.cantidad,
            "estado": self.estado.value,
            "precio_unitario": self.precio_unitario,
            "monto_total": self.monto_total,
            "error": self.error,
            "creado_en": self.creado_en.isoformat(),
            "actualizado_en": self.actualizado_en.isoformat(),
            "historial_pasos": self.historial
        }


class SagaStore:
    """Almacén central en memoria con candado thread-safe para rastrear la máquina de estados de cada SAGA."""
    def __init__(self):
        self._sagas: Dict[str, SagaInstance] = {}
        self._lock = threading.Lock()

    def crear_saga(self, id_saga: str, id_cliente: int, id_zapato: int, cantidad: int) -> SagaInstance:
        with self._lock:
            saga = SagaInstance(id_saga, id_cliente, id_zapato, cantidad)
            saga.registrar_evento("SAGA_INICIADA", f"Orquestador crea la transacción SAGA {id_saga}")
            self._sagas[id_saga] = saga
            return saga

    def obtener_saga(self, id_saga: str) -> Optional[SagaInstance]:
        with self._lock:
            return self._sagas.get(id_saga)

    def listar_sagas(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._sagas.values()]


# Instancia singleton del almacén de sagas
saga_store = SagaStore()
