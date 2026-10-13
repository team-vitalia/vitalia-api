from pydantic import BaseModel
from typing import List, Optional
from datetime import date

# 1. Schema para la respuesta de Medicamentos (Faltaba este)
class MedicamentoResponse(BaseModel):
    id_PK: int
    nombre: str
    principio_activo: Optional[str] = None
    presentacion: Optional[str] = None
    requiere_receta: Optional[bool] = None
    descripcion: Optional[str] = None
    codigo_barras: Optional[str] = None
    categoria: Optional[str] = None

    class Config:
        from_attributes = True

# 2. Schemas para Inventario
class InventarioBase(BaseModel):
    medicamento_id_FK: int
    numero_lote: Optional[str] = None
    stock_actual: int
    ubicacion: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    precio_venta: Optional[float] = None
    proveedor_id_FK: Optional[int] = None
    fecha_recepcion: Optional[date] = None

class InventarioCreate(InventarioBase):
    pass

class InventarioResponse(InventarioBase):
    id_PK: int

    class Config:
        from_attributes = True

# 3. Schemas para Evaluación de Interacciones
class EvaluarInteraccionRequest(BaseModel):
    medicamentos_ids: List[int]

class InteraccionResultado(BaseModel):
    medicamento_1: str
    medicamento_2: str
    severidad: str
    descripcion: str
    nivel_evidencia: Optional[str] = None
    accion_requerida: Optional[str] = None

class EvaluarInteraccionResponse(BaseModel):
    tiene_interaccion: bool
    detalles: List[InteraccionResultado]