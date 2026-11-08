from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import ROL_ADMIN, ROL_COORDINADOR, ROL_DOCTOR, clinica_de, exigir_rol
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.paciente import Paciente
from app.models.receta import Receta
from app.models.usuario import Usuario
from app.schemas.consulta import ConsultaActualizar, ConsultaCrear, ConsultaOut
from app.services.acceso_clinico import doctor_de_usuario, puede_ver_paciente
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar

router = APIRouter(prefix="/api/consultas", tags=["Consultas"])


def _out(db: Session, c: Consulta) -> dict:
    ids = [r[0] for r in db.query(Receta.id_PK).filter(Receta.consulta_id_FK == c.id_PK).all()]
    return {
        "id_PK": c.id_PK,
        "cita_id_FK": c.cita_id_FK,
        "paciente_id_FK": c.paciente_id_FK,
        "doctor_id_FK": c.doctor_id_FK,
        "diagnostico": c.diagnostico,
        "tratamiento": c.tratamiento,
        "notas": c.notas,
        "fecha_visita": c.fecha_visita,
        "signos_vitales": c.signos_vitales,
        "fecha_proxima_cita": c.fecha_proxima_cita,
        "codigo_cie10": c.codigo_cie10,
        "receta_ids": ids,
    }


@router.post("/", response_model=ConsultaOut, status_code=status.HTTP_201_CREATED)
def registrar_consulta(
    datos: ConsultaCrear,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Registra la consulta realizada en una cita (paso previo al expediente y la receta)."""
    exigir_rol(usuario_actual, [ROL_DOCTOR], "Solo los médicos pueden registrar consultas")
    doctor = doctor_de_usuario(db, usuario_actual)
    if not doctor:
        raise HTTPException(status_code=404, detail="Perfil de médico no encontrado")

    cita = db.query(Cita).filter(Cita.id_PK == datos.cita_id_FK).first()
    if not cita:
        raise HTTPException(status_code=404, detail="La cita no existe")
    clinica = clinica_de(usuario_actual)
    if clinica is not None and cita.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta cita")
    if cita.doctor_id_FK != doctor.id_PK:
        raise HTTPException(status_code=403, detail="Solo puedes registrar consultas de tus citas")
    if (cita.estado or "").lower() in ("cancelada", "no_asistio"):
        raise HTTPException(status_code=409, detail="No se puede registrar una consulta de una cita cancelada o no asistida")

    # La receta puede haber creado una consulta «vacía»: se completa en lugar de duplicar
    consulta = (
        db.query(Consulta)
        .filter(Consulta.cita_id_FK == cita.id_PK, Consulta.doctor_id_FK == doctor.id_PK)
        .first()
    )
    if consulta and (consulta.diagnostico or consulta.tratamiento or consulta.notas):
        raise HTTPException(status_code=409, detail="La cita ya tiene una consulta registrada; edítala con PUT")
    if not consulta:
        consulta = Consulta(
            cita_id_FK=cita.id_PK,
            paciente_id_FK=cita.paciente_id_FK,
            doctor_id_FK=doctor.id_PK,
        )
        db.add(consulta)

    consulta.diagnostico = datos.diagnostico
    consulta.tratamiento = datos.tratamiento
    consulta.notas = datos.notas
    consulta.signos_vitales = datos.signos_vitales
    consulta.fecha_proxima_cita = datos.fecha_proxima_cita
    consulta.codigo_cie10 = datos.codigo_cie10
    consulta.fecha_visita = consulta.fecha_visita or datetime.now()
    db.flush()

    if datos.finalizar_cita and (cita.estado or "").lower() != "completada":
        cita.estado = "completada"

    registrar_auditoria(
        db, usuario_actual, "CREAR", "consultas", consulta.id_PK, None,
        serializar({"cita_id": cita.id_PK, "paciente_id": cita.paciente_id_FK, "cie10": datos.codigo_cie10}),
        ip=ip_desde_request(request), descripcion="Consulta registrada",
    )
    db.commit()
    db.refresh(consulta)
    return _out(db, consulta)


@router.get("/paciente/{paciente_id}", response_model=list[ConsultaOut])
def consultas_de_paciente(
    paciente_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = db.query(Paciente).filter(Paciente.id_PK == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if not puede_ver_paciente(db, usuario_actual, paciente):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este historial")
    consultas = (
        db.query(Consulta)
        .filter(Consulta.paciente_id_FK == paciente_id)
        .order_by(Consulta.fecha_visita.desc())
        .all()
    )
    return [_out(db, c) for c in consultas]


@router.get("/{consulta_id}", response_model=ConsultaOut)
def obtener_consulta(
    consulta_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    consulta = db.query(Consulta).filter(Consulta.id_PK == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    paciente = db.query(Paciente).filter(Paciente.id_PK == consulta.paciente_id_FK).first()
    if not paciente or not puede_ver_paciente(db, usuario_actual, paciente):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver esta consulta")
    return _out(db, consulta)


@router.put("/{consulta_id}", response_model=ConsultaOut)
def actualizar_consulta(
    consulta_id: int,
    datos: ConsultaActualizar,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_DOCTOR, ROL_ADMIN], "Solo el médico tratante puede editar la consulta")
    consulta = db.query(Consulta).filter(Consulta.id_PK == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    if usuario_actual.rol_id_FK == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario_actual)
        if not doctor or consulta.doctor_id_FK != doctor.id_PK:
            raise HTTPException(status_code=403, detail="Solo puedes editar tus propias consultas")
    else:
        paciente = db.query(Paciente).filter(Paciente.id_PK == consulta.paciente_id_FK).first()
        if not paciente or not puede_ver_paciente(db, usuario_actual, paciente):
            raise HTTPException(status_code=403, detail="No tienes permiso sobre esta consulta")

    cambios = datos.model_dump(exclude_unset=True)
    antiguos = {k: getattr(consulta, k) for k in cambios}
    for campo, valor in cambios.items():
        setattr(consulta, campo, valor)
    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "consultas", consulta.id_PK,
        serializar(antiguos), serializar(cambios), ip=ip_desde_request(request),
        descripcion="Consulta actualizada",
    )
    db.commit()
    db.refresh(consulta)
    return _out(db, consulta)
