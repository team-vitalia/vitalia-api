from fastapi import Request
from sqlalchemy.orm import Session

from app.models.equipamiento_sala import EquipamientoSala
from app.models.usuario import Usuario
from app.schemas.equipamiento import EquipamientoUpdate
from app.utils.auditoria import (
    registrar_auditoria,
    ip_desde_request,
    serializar,
)


class EquipamientoService:
    def __init__(self, db: Session):
        self.db = db

    def obtener(self, equipo_id: int) -> EquipamientoSala | None:
        return self.db.get(EquipamientoSala, equipo_id)

    def actualizar(
        self,
        equipo_id: int,
        payload: EquipamientoUpdate,
        usuario: Usuario,
        request: Request,
    ) -> EquipamientoSala | None:
        equipo = self.db.get(EquipamientoSala, equipo_id)
        if not equipo:
            return None

        antes = serializar(
            {c.name: getattr(equipo, c.name)
             for c in EquipamientoSala.__table__.columns}
        )

        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(equipo, k, v)

        self.db.flush()

        despues = serializar(
            {c.name: getattr(equipo, c.name)
             for c in EquipamientoSala.__table__.columns}
        )

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="UPDATE",
            tabla="equipamiento_sala",
            id_registro=equipo.id_PK,
            antiguos=antes,
            nuevos=despues,
            ip=ip_desde_request(request),
            descripcion=f"Actualización de equipo {equipo.nombre_equipo}",
        )

        self.db.commit()
        self.db.refresh(equipo)
        return equipo

    def eliminar(
        self,
        equipo_id: int,
        usuario: Usuario,
        request: Request,
    ) -> bool:
        equipo = self.db.get(EquipamientoSala, equipo_id)
        if not equipo:
            return False

        antes = serializar(
            {c.name: getattr(equipo, c.name)
             for c in EquipamientoSala.__table__.columns}
        )
        nombre = equipo.nombre_equipo

        self.db.delete(equipo)

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="DELETE",
            tabla="equipamiento_sala",
            id_registro=equipo_id,
            antiguos=antes,
            nuevos=None,
            ip=ip_desde_request(request),
            descripcion=f"Eliminación de equipo {nombre}",
        )

        self.db.commit()
        return True
