from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import ROL_ADMIN, ROL_COORDINADOR, ROL_DOCTOR, clinica_de, exigir_rol
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.doctor import Doctor
from app.models.paciente import Paciente
from app.models.transferencia_paciente import TransferenciaPaciente
from app.models.usuario import Usuario
from app.schemas.transferencia import TransferenciaCrear, TransferenciaOut
from app.services.acceso_clinico import (
    doctor_de_usuario, doctor_tiene_relacion, nombre_completo, puede_ver_paciente,
)
from app.services.notificacion_service import NotificacionService
from app.utils.auditoria import ip_desde_request, registrar_auditoria

router = APIRouter(prefix="/api/transferencias", tags=["Transferencia de pacientes"])

ESTADOS_NO_ACTIVOS = ("cancelada", "no_asistio", "completada", "atendida")


def _out(t: TransferenciaPaciente, conflictos: list[dict] | None = None) -> dict:
    return {
        "id_PK": t.id_PK,
        "paciente_id_FK": t.paciente_id_FK,
        "paciente": nombre_completo(t.paciente),
        "doctor_origen_id_FK": t.doctor_origen_id_FK,
        "doctor_origen": t.doctor_origen.nombre if t.doctor_origen else None,
        "doctor_destino_id_FK": t.doctor_destino_id_FK,
        "doctor_destino": t.doctor_destino.nombre if t.doctor_destino else None,
        "motivo": t.motivo,
        "citas_reasignadas": t.citas_reasignadas,
        "citas_con_conflicto": conflictos or [],
        "creado_en": t.creado_en,
    }


def _hay_empalme(db: Session, doctor_id: int, cita: Cita) -> bool:
    q = db.query(Cita.id_PK).filter(
        Cita.doctor_id_FK == doctor_id,
        Cita.fecha == cita.fecha,
        or_(Cita.estado.is_(None), Cita.estado.notin_(["cancelada", "no_asistio"])),
    )
    if cita.hora_inicio and cita.hora_fin:
        q = q.filter(Cita.hora_inicio < cita.hora_fin, Cita.hora_fin > cita.hora_inicio)
    elif cita.hora_inicio:
        q = q.filter(Cita.hora_inicio == cita.hora_inicio)
    return q.first() is not None


