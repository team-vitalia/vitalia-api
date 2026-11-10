from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import (
    ROL_ADMIN, ROL_ALMACEN, ROL_COORDINADOR, ROL_DOCTOR, ROL_PACIENTE,
    clinica_de, exigir_rol,
)
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.consulta import Consulta
from app.models.inventario import Inventario
from app.models.item_receta import ItemReceta
from app.models.medicamento import Medicamento
from app.models.paciente import Paciente
from app.models.receta import Receta
from app.models.usuario import Usuario
from app.schemas.receta import RecetaCreada, RecetaCrear, RecetaDetalle
from app.services import inventario_service as inv
from app.services.acceso_clinico import (
    doctor_de_usuario, nombre_completo, paciente_de_usuario, puede_ver_paciente,
)
from app.services.interacciones_service import (
    alertas_alergias, es_grave, evaluar_interacciones,
)
from app.utils.auditoria import ip_desde_request, registrar_auditoria

router = APIRouter(prefix="/api/recetas", tags=["Recetas"])


# ------------------------------------------------------------------ helpers
def _items_de(db: Session, receta_id: int) -> list[ItemReceta]:
    return (
        db.query(ItemReceta)
        .filter(ItemReceta.receta_id_FK == receta_id)
        .order_by(ItemReceta.id_PK)
        .all()
    )


def _detalle(db: Session, receta: Receta, con_disponibilidad: bool = True) -> dict:
    items = _items_de(db, receta.id_PK)
    return {
        "id_PK": receta.id_PK,
        "paciente_id_FK": receta.paciente_id_FK,
        "doctor_id_FK": receta.doctor_id_FK,
        "consulta_id_FK": receta.consulta_id_FK,
        "estado": receta.estado,
        "creado_en": receta.creado_en,
        "paciente": nombre_completo(receta.paciente),
        "doctor": receta.doctor.nombre if receta.doctor else None,
        "items": [
            {
                "id_PK": it.id_PK,
                "medicamento_id_FK": it.medicamento_id_FK,
                "medicamento": it.medicamento.nombre if it.medicamento else None,
                "presentacion": it.medicamento.presentacion if it.medicamento else None,
                "dosis": it.dosis,
                "frecuencia": it.frecuencia,
                "duracion": it.duracion,
                "cantidad": it.cantidad,
                "cantidad_dispensada": it.cantidad_dispensada or 0,
                "instrucciones": it.instrucciones,
                "via_administracion": it.via_administracion,
            }
            for it in items
        ],
        "disponibilidad": inv.disponibilidad_receta(db, items) if con_disponibilidad else [],
    }


def _puede_ver_receta(db: Session, usuario: Usuario, receta: Receta) -> bool:
    rol = usuario.rol_id_FK
    clinica = clinica_de(usuario)
    paciente = receta.paciente
    if clinica is not None and paciente is not None and paciente.clinica_id_FK != clinica:
        return False
    if rol in (ROL_ADMIN, ROL_COORDINADOR, ROL_ALMACEN):
        return True
    if rol == ROL_PACIENTE:
        return bool(paciente and paciente.usuario_id_FK == usuario.id_PK)
    if rol == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario)
        if doctor and receta.doctor_id_FK == doctor.id_PK:
            return True
        return bool(paciente and puede_ver_paciente(db, usuario, paciente))
    return False


def _consulta_para_receta(db: Session, datos: RecetaCrear, doctor, paciente) -> Consulta:
    """Valida la consulta indicada o busca/crea la consulta de la cita."""
    if datos.consulta_id_FK is not None:
        consulta = db.query(Consulta).filter(Consulta.id_PK == datos.consulta_id_FK).first()
        if not consulta:
            raise HTTPException(status_code=404, detail="La consulta indicada no existe")
        if consulta.doctor_id_FK != doctor.id_PK:
            raise HTTPException(status_code=403, detail="La consulta pertenece a otro médico")
        if consulta.paciente_id_FK != paciente.id_PK:
            raise HTTPException(status_code=400, detail="La consulta no corresponde a este paciente")
        return consulta

    cita = db.query(Cita).filter(Cita.id_PK == datos.cita_id_FK).first()
    if not cita:
        raise HTTPException(status_code=404, detail="La cita indicada no existe")
    if cita.doctor_id_FK != doctor.id_PK:
        raise HTTPException(status_code=403, detail="La cita pertenece a otro médico")
    if cita.paciente_id_FK != paciente.id_PK:
        raise HTTPException(status_code=400, detail="La cita no corresponde a este paciente")

    consulta = (
        db.query(Consulta)
        .filter(Consulta.cita_id_FK == cita.id_PK, Consulta.doctor_id_FK == doctor.id_PK)
        .first()
    )
    if not consulta:
        consulta = Consulta(
            cita_id_FK=cita.id_PK,
            paciente_id_FK=paciente.id_PK,
            doctor_id_FK=doctor.id_PK,
            fecha_visita=datetime.now(),
        )
        db.add(consulta)
        db.flush()
    return consulta


