from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import (
    ROL_ADMIN, ROL_COORDINADOR, ROL_DOCTOR, ROL_RECEPCION, clinica_de, exigir_rol,
)
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.doctor import Doctor
from app.models.especialidad import Especialidad
from app.models.lista_espera import ListaEspera
from app.models.paciente import Paciente
from app.models.usuario import Usuario
from app.schemas.lista_espera import EsperaCrear, EsperaEstado, EsperaOut
from app.services.acceso_clinico import doctor_de_usuario, nombre_completo
from app.services.lista_espera_service import ACTIVOS, orden_prioridad
from app.services.notificacion_service import NotificacionService
from app.utils.auditoria import ip_desde_request, registrar_auditoria

router = APIRouter(prefix="/api/lista-espera", tags=["Lista de espera"])

ROLES_GESTION = [ROL_ADMIN, ROL_RECEPCION, ROL_COORDINADOR]


def _out(e: ListaEspera, posicion: int | None = None) -> dict:
    return {
        "id_PK": e.id_PK,
        "paciente_id_FK": e.paciente_id_FK,
        "paciente": nombre_completo(e.paciente),
        "doctor_id_FK": e.doctor_id_FK,
        "doctor": e.doctor.nombre if e.doctor else None,
        "especialidad_id_FK": e.especialidad_id_FK,
        "especialidad": e.especialidad.nombre if e.especialidad else None,
        "fecha_deseada": e.fecha_deseada,
        "motivo": e.motivo,
        "prioridad": e.prioridad,
        "estado": e.estado,
        "posicion": posicion,
        "creado_en": e.creado_en,
        "atendida_en": e.atendida_en,
        "cita_id_FK": e.cita_id_FK,
    }


def _entrada_de_clinica(db: Session, espera_id: int, usuario: Usuario) -> ListaEspera:
    e = db.query(ListaEspera).filter(ListaEspera.id_PK == espera_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Registro de lista de espera no encontrado")
    clinica = clinica_de(usuario)
    if clinica is not None and e.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre este registro")
    return e


@router.post("/", response_model=EsperaOut, status_code=status.HTTP_201_CREATED)
def agregar_a_lista_espera(
    datos: EsperaCrear,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_GESTION, "Solo recepción o administración gestionan la lista de espera")

    paciente = db.query(Paciente).filter(Paciente.id_PK == datos.paciente_id_FK).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    clinica = clinica_de(usuario_actual)
    if clinica is not None and paciente.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="El paciente no pertenece a tu clínica")

    if datos.doctor_id_FK is not None and not db.query(Doctor).filter(Doctor.id_PK == datos.doctor_id_FK).first():
        raise HTTPException(status_code=404, detail="El doctor no existe")
    if datos.especialidad_id_FK is not None and not db.query(Especialidad).filter(
        Especialidad.id_PK == datos.especialidad_id_FK
    ).first():
        raise HTTPException(status_code=404, detail="La especialidad no existe")

    duplicado = db.query(ListaEspera).filter(
        ListaEspera.paciente_id_FK == paciente.id_PK,
        ListaEspera.doctor_id_FK == datos.doctor_id_FK,
        ListaEspera.estado.in_(ACTIVOS),
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="El paciente ya está en la lista de espera para esta opción")

    entrada = ListaEspera(
        clinica_id_FK=paciente.clinica_id_FK,
        creado_por=usuario_actual.id_PK,
        estado="en_espera",
        **datos.model_dump(),
    )
    db.add(entrada)
    db.flush()
    registrar_auditoria(
        db, usuario_actual, "CREAR", "lista_espera", entrada.id_PK, None,
        {"paciente_id": paciente.id_PK, "prioridad": datos.prioridad},
        ip=ip_desde_request(request), descripcion="Paciente agregado a lista de espera",
    )
    db.commit()
    db.refresh(entrada)
    return _out(entrada)