@router.post("/", response_model=TransferenciaOut, status_code=status.HTTP_201_CREATED)
def transferir_paciente(
    datos: TransferenciaCrear,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Transfiere un paciente a otro médico conservando su expediente e historial.

    * Registra la transferencia en el historial.
    * Reasigna las citas FUTURAS vigentes del paciente al nuevo médico
      (las que se empalman con su agenda se reportan como conflicto).
    * El nuevo médico obtiene acceso al expediente (ver acceso_clinico).
    """
    exigir_rol(usuario_actual, [ROL_DOCTOR, ROL_ADMIN, ROL_COORDINADOR])

    paciente = db.query(Paciente).filter(Paciente.id_PK == datos.paciente_id_FK).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    clinica = clinica_de(usuario_actual)
    if clinica is not None and paciente.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="El paciente no pertenece a tu clínica")

    if usuario_actual.rol_id_FK == ROL_DOCTOR:
        origen = doctor_de_usuario(db, usuario_actual)
        if not origen:
            raise HTTPException(status_code=404, detail="Perfil de médico no encontrado")
        if not doctor_tiene_relacion(db, origen.id_PK, paciente.id_PK):
            raise HTTPException(status_code=403, detail="Solo puedes transferir pacientes que atiendes")
    else:
        if datos.doctor_origen_id_FK is None:
            raise HTTPException(status_code=422, detail="Indica el médico de origen (doctor_origen_id_FK)")
        origen = db.query(Doctor).filter(Doctor.id_PK == datos.doctor_origen_id_FK).first()
        if not origen:
            raise HTTPException(status_code=404, detail="El médico de origen no existe")

    destino = db.query(Doctor).filter(Doctor.id_PK == datos.doctor_destino_id_FK).first()
    if not destino or (destino.estado or "").lower() != "activo":
        raise HTTPException(status_code=404, detail="El médico destino no existe o está inactivo")
    if destino.id_PK == origen.id_PK:
        raise HTTPException(status_code=400, detail="El médico destino debe ser distinto al de origen")
    if clinica is not None and destino.usuario and destino.usuario.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="El médico destino no pertenece a tu clínica")

    futuras = (
        db.query(Cita)
        .filter(
            Cita.paciente_id_FK == paciente.id_PK,
            Cita.doctor_id_FK == origen.id_PK,
            Cita.fecha >= date.today(),
            or_(Cita.estado.is_(None), Cita.estado.notin_(ESTADOS_NO_ACTIVOS)),
        )
        .all()
    )
    reasignadas, conflictos = 0, []
    for cita in futuras:
        if _hay_empalme(db, destino.id_PK, cita):
            conflictos.append(
                {"cita_id": cita.id_PK, "fecha": cita.fecha.isoformat(),
                 "hora_inicio": cita.hora_inicio.isoformat() if cita.hora_inicio else None}
            )
            continue
        cita.doctor_id_FK = destino.id_PK
        cita.notas = f"{cita.notas or ''}\n[Paciente transferido de Dr. {origen.nombre} a Dr. {destino.nombre}]".strip()
        reasignadas += 1

    transferencia = TransferenciaPaciente(
        clinica_id_FK=paciente.clinica_id_FK,
        paciente_id_FK=paciente.id_PK,
        doctor_origen_id_FK=origen.id_PK,
        doctor_destino_id_FK=destino.id_PK,
        motivo=datos.motivo,
        citas_reasignadas=reasignadas,
        realizado_por=usuario_actual.id_PK,
    )
    db.add(transferencia)
    db.flush()
    registrar_auditoria(
        db, usuario_actual, "CREAR", "transferencias_paciente", transferencia.id_PK, None,
        {"paciente_id": paciente.id_PK, "origen": origen.id_PK, "destino": destino.id_PK,
         "citas_reasignadas": reasignadas, "conflictos": len(conflictos)},
        ip=ip_desde_request(request), descripcion="Transferencia de paciente entre médicos",
    )
    db.commit()
    db.refresh(transferencia)

    try:  # avisos: no deben romper la respuesta
        servicio = NotificacionService(db)
        nombre = nombre_completo(paciente) or "Paciente"
        if destino.usuario_id_FK:
            servicio.crear(destino.usuario_id_FK, f"Se te transfirió al paciente {nombre}. Ya puedes consultar su expediente.",
                           tipo="patient_transferred", enlace="/doctor/pacientes")
        if paciente.usuario_id_FK:
            servicio.crear(paciente.usuario_id_FK, f"Tu atención fue transferida al Dr. {destino.nombre}.",
                           tipo="patient_transferred", enlace="/paciente")
    except Exception:  # noqa: BLE001
        pass

    return _out(transferencia, conflictos)


@router.get("/recibidas", response_model=list[TransferenciaOut])
def transferencias_recibidas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_DOCTOR])
    doctor = doctor_de_usuario(db, usuario_actual)
    if not doctor:
        return []
    filas = (
        db.query(TransferenciaPaciente)
        .filter(TransferenciaPaciente.doctor_destino_id_FK == doctor.id_PK)
        .order_by(TransferenciaPaciente.creado_en.desc())
        .all()
    )
    return [_out(t) for t in filas]


@router.get("/paciente/{paciente_id}", response_model=list[TransferenciaOut])
def historial_de_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = db.query(Paciente).filter(Paciente.id_PK == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if not puede_ver_paciente(db, usuario_actual, paciente):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este historial")
    filas = (
        db.query(TransferenciaPaciente)
        .filter(TransferenciaPaciente.paciente_id_FK == paciente_id)
        .order_by(TransferenciaPaciente.creado_en.desc())
        .all()
    )
    return [_out(t) for t in filas]
