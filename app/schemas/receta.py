from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemRecetaCrear(BaseModel):
    medicamento_id_FK: int
    dosis: str
    frecuencia: str
    duracion: str
    cantidad: int = Field(gt=0)
    instrucciones: str | None = None
    via_administracion: str | None = None
    recargas_permitidas: int | None = 0


class RecetaCrear(BaseModel):
    paciente_id_FK: int
    # Se acepta `consulta_id_FK` (consulta ya registrada) o `cita_id_FK`:
    # con la cita, el backend busca o crea la consulta del médico.
    consulta_id_FK: int | None = None
    cita_id_FK: int | None = None
    items: list[ItemRecetaCrear] = Field(min_length=1)
    # El médico confirma que revisó las interacciones graves y desea continuar.
    confirmar_interacciones: bool = False

    @model_validator(mode="after")
    def _requiere_consulta_o_cita(self):
        if self.consulta_id_FK is None and self.cita_id_FK is None:
            raise ValueError("Indica consulta_id_FK o cita_id_FK")
        return self


class RecetaResponse(BaseModel):
    id_PK: int
    paciente_id_FK: int | None
    doctor_id_FK: int | None
    consulta_id_FK: int | None
    estado: str | None
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class DisponibilidadItem(BaseModel):
    item_receta_id: int
    medicamento_id: int | None = None
    medicamento: str | None = None
    presentacion: str | None = None
    cantidad_recetada: int
    cantidad_dispensada: int
    cantidad_pendiente: int
    stock_disponible: int
    # disponible | parcial | no_disponible | dispensado
    estado: str


class ItemRecetaOut(BaseModel):
    id_PK: int
    medicamento_id_FK: int | None
    medicamento: str | None = None
    presentacion: str | None = None
    dosis: str | None
    frecuencia: str | None
    duracion: str | None
    cantidad: int | None
    cantidad_dispensada: int = 0
    instrucciones: str | None
    via_administracion: str | None


class RecetaDetalle(RecetaResponse):
    paciente: str | None = None
    doctor: str | None = None
    items: list[ItemRecetaOut] = []
    disponibilidad: list[DisponibilidadItem] = []


class RecetaCreada(RecetaDetalle):
    advertencias_interacciones: list[dict] = []
    alertas_alergias: list[dict] = []
    hay_faltantes: bool = False
    mensaje_disponibilidad: str | None = None
