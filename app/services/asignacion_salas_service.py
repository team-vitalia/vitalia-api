"""Asignación de salas a doctores por horario (calendario semanal).

Reglas:
  * Un doctor solo puede estar en UNA sala a la vez (sus bloques no se pueden traslapar).
  * Una sala solo puede tener UN doctor a la vez (no se puede repetir en el mismo horario).
  * Una sala inactiva o en mantenimiento no se puede asignar.
  * Dos bloques solo chocan si coinciden en el día (o alguno aplica a «todos los días») Y sus horas se cruzan;
    por eso una sala SÍ puede compartirse entre doctores si lo hacen en horarios distintos.
  * Un turno puede cruzar la medianoche (23:00 → 04:00): termina al día siguiente y ese día también
    cuenta como ocupado (ver app/core/horarios_sala.py).
"""
from __future__ import annotations

import logging
from datetime import time

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.horarios_sala import cruza_medianoche, se_traslapan  # noqa: F401  (se_traslapan se reexporta)
from app.models.doctor import Doctor
from app.models.doctor_sala import DoctorSala
from app.models.sala import Sala
from app.models.usuario import Usuario
from app.schemas.doctor_sala import AsignacionNueva, ConflictoOut
from app.services.citas_notification_service import guardar_notificacion_bd
from app.services.connection_manager import manager
from app.utils.auditoria import ip_desde_request, registrar_auditoria

logger = logging.getLogger(__name__)

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
SALA_NO_DISPONIBLE = ("inactiva", "mantenimiento")


def nombre_dia(d: int | None) -> str:
    return "todos los días" if d is None else DIAS[d].lower()


def hhmm(t: time | None) -> str:
    return t.strftime("%H:%M") if t else "--:--"


def cuando(dia: int | None, ini: time, fin: time) -> str:
    prefijo = "todos los días" if dia is None else f"el {DIAS[dia].lower()}"
    if ini and fin and cruza_medianoche(ini, fin):
        return f"{prefijo} de {hhmm(ini)} a {hhmm(fin)} del día siguiente"
    return f"{prefijo} de {hhmm(ini)} a {hhmm(fin)}"


