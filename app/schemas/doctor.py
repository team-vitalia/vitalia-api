from pydantic import BaseModel


class DoctorCrear(BaseModel):
    usuario_id_FK: int
    especialidad_id_FK: int | None = None
    numero_licencia: str | None = None
    estado: str = "activo"
    costo_consulta: float | None = None