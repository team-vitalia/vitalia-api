
from pydantic import BaseModel, Field, ConfigDict


class DoctorCrear(BaseModel):
    usuario_id_FK: int
    especialidad_id_FK: int | None = None  # Compatibilidad
    especialidad_ids: list[int] = Field(default_factory=list)
    numero_licencia: str | None = None
    estado: str = "activo"
    costo_consulta: float | None = Field(default=None, ge=0)


class DoctorActualizarPerfil(BaseModel):
    numero_licencia: str | None = None
    costo_consulta: float | None = Field(default=None, ge=0)
    especialidad_ids: list[int] | None = None


class DoctorActualizarAdmin(BaseModel):
    numero_licencia: str | None = None
    costo_consulta: float | None = Field(default=None, ge=0)
    estado: str | None = None
    especialidad_ids: list[int] | None = None

    model_config = ConfigDict(extra="forbid")