class AsignacionSalasService:
    def __init__(self, db: Session, clinica_id: int | None = None):
        self.db = db
        self.clinica_id = clinica_id

    # ------------------------------------------------------------ búsquedas (con aislamiento por clínica)
    def doctor(self, doctor_id: int) -> Doctor | None:
        q = self.db.query(Doctor).filter(Doctor.id_PK == doctor_id)
        if self.clinica_id is not None:
            q = q.join(Usuario, Usuario.id_PK == Doctor.usuario_id_FK).filter(Usuario.clinica_id_FK == self.clinica_id)
        return q.first()

    def sala(self, sala_id: int) -> Sala | None:
        q = self.db.query(Sala).filter(Sala.id_PK == sala_id)
        if self.clinica_id is not None:
            q = q.filter(Sala.clinica_id_FK == self.clinica_id)
        return q.first()

    def _asignacion(self, asignacion_id: int) -> DoctorSala | None:
        fila = self.db.get(DoctorSala, asignacion_id)
        if not fila:
            return None
        if self.clinica_id is not None:
            sala = self.db.get(Sala, fila.sala_id_FK)
            if not sala or sala.clinica_id_FK != self.clinica_id:
                return None
        return fila

    def nombre_doctor(self, doctor: Doctor | None) -> str:
        if not doctor:
            return "un doctor"
        u = self.db.get(Usuario, doctor.usuario_id_FK) if doctor.usuario_id_FK else None
        if not u:
            return f"Doctor #{doctor.id_PK}"
        partes = [u.nombre, getattr(u, "apellido_paterno", None), getattr(u, "apellido_materno", None)]
        return " ".join(p for p in partes if p) or f"Doctor #{doctor.id_PK}"

    # ------------------------------------------------------------ validación
    def conflictos(
        self, doctor_id: int, sala_id: int, dia: int | None, ini: time, fin: time, excluir_id: int | None = None
    ) -> list[ConflictoOut]:
        out: list[ConflictoOut] = []
        sala = self.sala(sala_id)
        if sala and (sala.estado or "") in SALA_NO_DISPONIBLE:
            out.append(ConflictoOut(
                tipo="sala_no_disponible",
                mensaje=f"La sala «{sala.nombre}» está {sala.estado.replace('_', ' ')} y no se puede asignar.",
            ))

        # 1) El doctor no puede estar en dos salas a la vez
        propias = self.db.query(DoctorSala).filter(DoctorSala.doctor_id_FK == doctor_id).all()
        for f in propias:
            if excluir_id and f.id_PK == excluir_id:
                continue
            if se_traslapan(dia, ini, fin, f.dia_semana, f.hora_inicio, f.hora_fin):
                s = self.db.get(Sala, f.sala_id_FK)
                out.append(ConflictoOut(
                    tipo="doctor_ocupado",
                    mensaje=(f"Ese doctor ya está en la sala «{s.nombre if s else f.sala_id_FK}» "
                             f"{cuando(f.dia_semana, f.hora_inicio, f.hora_fin)}. Un doctor solo puede usar una sala a la vez."),
                ))

        out.extend(self.conflictos_sala_otros(doctor_id, sala_id, dia, ini, fin, excluir_id))
        return out

    def conflictos_sala_otros(
        self, doctor_id: int, sala_id: int, dia: int | None, ini: time, fin: time, excluir_id: int | None = None
    ) -> list[ConflictoOut]:
        """La sala no puede tener dos doctores a la vez: choques con bloques de OTROS doctores."""
        out: list[ConflictoOut] = []
        de_la_sala = self.db.query(DoctorSala).filter(DoctorSala.sala_id_FK == sala_id).all()
        for f in de_la_sala:
            if (excluir_id and f.id_PK == excluir_id) or f.doctor_id_FK == doctor_id:
                continue
            if se_traslapan(dia, ini, fin, f.dia_semana, f.hora_inicio, f.hora_fin):
                otro = self.db.get(Doctor, f.doctor_id_FK)
                out.append(ConflictoOut(
                    tipo="sala_ocupada",
                    mensaje=(f"La sala ya está ocupada por {self.nombre_doctor(otro)} "
                             f"{cuando(f.dia_semana, f.hora_inicio, f.hora_fin)}."),
                ))
        return out

    def validar(self, datos: AsignacionNueva, excluir_id: int | None = None) -> list[ConflictoOut]:
        if not self.doctor(datos.doctor_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El doctor no existe")
        if not self.sala(datos.sala_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La sala no existe")
        return self.conflictos(datos.doctor_id, datos.sala_id, datos.dia_semana, datos.hora_inicio, datos.hora_fin, excluir_id)

    def _exigir_sin_conflictos(self, datos: AsignacionNueva, excluir_id: int | None = None) -> None:
        conflictos = self.validar(datos, excluir_id)
        if conflictos:
            extra = f" (y {len(conflictos) - 1} conflicto(s) más)" if len(conflictos) > 1 else ""
            raise HTTPException(status.HTTP_409_CONFLICT, conflictos[0].mensaje + extra)

    # ------------------------------------------------------------ aviso al doctor
    async def avisar_doctor(self, doctor: Doctor, titulo: str, texto: str, tipo: str) -> bool:
        """Guarda la notificación y la empuja en tiempo real. Nunca debe tumbar la operación principal."""
        uid = getattr(doctor, "usuario_id_FK", None)
        if not uid:
            return False
        try:
            notif = guardar_notificacion_bd(self.db, uid, texto, tipo, "/doctor")
            payload = {"type": tipo, "title": titulo, "body": texto, "timestamp": __import__("datetime").datetime.now().isoformat()}
            if notif:
                payload["notificacion_id"] = notif.id_PK
            await manager.send_personal_message(payload, f"user_{uid}")
            return bool(notif)
        except Exception:
            logger.warning("No se pudo avisar al doctor %s", doctor.id_PK, exc_info=True)
            return False

    # ------------------------------------------------------------ operaciones
    async def crear(self, datos: AsignacionNueva, usuario: Usuario, request: Request) -> tuple[DoctorSala, bool]:
        self._exigir_sin_conflictos(datos)
        doctor, sala = self.doctor(datos.doctor_id), self.sala(datos.sala_id)
        fila = DoctorSala(
            doctor_id_FK=datos.doctor_id, sala_id_FK=datos.sala_id, dia_semana=datos.dia_semana,
            hora_inicio=datos.hora_inicio, hora_fin=datos.hora_fin,
        )
        self.db.add(fila)
        self.db.flush()
        nombre = self.nombre_doctor(doctor)
        registrar_auditoria(
            db=self.db, usuario=usuario, accion="ASIGNAR_SALA_DOCTOR", tabla="doctor_salas", id_registro=fila.id_PK,
            antiguos=None,
            nuevos={"doctor": nombre, "sala": sala.nombre, "dia": nombre_dia(datos.dia_semana),
                    "hora_inicio": hhmm(datos.hora_inicio), "hora_fin": hhmm(datos.hora_fin)},
            ip=ip_desde_request(request),
            descripcion=f"Se asignó la sala «{sala.nombre}» a {nombre} {cuando(datos.dia_semana, datos.hora_inicio, datos.hora_fin)}",
        )
        self.db.commit()
        self.db.refresh(fila)
        avisado = False
        if datos.notificar:
            piso = f" (piso {sala.piso})" if sala.piso else ""
            avisado = await self.avisar_doctor(
                doctor, "Sala asignada",
                f"Se te asignó la sala «{sala.nombre}»{piso} {cuando(datos.dia_semana, datos.hora_inicio, datos.hora_fin)}.",
                "room_assigned",
            )
        return fila, avisado

    async def actualizar(
        self, asignacion_id: int, datos: AsignacionNueva, usuario: Usuario, request: Request
    ) -> tuple[DoctorSala, bool] | None:
        fila = self._asignacion(asignacion_id)
        if not fila:
            return None
        self._exigir_sin_conflictos(datos, excluir_id=asignacion_id)
        sala_ant = self.db.get(Sala, fila.sala_id_FK)
        doctor_ant = self.db.get(Doctor, fila.doctor_id_FK)
        antes = {"doctor": self.nombre_doctor(doctor_ant), "sala": sala_ant.nombre if sala_ant else "—",
                 "dia": nombre_dia(fila.dia_semana), "hora_inicio": hhmm(fila.hora_inicio), "hora_fin": hhmm(fila.hora_fin)}
        fila.doctor_id_FK, fila.sala_id_FK = datos.doctor_id, datos.sala_id
        fila.dia_semana, fila.hora_inicio, fila.hora_fin = datos.dia_semana, datos.hora_inicio, datos.hora_fin
        self.db.flush()
        doctor, sala = self.doctor(datos.doctor_id), self.sala(datos.sala_id)
        nombre = self.nombre_doctor(doctor)
        registrar_auditoria(
            db=self.db, usuario=usuario, accion="MOVER_SALA_DOCTOR", tabla="doctor_salas", id_registro=fila.id_PK,
            antiguos=antes,
            nuevos={"doctor": nombre, "sala": sala.nombre, "dia": nombre_dia(datos.dia_semana),
                    "hora_inicio": hhmm(datos.hora_inicio), "hora_fin": hhmm(datos.hora_fin)},
            ip=ip_desde_request(request),
            descripcion=f"Se cambió la asignación de {nombre}: ahora usa «{sala.nombre}» {cuando(datos.dia_semana, datos.hora_inicio, datos.hora_fin)}",
        )
        self.db.commit()
        self.db.refresh(fila)
        avisado = False
        if datos.notificar:
            avisado = await self.avisar_doctor(
                doctor, "Cambio en tu sala",
                f"Tu asignación cambió: ahora usarás la sala «{sala.nombre}» {cuando(datos.dia_semana, datos.hora_inicio, datos.hora_fin)}.",
                "room_changed",
            )
        return fila, avisado

    async def eliminar(self, asignacion_id: int, notificar: bool, usuario: Usuario, request: Request) -> tuple[bool, bool]:
        fila = self._asignacion(asignacion_id)
        if not fila:
            return False, False
        sala = self.db.get(Sala, fila.sala_id_FK)
        doctor = self.db.get(Doctor, fila.doctor_id_FK)
        nombre = self.nombre_doctor(doctor)
        detalle = cuando(fila.dia_semana, fila.hora_inicio, fila.hora_fin)
        antes = {"doctor": nombre, "sala": sala.nombre if sala else "—", "dia": nombre_dia(fila.dia_semana),
                 "hora_inicio": hhmm(fila.hora_inicio), "hora_fin": hhmm(fila.hora_fin)}
        self.db.delete(fila)
        registrar_auditoria(
            db=self.db, usuario=usuario, accion="QUITAR_SALA_DOCTOR", tabla="doctor_salas", id_registro=asignacion_id,
            antiguos=antes, nuevos=None, ip=ip_desde_request(request),
            descripcion=f"Se quitó la sala «{antes['sala']}» a {nombre} ({detalle})",
        )
        self.db.commit()
        avisado = False
        if notificar:
            avisado = await self.avisar_doctor(
                doctor, "Sala retirada", f"Se retiró tu asignación de la sala «{antes['sala']}» {detalle}.", "room_removed"
            )
        return True, avisado

    # ------------------------------------------------------------ calendario
    def resumen_exportable(self) -> dict:
        """Datos para el Excel/PDF de resumen: salas, doctores activos y todas las asignaciones de la clínica."""
        qs = self.db.query(Sala)
        if self.clinica_id is not None:
            qs = qs.filter(Sala.clinica_id_FK == self.clinica_id)
        salas = [{"id": s.id_PK, "nombre": s.nombre, "tipo": s.tipo, "piso": s.piso, "estado": s.estado} for s in qs.order_by(Sala.nombre).all()]

        qd = self.db.query(Doctor, Usuario).join(Usuario, Usuario.id_PK == Doctor.usuario_id_FK).filter(Doctor.estado == "activo")
        if self.clinica_id is not None:
            qd = qd.filter(Usuario.clinica_id_FK == self.clinica_id)
        doctores = []
        for d, u in qd.all():
            partes = [u.nombre, getattr(u, "apellido_paterno", None), getattr(u, "apellido_materno", None)]
            doctores.append({
                "id": d.id_PK,
                "nombre": " ".join(p for p in partes if p),
                "especialidad": getattr(getattr(d, "especialidad", None), "nombre", None),
            })
        doctores.sort(key=lambda x: x["nombre"].lower())
        return {"salas": salas, "doctores": doctores, "asignaciones": self.calendario()}

    def calendario(self, sala_id: int | None = None, doctor_id: int | None = None) -> list[dict]:
        q = (
            self.db.query(DoctorSala, Sala, Doctor, Usuario)
            .join(Sala, Sala.id_PK == DoctorSala.sala_id_FK)
            .join(Doctor, Doctor.id_PK == DoctorSala.doctor_id_FK)
            .join(Usuario, Usuario.id_PK == Doctor.usuario_id_FK)
        )
        if self.clinica_id is not None:
            q = q.filter(Sala.clinica_id_FK == self.clinica_id)
        if sala_id:
            q = q.filter(DoctorSala.sala_id_FK == sala_id)
        if doctor_id:
            q = q.filter(DoctorSala.doctor_id_FK == doctor_id)
        filas = []
        for f, s, d, u in q.order_by(DoctorSala.dia_semana, DoctorSala.hora_inicio).all():
            esp = getattr(getattr(d, "especialidad", None), "nombre", None)
            partes = [u.nombre, getattr(u, "apellido_paterno", None), getattr(u, "apellido_materno", None)]
            filas.append({
                "id_PK": f.id_PK, "doctor_id": d.id_PK, "doctor_nombre": " ".join(p for p in partes if p),
                "especialidad": esp, "sala_id": s.id_PK, "sala_nombre": s.nombre, "sala_tipo": s.tipo,
                "sala_piso": s.piso, "sala_estado": s.estado, "dia_semana": f.dia_semana,
                "hora_inicio": f.hora_inicio, "hora_fin": f.hora_fin,
            })
        return filas