@router.get("/", response_model=list[EsperaOut])
def listar_lista_espera(
    estado: str | None = Query(None, description="en_espera | notificado | asignada | cancelada"),
    doctor_id: int | None = Query(None),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_GESTION + [ROL_DOCTOR])

    q = db.query(ListaEspera)
    clinica = clinica_de(usuario_actual)
    if clinica is not None:
        q = q.filter(ListaEspera.clinica_id_FK == clinica)
    if usuario_actual.rol_id_FK == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario_actual)
        if not doctor:
            return []
        q = q.filter(ListaEspera.doctor_id_FK == doctor.id_PK)
    elif doctor_id:
        q = q.filter(ListaEspera.doctor_id_FK == doctor_id)
    q = q.filter(ListaEspera.estado == estado) if estado else q.filter(ListaEspera.estado.in_(ACTIVOS))

    filas = q.order_by(orden_prioridad(), ListaEspera.creado_en.asc()).all()
    return [_out(e, i + 1) for i, e in enumerate(filas)]


@router.patch("/{espera_id}/estado", response_model=EsperaOut)
def cambiar_estado_espera(
    espera_id: int,
    datos: EsperaEstado,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_GESTION)
    e = _entrada_de_clinica(db, espera_id, usuario_actual)
    if e.estado in ("asignada", "cancelada"):
        raise HTTPException(status_code=409, detail=f"El registro ya está {e.estado}")

    if datos.estado == "asignada":
        if datos.cita_id_FK is None:
            raise HTTPException(status_code=422, detail="Indica la cita asignada (cita_id_FK)")
        cita = db.query(Cita).filter(Cita.id_PK == datos.cita_id_FK).first()
        if not cita or cita.paciente_id_FK != e.paciente_id_FK:
            raise HTTPException(status_code=400, detail="La cita no existe o no es de este paciente")
        e.cita_id_FK = cita.id_PK
        e.atendida_en = datetime.now()
    elif datos.estado == "cancelada":
        e.atendida_en = datetime.now()

    anterior = e.estado
    e.estado = datos.estado
    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "lista_espera", e.id_PK,
        {"estado": anterior}, {"estado": e.estado}, ip=ip_desde_request(request),
        descripcion="Cambio de estado en lista de espera",
    )
    db.commit()
    db.refresh(e)
    return _out(e)


@router.post("/{espera_id}/notificar", response_model=EsperaOut)
def notificar_paciente(
    espera_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Avisa al paciente que hay disponibilidad (requiere que tenga cuenta en la app)."""
    exigir_rol(usuario_actual, ROLES_GESTION)
    e = _entrada_de_clinica(db, espera_id, usuario_actual)
    if e.estado not in ACTIVOS:
        raise HTTPException(status_code=409, detail="El registro ya no está activo")
    paciente = e.paciente
    if not paciente or not paciente.usuario_id_FK:
        raise HTTPException(status_code=409, detail="El paciente no tiene cuenta en la app; contáctalo por teléfono")

    e.estado = "notificado"
    db.commit()
    NotificacionService(db).crear(
        paciente.usuario_id_FK,
        "Hay disponibilidad para tu cita. Comunícate con recepción para confirmarla.",
        tipo="waitlist_available",
        enlace="/paciente",
    )
    db.refresh(e)
    return _out(e)


@router.delete("/{espera_id}", response_model=EsperaOut)
def quitar_de_lista_espera(
    espera_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Cancela el registro (se conserva para trazabilidad)."""
    exigir_rol(usuario_actual, ROLES_GESTION)
    e = _entrada_de_clinica(db, espera_id, usuario_actual)
    if e.estado in ("asignada", "cancelada"):
        raise HTTPException(status_code=409, detail=f"El registro ya está {e.estado}")
    e.estado = "cancelada"
    e.atendida_en = datetime.now()
    db.commit()
    db.refresh(e)
    return _out(e)
