from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.registro_auditoria import RegistroAuditoria
from app.models.usuario import Usuario
from app.services.auditoria_explicador import AREAS, CODIGO_A_TIPO, TIPOS_ACCION, explicar_lote

_ACCIONES_SALA_IA = TIPOS_ACCION["sala"]["codigos"] + TIPOS_ACCION["ia"]["codigos"]


class AuditoriaService:
    def __init__(self, db: Session, clinica_id: int | None = None):
        self.db = db
        self.clinica_id = clinica_id

    def _base(self, stmt):
        # Todas las consultas se limitan a la clínica del usuario (antes `obtener` no lo hacía)
        if self.clinica_id is not None:
            stmt = stmt.join(Usuario, RegistroAuditoria.usuario_id_FK == Usuario.id_PK).where(
                Usuario.clinica_id_FK == self.clinica_id
            )
        return stmt

    def _filtros(
        self, stmt, usuario_id=None, nombre_tabla=None, accion=None, area=None, tipo_accion=None,
        buscar=None, desde=None, hasta=None,
    ):
        if usuario_id:
            stmt = stmt.where(RegistroAuditoria.usuario_id_FK == usuario_id)
        if nombre_tabla:
            stmt = stmt.where(RegistroAuditoria.nombre_tabla == nombre_tabla)
        if accion:
            stmt = stmt.where(RegistroAuditoria.accion == accion)
        if tipo_accion in TIPOS_ACCION:
            stmt = stmt.where(RegistroAuditoria.accion.in_(TIPOS_ACCION[tipo_accion]["codigos"]))
        if area == "ia":
            stmt = stmt.where(RegistroAuditoria.accion.in_(TIPOS_ACCION["ia"]["codigos"]))
        elif area in AREAS:
            cond = and_(
                RegistroAuditoria.nombre_tabla.in_(AREAS[area]["tablas"]),
                RegistroAuditoria.accion.notin_(_ACCIONES_SALA_IA),
            )
            if area == "salas":  # reservas de sala hechas desde citas también son «uso de salas»
                cond = or_(cond, RegistroAuditoria.accion.in_(TIPOS_ACCION["sala"]["codigos"]))
            stmt = stmt.where(cond)
        if buscar:
            like = f"%{buscar.strip()}%"
            condiciones = [RegistroAuditoria.descripcion.ilike(like), RegistroAuditoria.nombre_tabla.ilike(like)]
            if self.clinica_id is not None:  # `Usuario` ya está unido en _base(): se busca también por nombre de la persona
                condiciones += [Usuario.nombre.ilike(like), Usuario.apellido_paterno.ilike(like)]
            stmt = stmt.where(or_(*condiciones))
        if desde:
            stmt = stmt.where(RegistroAuditoria.marca_tiempo >= desde)
        if hasta:
            stmt = stmt.where(RegistroAuditoria.marca_tiempo <= hasta)
        return stmt

    def listar(self, page: int = 1, page_size: int = 20, **filtros):
        stmt = self._filtros(self._base(select(RegistroAuditoria)), **filtros)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.order_by(RegistroAuditoria.marca_tiempo.desc(), RegistroAuditoria.id_PK.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return items, total

    def obtener(self, registro_id: int) -> RegistroAuditoria | None:
        stmt = self._base(select(RegistroAuditoria)).where(RegistroAuditoria.id_PK == registro_id)
        return self.db.scalars(stmt).first()

    def explicar(self, registros: list[RegistroAuditoria]) -> list[dict]:
        return explicar_lote(self.db, registros)

    def resumen(self, desde: datetime | None = None, hasta: datetime | None = None) -> dict:
        """Conteo de actividad por área y por tipo de acción (por defecto, últimos 30 días)."""
        hasta = hasta or datetime.now()
        desde = desde or (hasta - timedelta(days=30))
        stmt = self._filtros(
            self._base(select(RegistroAuditoria.nombre_tabla, RegistroAuditoria.accion, func.count())),
            desde=desde, hasta=hasta,
        ).group_by(RegistroAuditoria.nombre_tabla, RegistroAuditoria.accion)

        por_area: dict[str, int] = {}
        por_tipo: dict[str, int] = {}
        total = 0
        for tabla, accion, n in self.db.execute(stmt).all():
            tipo = CODIGO_A_TIPO.get(accion or "", "modificar")
            area = "salas" if tipo == "sala" else "ia" if tipo == "ia" else next(
                (k for k, v in AREAS.items() if tabla in v["tablas"]), "otros"
            )
            por_area[area] = por_area.get(area, 0) + n
            por_tipo[tipo] = por_tipo.get(tipo, 0) + n
            total += n
        return {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "total": total, "por_area": por_area, "por_tipo": por_tipo}
