from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cita import Cita
from app.models.cola import Cola
from app.models.doctor import Doctor
from app.models.evento_calendario import EventoCalendario
from app.models.inventario import Inventario
from app.models.medicamento import Medicamento
from app.models.receta import Receta
from app.models.sala import Sala
from app.models.usuario import Usuario

ESTADOS_CITA_INACTIVOS = ("cancelada",)


def _rango_datetime(desde: date | None, hasta: date | None):
    """Convierte un rango de fechas en [inicio, fin) de datetimes (fin exclusivo)."""
    ini = datetime.combine(desde, time.min) if desde else None
    fin = datetime.combine(hasta + timedelta(days=1), time.min) if hasta else None
    return ini, fin


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


class ReporteService:
    """Reportes de gestión (C2) calculados con las tablas reales del sistema."""

    def __init__(self, db: Session):
        self.db = db

    def _nombres_doctores(self) -> dict[int, str]:
        filas = self.db.execute(
            select(Doctor.id_PK, Usuario.nombre).join(
                Usuario, Usuario.id_PK == Doctor.usuario_id_FK, isouter=True
            )
        ).all()
        return {doc_id: nombre for doc_id, nombre in filas}

    # ---------- Ocupación de salas ----------
    def ocupacion_salas(self, desde: date | None, hasta: date | None):
        salas = self.db.scalars(select(Sala).order_by(Sala.nombre)).all()

        por_estado: dict[str, int] = defaultdict(int)
        for s in salas:
            por_estado[s.estado or "sin_estado"] += 1

        # Las citas no tienen sala propia: se asocian a una sala cuando el evento
        # de calendario de la cita tiene como ubicación el nombre de la sala.
        stmt = (
            select(EventoCalendario.ubicacion, Cita.hora_inicio, Cita.hora_fin)
            .join(Cita, Cita.evento_calendario_id == EventoCalendario.id_PK)
            .where(EventoCalendario.ubicacion.is_not(None))
            .where(Cita.estado.notin_(ESTADOS_CITA_INACTIVOS) | Cita.estado.is_(None))
        )
        if desde:
            stmt = stmt.where(Cita.fecha >= desde)
        if hasta:
            stmt = stmt.where(Cita.fecha <= hasta)

        uso: dict[str, dict] = defaultdict(lambda: {"citas": 0, "minutos": 0})
        for ubicacion, h_ini, h_fin in self.db.execute(stmt).all():
            u = uso[ubicacion.strip().lower()]
            u["citas"] += 1
            if h_ini and h_fin:
                minutos = (
                    datetime.combine(date.min, h_fin)
                    - datetime.combine(date.min, h_ini)
                ).total_seconds() / 60
                u["minutos"] += max(int(minutos), 0)

        detalle = []
        for s in salas:
            u = uso.get((s.nombre or "").strip().lower(), {"citas": 0, "minutos": 0})
            detalle.append(
                {
                    "sala_id": s.id_PK,
                    "nombre": s.nombre,
                    "tipo": s.tipo,
                    "piso": s.piso,
                    "estado": s.estado,
                    "capacidad": s.capacidad,
                    "total_citas": u["citas"],
                    "horas_ocupadas": round(u["minutos"] / 60, 2),
                }
            )

        return {
            "desde": _iso(desde),
            "hasta": _iso(hasta),
            "total_salas": len(salas),
            "por_estado": dict(por_estado),
            "detalle": detalle,
        }

    # ---------- Citas por doctor ----------
    def citas_por_doctor(self, desde: date | None, hasta: date | None):
        stmt = select(Cita.doctor_id_FK, Cita.estado, func.count()).group_by(
            Cita.doctor_id_FK, Cita.estado
        )
        if desde:
            stmt = stmt.where(Cita.fecha >= desde)
        if hasta:
            stmt = stmt.where(Cita.fecha <= hasta)

        nombres = self._nombres_doctores()
        agrupado: dict[int | None, dict] = {}
        for doctor_id, estado, cantidad in self.db.execute(stmt).all():
            d = agrupado.setdefault(
                doctor_id,
                {
                    "doctor_id": doctor_id,
                    "doctor": nombres.get(doctor_id),
                    "total": 0,
                    "por_estado": {},
                },
            )
            d["total"] += cantidad
            d["por_estado"][estado or "sin_estado"] = cantidad

        detalle = sorted(agrupado.values(), key=lambda x: x["total"], reverse=True)
        return {
            "desde": _iso(desde),
            "hasta": _iso(hasta),
            "total_citas": sum(d["total"] for d in detalle),
            "detalle": detalle,
        }

    # ---------- Tiempos de espera ----------
    def tiempos_espera(self, desde: date | None, hasta: date | None):
        ini, fin = _rango_datetime(desde, hasta)
        stmt = select(Cola.doctor_id_FK, Cola.hora_registro, Cola.hora_llamado).where(
            Cola.hora_registro.is_not(None), Cola.hora_llamado.is_not(None)
        )
        if ini:
            stmt = stmt.where(Cola.hora_registro >= ini)
        if fin:
            stmt = stmt.where(Cola.hora_registro < fin)

        nombres = self._nombres_doctores()
        espera_por_doctor: dict[int | None, list[float]] = defaultdict(list)
        todas: list[float] = []
        for doctor_id, registro, llamado in self.db.execute(stmt).all():
            minutos = (llamado - registro).total_seconds() / 60
            if minutos < 0:
                continue
            espera_por_doctor[doctor_id].append(minutos)
            todas.append(minutos)

        detalle = [
            {
                "doctor_id": doctor_id,
                "doctor": nombres.get(doctor_id),
                "atenciones": len(valores),
                "promedio_minutos": round(sum(valores) / len(valores), 2),
                "maximo_minutos": round(max(valores), 2),
            }
            for doctor_id, valores in espera_por_doctor.items()
        ]
        detalle.sort(key=lambda x: x["promedio_minutos"], reverse=True)

        return {
            "desde": _iso(desde),
            "hasta": _iso(hasta),
            "total_atenciones": len(todas),
            "promedio_minutos": round(sum(todas) / len(todas), 2) if todas else 0,
            "detalle": detalle,
        }

    # ---------- Inventario bajo ----------
    def inventario_bajo(self, umbral: int = 10):
        stock_total = func.coalesce(func.sum(Inventario.stock_actual), 0)
        filas = self.db.execute(
            select(
                Medicamento.id_PK,
                Medicamento.nombre,
                Medicamento.presentacion,
                Medicamento.categoria,
                stock_total.label("stock_total"),
                func.count(Inventario.id_PK).label("lotes"),
                func.min(Inventario.fecha_vencimiento).label("proximo_vencimiento"),
            )
            .join(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
            .group_by(
                Medicamento.id_PK,
                Medicamento.nombre,
                Medicamento.presentacion,
                Medicamento.categoria,
            )
            .having(stock_total <= umbral)
            .order_by(stock_total.asc(), Medicamento.nombre)
        ).all()

        detalle = [
            {
                "medicamento_id": f.id_PK,
                "nombre": f.nombre,
                "presentacion": f.presentacion,
                "categoria": f.categoria,
                "stock_total": int(f.stock_total),
                "lotes": f.lotes,
                "proximo_vencimiento": _iso(f.proximo_vencimiento),
            }
            for f in filas
        ]
        return {"umbral": umbral, "total": len(detalle), "detalle": detalle}

    # ---------- Recetas ----------
    def recetas(self, desde: date | None, hasta: date | None):
        ini, fin = _rango_datetime(desde, hasta)
        stmt = select(Receta.doctor_id_FK, Receta.estado, func.count()).group_by(
            Receta.doctor_id_FK, Receta.estado
        )
        if ini:
            stmt = stmt.where(Receta.creado_en >= ini)
        if fin:
            stmt = stmt.where(Receta.creado_en < fin)

        nombres = self._nombres_doctores()
        por_estado: dict[str, int] = defaultdict(int)
        por_doctor: dict[int | None, dict] = {}
        total = 0
        for doctor_id, estado, cantidad in self.db.execute(stmt).all():
            total += cantidad
            por_estado[estado or "sin_estado"] += cantidad
            d = por_doctor.setdefault(
                doctor_id,
                {"doctor_id": doctor_id, "doctor": nombres.get(doctor_id), "total": 0},
            )
            d["total"] += cantidad

        return {
            "desde": _iso(desde),
            "hasta": _iso(hasta),
            "total": total,
            "por_estado": dict(por_estado),
            "detalle": sorted(por_doctor.values(), key=lambda x: x["total"], reverse=True),
        }
