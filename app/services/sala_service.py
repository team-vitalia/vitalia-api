import logging
from datetime import date, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cita import Cita
from app.models.doctor_sala import DoctorSala
from app.models.equipamiento_sala import EquipamientoSala
from app.models.sala import Sala
from app.models.usuario import Usuario
from app.schemas.equipamiento import EquipamientoCreate
from app.schemas.sala import SalaCreate, SalaUpdate
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar
from app.utils.textos_auditoria import frase_cambios, valor_legible

logger = logging.getLogger(__name__)

ESTADOS_CITA_FUERA = ("cancelada", "completada")
PROBLEMA_EQUIPO = ("mantenimiento", "fuera_de_servicio")


def estado_mantenimiento(equipo, hoy: date | None = None) -> str:
    """al_dia | proximo (<= 30 días) | vencido | sin_programar."""
    hoy = hoy or date.today()
    prox = getattr(equipo, "proximo_mantenimiento", None)
    if not prox:
        return "sin_programar"
    if prox < hoy:
        return "vencido"
    if prox <= hoy + timedelta(days=30):
        return "proximo"
    return "al_dia"


def _columnas(obj) -> dict:
    return serializar({c.name: getattr(obj, c.name) for c in obj.__table__.columns})


class SalaService:
    def __init__(self, db: Session, clinica_id: int | None = None):
        self.db = db
        self.clinica_id = clinica_id

    # ------------------------------------------------------------ consultas
    def obtener(self, sala_id: int) -> Sala | None:
        """Devuelve la sala SOLO si es de la clínica del usuario (aislamiento entre clínicas)."""
        sala = self.db.get(Sala, sala_id)
        if not sala:
            return None
        if self.clinica_id is not None and getattr(sala, "clinica_id_FK", None) != self.clinica_id:
            return None
        return sala

    def listar(
        self,
        clinica_id: int | None = None,
        estado: str | None = None,
        piso: str | None = None,
        tipo: str | None = None,
        page: int = 1,
        page_size: int = 20,
        buscar: str | None = None,
    ):
        clinica_id = clinica_id if clinica_id is not None else self.clinica_id
        stmt = select(Sala)
        if clinica_id is not None:
            stmt = stmt.where(Sala.clinica_id_FK == clinica_id)
        if estado:
            stmt = stmt.where(Sala.estado == estado)
        if piso:
            stmt = stmt.where(Sala.piso == piso)
        if tipo:
            stmt = stmt.where(Sala.tipo.ilike(f"%{tipo}%"))
        if buscar:
            like = f"%{buscar}%"
            stmt = stmt.where(Sala.nombre.ilike(like) | Sala.ubicacion.ilike(like))

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.order_by(Sala.nombre).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return items, total

    def conteos(self, salas: list) -> dict[int, dict]:
        """Equipos, equipos con problema y citas próximas por sala (para las tarjetas de la app)."""
        ids = [s.id_PK for s in salas]
        out = {i: {"total_equipos": 0, "equipos_con_problema": 0, "citas_proximas": 0} for i in ids}
        if not ids:
            return out
        try:
            for sala_id, estado, n in self.db.execute(
                select(EquipamientoSala.sala_id_FK, EquipamientoSala.estado, func.count())
                .where(EquipamientoSala.sala_id_FK.in_(ids))
                .group_by(EquipamientoSala.sala_id_FK, EquipamientoSala.estado)
            ).all():
                out[sala_id]["total_equipos"] += n
                if estado in PROBLEMA_EQUIPO:
                    out[sala_id]["equipos_con_problema"] += n
            for sala_id, n in self.db.execute(
                select(Cita.sala_id_FK, func.count())
                .where(
                    Cita.sala_id_FK.in_(ids),
                    Cita.fecha >= date.today(),
                    Cita.estado.notin_(ESTADOS_CITA_FUERA) | Cita.estado.is_(None),
                )
                .group_by(Cita.sala_id_FK)
            ).all():
                out[sala_id]["citas_proximas"] = n
        except Exception:  # los contadores son un extra: nunca deben tumbar el listado
            logger.exception("No se pudieron calcular los contadores de salas")
        return out

    # ------------------------------------------------------------ escritura
    def _nombre_repetido(self, nombre: str, excluir_id: int | None = None) -> bool:
        consulta = self.db.query(Sala).filter(func.lower(Sala.nombre) == nombre.lower())
        if self.clinica_id is not None:
            consulta = consulta.filter(Sala.clinica_id_FK == self.clinica_id)
        existente = consulta.first()
        return bool(existente) and getattr(existente, "id_PK", None) != excluir_id

    def crear(self, payload: SalaCreate, usuario: Usuario, request: Request) -> Sala:
        # CORREGIDO: antes no se asignaba la clínica y la inserción fallaba (clinica_id_FK es NOT NULL)
        clinica_id = self.clinica_id if self.clinica_id is not None else getattr(usuario, "clinica_id_FK", None)
        if self._nombre_repetido(payload.nombre):
            raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe una sala llamada «{payload.nombre}».")

        datos = payload.model_dump()
        if clinica_id is not None:
            datos["clinica_id_FK"] = clinica_id
        sala = Sala(**datos)
        self.db.add(sala)
        self.db.flush()

        detalle = ", ".join(x for x in [sala.tipo, f"piso {sala.piso}" if sala.piso else None] if x)
        registrar_auditoria(
            db=self.db, usuario=usuario, accion="CREATE", tabla="salas", id_registro=sala.id_PK,
            antiguos=None, nuevos=serializar(payload.model_dump(mode="json")),
            ip=ip_desde_request(request),
            descripcion=f"Se creó la sala «{sala.nombre}»" + (f" ({detalle})" if detalle else ""),
        )
        self.db.commit()
        self.db.refresh(sala)
        return sala

    def actualizar(self, sala_id: int, payload: SalaUpdate, usuario: Usuario, request: Request) -> Sala | None:
        sala = self.obtener(sala_id)
        if not sala:
            return None

        cambios = payload.model_dump(exclude_unset=True)
        if "nombre" in cambios and cambios["nombre"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El nombre de la sala no puede quedar vacío.")
        if cambios.get("nombre") and self._nombre_repetido(cambios["nombre"], excluir_id=sala.id_PK):
            raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe una sala llamada «{cambios['nombre']}».")

        antes = _columnas(sala)
        for k, v in cambios.items():
            setattr(sala, k, v)
        self.db.flush()
        despues = _columnas(sala)

        registrar_auditoria(
            db=self.db, usuario=usuario, accion="UPDATE", tabla="salas", id_registro=sala.id_PK,
            antiguos=antes, nuevos=despues, ip=ip_desde_request(request),
            descripcion=f"Se modificó la sala «{sala.nombre}»: {frase_cambios(antes, despues)}",
        )
        self.db.commit()
        self.db.refresh(sala)
        return sala

    def cambiar_estado(self, sala_id: int, nuevo_estado: str, usuario: Usuario, request: Request) -> Sala | None:
        sala = self.obtener(sala_id)
        if not sala:
            return None

        anterior = sala.estado
        if anterior == nuevo_estado:
            return sala

        # Dejar fuera de uso una sala con citas pendientes dejaría citas "fantasma": se avisa antes.
        if nuevo_estado in ("inactiva", "mantenimiento"):
            pendientes = self.db.query(Cita).filter(
                Cita.sala_id_FK == sala.id_PK,
                Cita.fecha >= date.today(),
                Cita.estado.notin_(ESTADOS_CITA_FUERA) | Cita.estado.is_(None),
            ).count()
            if pendientes:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"La sala «{sala.nombre}» tiene {pendientes} cita(s) pendiente(s). "
                    "Reprográmalas o cámbiales de sala antes de dejarla fuera de uso.",
                )

        sala.estado = nuevo_estado
        self.db.flush()
        registrar_auditoria(
            db=self.db, usuario=usuario, accion="UPDATE_ESTADO", tabla="salas", id_registro=sala.id_PK,
            antiguos={"estado": anterior}, nuevos={"estado": nuevo_estado}, ip=ip_desde_request(request),
            descripcion=f"La sala «{sala.nombre}» pasó de «{valor_legible(anterior)}» a «{valor_legible(nuevo_estado)}»",
        )
        self.db.commit()
        self.db.refresh(sala)
        return sala

    def eliminar(self, sala_id: int, usuario: Usuario, request: Request) -> bool:
        sala = self.obtener(sala_id)
        if not sala:
            return False

        # CORREGIDO: antes se intentaba borrar y la base devolvía error 500 si había citas.
        citas = self.db.query(Cita).filter(Cita.sala_id_FK == sala.id_PK).count()
        if citas:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"No se puede eliminar «{sala.nombre}» porque tiene {citas} cita(s) registrada(s). "
                "Márcala como «Inactiva» para conservar el historial.",
            )

        antes = _columnas(sala)
        nombre = sala.nombre
        n_equipos = self.db.query(EquipamientoSala).filter(EquipamientoSala.sala_id_FK == sala.id_PK).delete()
        self.db.query(DoctorSala).filter(DoctorSala.sala_id_FK == sala.id_PK).delete()
        self.db.delete(sala)

        registrar_auditoria(
            db=self.db, usuario=usuario, accion="DELETE", tabla="salas", id_registro=sala_id,
            antiguos=antes, nuevos=None, ip=ip_desde_request(request),
            descripcion=f"Se eliminó la sala «{nombre}»" + (f" junto con sus {n_equipos} equipo(s)" if n_equipos else ""),
        )
        self.db.commit()
        return True

    # ------------------------------------------------------------ equipamiento
    def listar_equipos(self, sala_id: int) -> list[EquipamientoSala] | None:
        if not self.obtener(sala_id):
            return None
        return self.db.scalars(
            select(EquipamientoSala).where(EquipamientoSala.sala_id_FK == sala_id).order_by(EquipamientoSala.nombre_equipo)
        ).all()

    def agregar_equipo(
        self, sala_id: int, payload: EquipamientoCreate, usuario: Usuario, request: Request
    ) -> EquipamientoSala | None:
        sala = self.obtener(sala_id)
        if not sala:
            return None

        datos = payload.model_dump()
        if not (datos.get("nombre_equipo") or "").strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El nombre del equipo es obligatorio.")
        serie = (datos.get("numero_serie") or "").strip() or None
        datos["numero_serie"] = serie
        if serie:
            consulta = self.db.query(EquipamientoSala).filter(EquipamientoSala.numero_serie == serie)
            if self.clinica_id is not None:  # el número de serie solo debe ser único dentro de la clínica
                consulta = consulta.join(Sala, Sala.id_PK == EquipamientoSala.sala_id_FK).filter(
                    Sala.clinica_id_FK == self.clinica_id
                )
            if consulta.first():
                raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un equipo con el número de serie «{serie}».")

        equipo = EquipamientoSala(sala_id_FK=sala_id, **datos)
        self.db.add(equipo)
        self.db.flush()

        registrar_auditoria(
            db=self.db, usuario=usuario, accion="CREATE", tabla="equipamiento_sala", id_registro=equipo.id_PK,
            antiguos=None, nuevos=serializar(payload.model_dump(mode="json")), ip=ip_desde_request(request),
            descripcion=f"Se agregó el equipo «{equipo.nombre_equipo}» a la sala «{sala.nombre}»",
        )
        self.db.commit()
        self.db.refresh(equipo)
        return equipo
