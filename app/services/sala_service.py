from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sala import Sala
from app.models.equipamiento_sala import EquipamientoSala
from app.models.usuario import Usuario
from app.schemas.sala import SalaCreate, SalaUpdate
from app.schemas.equipamiento import EquipamientoCreate
from app.utils.auditoria import (
    registrar_auditoria,
    ip_desde_request,
    serializar,
)


class SalaService:
    def __init__(self, db: Session):
        self.db = db

    # ---------- Consultas ----------
    def listar(
        self,
        estado: str | None = None,
        piso: str | None = None,
        tipo: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        stmt = select(Sala)
        if estado:
            stmt = stmt.where(Sala.estado == estado)
        if piso:
            stmt = stmt.where(Sala.piso == piso)
        if tipo:
            stmt = stmt.where(Sala.tipo == tipo)

        total = self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0
        items = self.db.scalars(
            stmt.order_by(Sala.nombre)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return items, total

    def obtener(self, sala_id: int) -> Sala | None:
        return self.db.get(Sala, sala_id)

    # ---------- CRUD ----------
    def crear(
        self,
        payload: SalaCreate,
        usuario: Usuario,
        request: Request,
    ) -> Sala:
        sala = Sala(**payload.model_dump())
        self.db.add(sala)
        self.db.flush()  # obtiene id_PK

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="CREATE",
            tabla="salas",
            id_registro=sala.id_PK,
            antiguos=None,
            nuevos=serializar(payload.model_dump(mode="json")),
            ip=ip_desde_request(request),
            descripcion=f"Creación de sala {sala.nombre}",
        )

        self.db.commit()
        self.db.refresh(sala)
        return sala

    def actualizar(
        self,
        sala_id: int,
        payload: SalaUpdate,
        usuario: Usuario,
        request: Request,
    ) -> Sala | None:
        sala = self.db.get(Sala, sala_id)
        if not sala:
            return None

        antes = serializar(
            {c.name: getattr(sala, c.name) for c in Sala.__table__.columns}
        )

        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(sala, k, v)

        self.db.flush()

        despues = serializar(
            {c.name: getattr(sala, c.name) for c in Sala.__table__.columns}
        )

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="UPDATE",
            tabla="salas",
            id_registro=sala.id_PK,
            antiguos=antes,
            nuevos=despues,
            ip=ip_desde_request(request),
            descripcion=f"Actualización de sala {sala.nombre}",
        )

        self.db.commit()
        self.db.refresh(sala)
        return sala

    def cambiar_estado(
        self,
        sala_id: int,
        nuevo_estado: str,
        usuario: Usuario,
        request: Request,
    ) -> Sala | None:
        sala = self.db.get(Sala, sala_id)
        if not sala:
            return None

        anterior = sala.estado
        sala.estado = nuevo_estado
        self.db.flush()

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="UPDATE_ESTADO",
            tabla="salas",
            id_registro=sala.id_PK,
            antiguos={"estado": anterior},
            nuevos={"estado": nuevo_estado},
            ip=ip_desde_request(request),
            descripcion=f"Cambio de estado: {anterior} → {nuevo_estado}",
        )

        self.db.commit()
        self.db.refresh(sala)
        return sala

    def eliminar(
        self,
        sala_id: int,
        usuario: Usuario,
        request: Request,
    ) -> bool:
        sala = self.db.get(Sala, sala_id)
        if not sala:
            return False

        antes = serializar(
            {c.name: getattr(sala, c.name) for c in Sala.__table__.columns}
        )
        nombre = sala.nombre

        # El equipamiento depende de la sala (FK): se elimina primero.
        equipos_eliminados = (
            self.db.query(EquipamientoSala)
            .filter(EquipamientoSala.sala_id_FK == sala_id)
            .delete(synchronize_session=False)
        )

        self.db.delete(sala)

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="DELETE",
            tabla="salas",
            id_registro=sala_id,
            antiguos=antes,
            nuevos=None,
            ip=ip_desde_request(request),
            descripcion=(
                f"Eliminación de sala {nombre}"
                f" ({equipos_eliminados} equipos eliminados)"
            ),
        )

        self.db.commit()
        return True

    # ---------- Equipamiento anidado ----------
    def listar_equipos(self, sala_id: int) -> list[EquipamientoSala]:
        return self.db.scalars(
            select(EquipamientoSala).where(
                EquipamientoSala.sala_id_FK == sala_id
            )
        ).all()

    def agregar_equipo(
        self,
        sala_id: int,
        payload: EquipamientoCreate,
        usuario: Usuario,
        request: Request,
    ) -> EquipamientoSala | None:
        sala = self.db.get(Sala, sala_id)
        if not sala:
            return None

        equipo = EquipamientoSala(
            sala_id_FK=sala_id,
            **payload.model_dump(),
        )
        self.db.add(equipo)
        self.db.flush()

        registrar_auditoria(
            db=self.db,
            usuario=usuario,
            accion="CREATE",
            tabla="equipamiento_sala",
            id_registro=equipo.id_PK,
            antiguos=None,
            nuevos=serializar(payload.model_dump(mode="json")),
            ip=ip_desde_request(request),
            descripcion=f"Equipo {equipo.nombre_equipo} agregado a sala {sala.nombre}",
        )

        self.db.commit()
        self.db.refresh(equipo)
        return equipo
