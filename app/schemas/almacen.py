from datetime import date, datetime
from typing import List, Literal, Optional

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
    tipo_articulo: str = "medicamento"
    unidad_medida: Optional[str] = None
    stock_minimo: int = 0

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
    tipo_articulo: str = "medicamento"
    unidad_medida: Optional[str] = None
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


# 8. Consumo interno de insumos / material
class ConsumoRequest(BaseModel):
    medicamento_id: int
    cantidad: int = Field(gt=0)
    # Área o motivo (consultorio, curaciones, esterilización...). Queda en la auditoría.
    area: Optional[str] = Field(default=None, max_length=100)
    motivo: Optional[str] = Field(default=None, max_length=200)


class ConsumoResponse(BaseModel):
    medicamento: Optional[str] = None
    tipo_articulo: str = "medicamento"
    cantidad: int
    lotes: List[dict]
    stock_restante: int


# 9. Entrada de mercancía por código de barras
class LoteResumen(BaseModel):
    inventario_id: int
    numero_lote: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    stock_actual: int = 0
    ubicacion: Optional[str] = None


class DatosGS1(BaseModel):
    """Lote y caducidad leídos de un código GS1 (DataMatrix / GS1-128), si los traía."""
    numero_lote: Optional[str] = None
    fecha_vencimiento: Optional[date] = None


class ProductoCodigoOut(BaseModel):
    medicamento_id: int
    nombre: str
    presentacion: Optional[str] = None
    principio_activo: Optional[str] = None
    codigo_barras: Optional[str] = None
    tipo_articulo: str = "medicamento"
    unidad_medida: Optional[str] = None
    stock_actual: int = 0
    stock_minimo: int = 0
    # Los medicamentos exigen lote y caducidad; insumos y equipo, no.
    requiere_lote: bool = True
    ubicacion_sugerida: Optional[str] = None
    lotes_recientes: List[LoteResumen] = []
    datos_gs1: Optional[DatosGS1] = None


class EntradaCodigoBarrasRequest(BaseModel):
    codigo_barras: str = Field(min_length=1, max_length=200)
    cantidad: int = Field(gt=0, le=100000)
    numero_lote: Optional[str] = Field(default=None, max_length=100)
    fecha_vencimiento: Optional[date] = None
    ubicacion: Optional[str] = Field(default=None, max_length=150)


class EntradaCodigoBarrasResponse(BaseModel):
    medicamento_id: int
    medicamento: str
    presentacion: Optional[str] = None
    unidad_medida: Optional[str] = None
    codigo_barras: Optional[str] = None
    inventario_id: int
    numero_lote: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    cantidad_agregada: int
    stock_lote_anterior: int
    stock_lote_nuevo: int
    stock_total: int
    # True si se creó un lote nuevo; False si se sumó a un lote existente (mismo lote y caducidad)
    lote_nuevo: bool
    movimiento_id: Optional[int] = None
    mensaje: str


class EvaluarInteraccionIARequest(BaseModel):
    medicamentos_ids: List[int] = Field(min_length=2, max_length=20)


class InteraccionIAPrediccion(BaseModel):
    medicamento_1: str
    medicamento_2: str
    severidad: Literal["leve", "moderada", "grave", "incierta"]
    descripcion: str = Field(min_length=1, max_length=1000)


class EvaluacionInteraccionesIA(BaseModel):
    detalles: List[InteraccionIAPrediccion] = Field(max_length=50)
    observaciones: str = Field(min_length=1, max_length=1000)


class EvaluarInteraccionIAResponse(BaseModel):
    tiene_interaccion: bool
    detalles: List[InteraccionResultado]
    observaciones: str
    fuente: Literal["Groq IA"] = "Groq IA"
    aviso: str = (
        "Análisis generado por IA como apoyo informativo. No descarta riesgos ni "
        "sustituye fuentes farmacológicas confiables ni el criterio de un profesional."
    )