# ------------------------------------------------------------------ crear
@router.post("/", response_model=RecetaCreada, status_code=status.HTTP_201_CREATED)
def crear_receta(
    datos: RecetaCrear,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Crea una receta, revisa interacciones/alergias y consulta el inventario.

    * Interacciones de severidad grave: responde 409 hasta que el médico envíe
      `confirmar_interacciones=true`. Las demás se devuelven como advertencia.
    * Siempre devuelve `disponibilidad` por medicamento para que el médico pueda
      avisar al paciente si algo no está disponible.
    Los avisos son una ayuda de apoyo: no sustituyen el criterio clínico.
    """
    exigir_rol(usuario_actual, [ROL_DOCTOR], "Solo los médicos pueden recetar")

    doctor = doctor_de_usuario(db, usuario_actual)
    if not doctor:
        raise HTTPException(status_code=404, detail="Perfil de médico no encontrado")

    paciente = db.query(Paciente).filter(Paciente.id_PK == datos.paciente_id_FK).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    clinica = clinica_de(usuario_actual)
    if clinica is not None and paciente.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="El paciente no pertenece a tu clínica")

    ids = [it.medicamento_id_FK for it in datos.items]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Hay medicamentos repetidos en la receta")

    medicamentos: list[Medicamento] = []
    for med_id in ids:
        med = db.query(Medicamento).filter(Medicamento.id_PK == med_id).first()
        if not med:
            raise HTTPException(status_code=404, detail=f"El medicamento con ID {med_id} no existe")
        if clinica is not None and med.clinica_id_FK != clinica:
            raise HTTPException(status_code=403, detail=f"El medicamento {med.nombre} no pertenece a tu clínica")
        if (med.tipo_articulo or "medicamento") != "medicamento":
            raise HTTPException(status_code=400, detail=f"«{med.nombre}» es un insumo/equipo y no se puede recetar")
        medicamentos.append(med)

    # Interacciones y alergias (avisos de apoyo)
    interacciones = evaluar_interacciones(db, ids)
    graves = [i for i in interacciones if es_grave(i["severidad"])]
    if graves and not datos.confirmar_interacciones:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "INTERACCION_GRAVE",
                "mensaje": "Se detectaron interacciones graves. Revisa y confirma para continuar.",
                "advertencias_interacciones": interacciones,
            },
        )
    alergias = alertas_alergias(db, paciente.id_PK, medicamentos)

    try:
        consulta = _consulta_para_receta(db, datos, doctor, paciente)

        receta = Receta(
            paciente_id_FK=paciente.id_PK,
            doctor_id_FK=doctor.id_PK,
            consulta_id_FK=consulta.id_PK,
            estado=inv.ESTADO_RECETA_ACTIVA,
        )
        db.add(receta)
        db.flush()

        for it in datos.items:
            db.add(
                ItemReceta(
                    receta_id_FK=receta.id_PK,
                    medicamento_id_FK=it.medicamento_id_FK,
                    dosis=it.dosis,
                    frecuencia=it.frecuencia,
                    duracion=it.duracion,
                    cantidad=it.cantidad,
                    instrucciones=it.instrucciones,
                    via_administracion=it.via_administracion,
                    recargas_permitidas=it.recargas_permitidas,
                    cantidad_dispensada=0,
                )
            )
        db.flush()

        registrar_auditoria(
            db, usuario_actual, "CREAR", "recetas", receta.id_PK, None,
            {
                "paciente_id": paciente.id_PK,
                "consulta_id": consulta.id_PK,
                "medicamentos": ids,
                "interacciones_confirmadas": bool(graves),
            },
            ip=ip_desde_request(request),
            descripcion="Receta creada",
        )
        db.commit()
        db.refresh(receta)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar la receta: {e}")

    detalle = _detalle(db, receta)
    # Si la clínica aún no usa el inventario (sin lotes), no se alerta de «sin existencias»
    inventario_en_uso = (
        db.query(Inventario.id_PK)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .filter(Medicamento.clinica_id_FK == paciente.clinica_id_FK)
        .first()
        is not None
    )
    faltantes = (
        [d for d in detalle["disponibilidad"] if d["estado"] in ("parcial", "no_disponible")]
        if inventario_en_uso
        else []
    )
    mensaje = None
    if faltantes:
        nombres = ", ".join(f"{d['medicamento']} ({d['estado'].replace('_', ' ')})" for d in faltantes)
        mensaje = f"Sin existencias completas en almacén: {nombres}. Informa al paciente."

    return {
        **detalle,
        "advertencias_interacciones": interacciones,
        "alertas_alergias": alergias,
        "hay_faltantes": bool(faltantes),
        "mensaje_disponibilidad": mensaje,
    }


# ------------------------------------------------------------------ consultar
@router.get("/mis-recetas", response_model=list[RecetaDetalle])
def mis_recetas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Recetas del paciente autenticado (app del paciente)."""
    exigir_rol(usuario_actual, [ROL_PACIENTE])
    paciente = paciente_de_usuario(db, usuario_actual)
    if not paciente:
        return []
    recetas = (
        db.query(Receta)
        .filter(Receta.paciente_id_FK == paciente.id_PK, Receta.estado != inv.ESTADO_RECETA_CANCELADA)
        .order_by(Receta.creado_en.desc())
        .all()
    )
    # El paciente ve su receta y el estado; el stock interno no se expone.
    salida = []
    for r in recetas:
        d = _detalle(db, r, con_disponibilidad=False)
        salida.append(d)
    return salida


@router.get("/", response_model=list[RecetaDetalle])
def listar_recetas(
    estado: str | None = Query(None, description="activa | dispensada_parcial | dispensada | cancelada"),
    paciente_id: int | None = Query(None),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Lista recetas según el rol (doctor: las suyas; admin/coord/almacén: de la clínica)."""
    exigir_rol(usuario_actual, [ROL_DOCTOR, ROL_ADMIN, ROL_COORDINADOR, ROL_ALMACEN])

    q = db.query(Receta).join(Paciente, Receta.paciente_id_FK == Paciente.id_PK)
    clinica = clinica_de(usuario_actual)
    if clinica is not None:
        q = q.filter(Paciente.clinica_id_FK == clinica)
    if usuario_actual.rol_id_FK == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario_actual)
        if not doctor:
            return []
        q = q.filter(Receta.doctor_id_FK == doctor.id_PK)
    if estado:
        q = q.filter(Receta.estado == estado)
    if paciente_id:
        q = q.filter(Receta.paciente_id_FK == paciente_id)

    recetas = q.order_by(Receta.creado_en.desc()).limit(limite).all()
    return [_detalle(db, r) for r in recetas]


@router.get("/{receta_id}", response_model=RecetaDetalle)
def obtener_receta(
    receta_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    receta = db.query(Receta).filter(Receta.id_PK == receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    if not _puede_ver_receta(db, usuario_actual, receta):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver esta receta")
    # El paciente no necesita ver existencias internas
    return _detalle(db, receta, con_disponibilidad=usuario_actual.rol_id_FK != ROL_PACIENTE)


@router.get("/{receta_id}/disponibilidad")
def disponibilidad_de_receta(
    receta_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Disponibilidad en inventario de cada medicamento de la receta."""
    exigir_rol(usuario_actual, [ROL_DOCTOR, ROL_ADMIN, ROL_COORDINADOR, ROL_ALMACEN])
    receta = db.query(Receta).filter(Receta.id_PK == receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    if not _puede_ver_receta(db, usuario_actual, receta):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver esta receta")
    items = _items_de(db, receta.id_PK)
    disponibilidad = inv.disponibilidad_receta(db, items)
    return {
        "receta_id": receta.id_PK,
        "estado": receta.estado,
        "todo_disponible": all(d["estado"] in ("disponible", "dispensado") for d in disponibilidad),
        "items": disponibilidad,
    }


# ------------------------------------------------------------------ cancelar
@router.patch("/{receta_id}/cancelar", response_model=RecetaDetalle)
def cancelar_receta(
    receta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_DOCTOR, ROL_ADMIN])
    receta = db.query(Receta).filter(Receta.id_PK == receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    clinica = clinica_de(usuario_actual)
    if clinica is not None and receta.paciente and receta.paciente.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta receta")
    if usuario_actual.rol_id_FK == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario_actual)
        if not doctor or receta.doctor_id_FK != doctor.id_PK:
            raise HTTPException(status_code=403, detail="Solo puedes cancelar tus propias recetas")

    if receta.estado in (inv.ESTADO_RECETA_DISPENSADA, inv.ESTADO_RECETA_PARCIAL):
        raise HTTPException(status_code=409, detail="La receta ya tiene medicamentos dispensados")
    if receta.estado == inv.ESTADO_RECETA_CANCELADA:
        raise HTTPException(status_code=409, detail="La receta ya está cancelada")

    anterior = receta.estado
    receta.estado = inv.ESTADO_RECETA_CANCELADA
    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "recetas", receta.id_PK,
        {"estado": anterior}, {"estado": receta.estado},
        ip=ip_desde_request(request), descripcion="Receta cancelada",
    )
    db.commit()
    db.refresh(receta)
    return _detalle(db, receta)
