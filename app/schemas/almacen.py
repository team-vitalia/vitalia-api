from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# 1. Schema para la respuesta de Medicamentos
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
    stock_actual: int = Field(ge=0)
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


# 4. Movimientos de inventario (entradas, salidas, mermas y ajustes)
class MovimientoManualRequest(BaseModel):
    # entrada | salida | merma | ajuste (ajuste fija el stock exacto)
    tipo: str
    cantidad: int = Field(ge=0)
    motivo: Optional[str] = None


class MovimientoOut(BaseModel):
    id_PK: int
    inventario_id_FK: Optional[int] = None
    medicamento: Optional[str] = None
    numero_lote: Optional[str] = None
    tipo: Optional[str] = None
    cantidad: Optional[int] = None
    stock_anterior: Optional[int] = None
    stock_nuevo: Optional[int] = None
    usuario_id_FK: Optional[int] = None
    id_referencia: Optional[int] = None
    creado_en: Optional[datetime] = None


# 5. Caducidades y resumen
class CaducidadOut(BaseModel):
    inventario_id: int
    medicamento_id: int
    medicamento: Optional[str] = None
    numero_lote: Optional[str] = None
    stock_actual: int
    ubicacion: Optional[str] = None
    fecha_vencimiento: date
    dias_restantes: int
    # vencido | por_vencer
    estado: str


class ResumenAlmacen(BaseModel):
    total_medicamentos: int
    total_lotes: int
    unidades_vigentes: int
    lotes_vencidos: int
    lotes_por_vencer: int
    medicamentos_stock_bajo: int
    recetas_pendientes: int
    umbral_stock_bajo: int
    dias_alerta_caducidad: int


# 6. Dispensación
class ItemDispensar(BaseModel):
    item_receta_id: int
    cantidad: int = Field(gt=0)


class DispensarRequest(BaseModel):
    receta_id: int
    # Si se omite, se dispensa todo lo pendiente que haya en existencia.
    items: Optional[List[ItemDispensar]] = None
    notas: Optional[str] = None


class DispensacionOut(BaseModel):
    id_PK: Optional[int] = None
    item_receta_id: int
    medicamento: Optional[str] = None
    inventario_id: int
    numero_lote: Optional[str] = None
    cantidad: int


class DispensarResponse(BaseModel):
    receta_id: int
    estado_receta: Optional[str] = None
    completa: bool
    dispensaciones: List[DispensacionOut]
    faltantes: List[dict] = []


class DispensacionHistorialOut(BaseModel):
    id_PK: int
    receta_id: int
    paciente: Optional[str] = None
    medicamento: Optional[str] = None
    numero_lote: Optional[str] = None
    cantidad: int
    usuario_id_FK: Optional[int] = None
    creado_en: Optional[datetime] = None


# 7. Presentaciones de medicamento
class PresentacionCreate(BaseModel):
    concentracion: Optional[str] = Field(default=None, max_length=100)
    forma_farmaceutica: Optional[str] = Field(default=None, max_length=100)
    contenido: Optional[str] = Field(default=None, max_length=100)


class PresentacionOut(PresentacionCreate):
    id_PK: int
    medicamento_id_FK: int
    esta_activo: bool = True

    model_config = ConfigDict(from_attributes=True)
