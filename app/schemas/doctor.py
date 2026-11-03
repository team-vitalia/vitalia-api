
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.core.validaciones import validar_rfc


def _normalizar_rfc_opcional(v: str | None) -> str | None:
    v = (v or "").strip()
    return validar_rfc(v) if v else None


class DoctorCrear(BaseModel):
    usuario_id_FK: int
    especialidad_id_FK: int | None = None  # Compatibilidad
    especialidad_ids: list[int] = Field(default_factory=list)
    numero_licencia: str | None = None
    rfc: str | None = None
    estado: str = "activo"
    costo_consulta: float | None = Field(default=None, ge=0)

    @field_validator("rfc")
    @classmethod
    def _validar_rfc(cls, v: str | None) -> str | None:
        return _normalizar_rfc_opcional(v)


class DoctorActualizarPerfil(BaseModel):
    numero_licencia: str | None = None
    costo_consulta: float | None = Field(default=None, ge=0)
    especialidad_ids: list[int] | None = None


class DoctorActualizarAdmin(BaseModel):
    numero_licencia: str | None = None
    rfc: str | None = None
    costo_consulta: float | None = Field(default=None, ge=0)
    estado: str | None = None
    especialidad_ids: list[int] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("rfc")
    @classmethod
    def _validar_rfc(cls, v: str | None) -> str | None:
        return _normalizar_rfc_opcional(v)
