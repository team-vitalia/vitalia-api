from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.registro_auditoria import RegistroAuditoria


class AuditoriaService:
    def __init__(self, db: Session):
        self.db = db

    def listar(
        self,
        usuario_id: int | None = None,
        nombre_tabla: str | None = None,
        accion: str | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        stmt = select(RegistroAuditoria)

        if usuario_id:
            stmt = stmt.where(RegistroAuditoria.usuario_id_FK == usuario_id)
        if nombre_tabla:
            stmt = stmt.where(RegistroAuditoria.nombre_tabla == nombre_tabla)
        if accion:
            stmt = stmt.where(RegistroAuditoria.accion == accion)
        if desde:
            stmt = stmt.where(RegistroAuditoria.marca_tiempo >= desde)
        if hasta:
            stmt = stmt.where(RegistroAuditoria.marca_tiempo <= hasta)

        total = self.db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        items = self.db.scalars(
            stmt.order_by(RegistroAuditoria.marca_tiempo.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        return items, total

    def obtener(self, registro_id: int) -> RegistroAuditoria | None:
        return self.db.get(RegistroAuditoria, registro_id)
