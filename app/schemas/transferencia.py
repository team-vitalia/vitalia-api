from datetime import datetime

from pydantic import BaseModel


class TransferenciaCrear(BaseModel):
    paciente_id_FK: int
    doctor_destino_id_FK: int
    # Solo necesario cuando lo registra administración/coordinación
    doctor_origen_id_FK: int | None = None
    motivo: str | None = None


class TransferenciaOut(BaseModel):
    id_PK: int
    paciente_id_FK: int
    paciente: str | None = None
    doctor_origen_id_FK: int
    doctor_origen: str | None = None
    doctor_destino_id_FK: int
    doctor_destino: str | None = None
    motivo: str | None = None
    citas_reasignadas: int
    citas_con_conflicto: list[dict] = []
    creado_en: datetime
