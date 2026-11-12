from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import ROL_ADMIN, ROL_DOCTOR, ROL_PACIENTE, exigir_rol
from app.database.connection import get_db
from app.models.alergia import Alergia
from app.models.alergia_paciente import AlergiaPaciente
from app.models.consulta import Consulta
from app.models.historial_medico import HistorialMedico
from app.models.item_receta import ItemReceta
from app.models.paciente import Paciente
from app.models.receta import Receta
from app.models.registro_medico import RegistroMedico
from app.models.transferencia_paciente import TransferenciaPaciente
from app.models.usuario import Usuario
from app.schemas.expediente import (
    AlergiaCatalogoCrear, AlergiaPacienteCrear, AntecedenteCrear, RegistroCrear,
)
from app.services.acceso_clinico import (
    doctor_de_usuario, nombre_completo, paciente_de_usuario, puede_ver_paciente,
)
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar

router = APIRouter(prefix="/api/expediente", tags=["Expediente clínico"])


def _paciente_o_404(db: Session, paciente_id: int) -> Paciente:
    paciente = db.query(Paciente).filter(Paciente.id_PK == paciente_id).first()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return paciente


def _exigir_acceso(db: Session, usuario: Usuario, paciente: Paciente) -> None:
    if not puede_ver_paciente(db, usuario, paciente):
        raise HTTPException(status_code=403, detail="No tienes permiso para ver este expediente")


def _armar(db: Session, paciente: Paciente, *, vista_paciente: bool) -> dict:
    """Arma el expediente. La vista del paciente omite notas internas del médico."""
    antecedentes = (
        db.query(HistorialMedico)
        .filter(HistorialMedico.paciente_id_FK == paciente.id_PK)
        .order_by(HistorialMedico.id_PK.desc())
        .all()
    )
    datos_clinicos = {}
    for a in antecedentes:  # el más reciente que tenga cada dato
        for campo in ("tipo_sangre", "nombre_contacto_emergencia", "telefono_contacto_emergencia", "numero_poliza_seguro"):
            if campo not in datos_clinicos and getattr(a, campo):
                datos_clinicos[campo] = getattr(a, campo)

    alergias = (
        db.query(AlergiaPaciente, Alergia)
        .join(Alergia, AlergiaPaciente.alergia_id_FK == Alergia.id_PK)
        .filter(AlergiaPaciente.paciente_id_FK == paciente.id_PK)
        .all()
    )

    consultas = (
        db.query(Consulta)
        .filter(Consulta.paciente_id_FK == paciente.id_PK)
        .order_by(Consulta.fecha_visita.desc())
        .all()
    )

    recetas = (
        db.query(Receta)
        .filter(Receta.paciente_id_FK == paciente.id_PK, Receta.estado != "cancelada")
        .order_by(Receta.creado_en.desc())
        .all()
    )

    salida = {
        "paciente": {
            "id_PK": paciente.id_PK,
            "nombre_completo": nombre_completo(paciente),
            "fecha_nacimiento": paciente.fecha_nacimiento,
            "genero": paciente.genero,
            "telefono": paciente.telefono,
            "correo_electronico": paciente.correo_electronico,
        },
        "datos_clinicos": datos_clinicos,
        "alergias": [
            {
                "id_PK": ap.id_PK,
                "alergia_id_FK": al.id_PK,
                "nombre": al.nombre,
                "tipo_alergia": al.tipo_alergia,
                "severidad": ap.severidad or al.severidad,
                "fecha_diagnostico": ap.fecha_diagnostico,
                "notas": ap.notas,
            }
            for ap, al in alergias
        ],
        "antecedentes": [
            {
                "id_PK": a.id_PK,
                "descripcion": a.descripcion,
                "diagnostico": a.diagnostico,
                "estado": a.estado,
                "fecha_diagnostico": a.fecha_diagnostico,
                "tratamiento": a.tratamiento,
                "doctor": a.doctor.nombre if a.doctor else None,
            }
            for a in antecedentes
            if a.descripcion or a.diagnostico or a.tratamiento
        ],
        "consultas": [
            {
                "id_PK": c.id_PK,
                "fecha_visita": c.fecha_visita,
                "doctor": c.doctor.nombre if c.doctor else None,
                "diagnostico": c.diagnostico,
                "tratamiento": c.tratamiento,
                "codigo_cie10": c.codigo_cie10,
                "signos_vitales": c.signos_vitales,
                "fecha_proxima_cita": c.fecha_proxima_cita,
                # Las notas internas solo las ve el personal clínico
                **({} if vista_paciente else {"notas": c.notas, "cita_id_FK": c.cita_id_FK}),
            }
            for c in consultas
        ],
        # 👇 AQUÍ ESTÁ EL CAMBIO: Ahora devuelve "items" con el detalle completo 👇
        "recetas": [
            {
                "id_PK": r.id_PK,
                "estado": r.estado,
                "creado_en": r.creado_en,
                "doctor": r.doctor.nombre if r.doctor else None,
                "items": [
                    {
                        "id_PK": it.id_PK,
                        "medicamento": it.medicamento.nombre if it.medicamento else None,
                        "presentacion": it.medicamento.presentacion if it.medicamento else None,
                        "dosis": it.dosis,
                        "frecuencia": it.frecuencia,
                        "duracion": it.duracion,
                        "cantidad": it.cantidad,
                        "instrucciones": it.instrucciones,
                        "via_administracion": it.via_administracion,
                    }
                    for it in db.query(ItemReceta).filter(ItemReceta.receta_id_FK == r.id_PK).all()
                ],
            }
            for r in recetas
        ],
    }

    if not vista_paciente:
        registros = (
            db.query(RegistroMedico)
            .filter(RegistroMedico.paciente_id_FK == paciente.id_PK)
            .order_by(RegistroMedico.creado_en.desc())
            .all()
        )
        transferencias = (
            db.query(TransferenciaPaciente)
            .filter(TransferenciaPaciente.paciente_id_FK == paciente.id_PK)
            .order_by(TransferenciaPaciente.creado_en.desc())
            .all()
        )
        salida["registros"] = [
            {
                "id_PK": r.id_PK,
                "tipo_registro": r.tipo_registro,
                "notas_generales": r.notas_generales,
                "creado_en": r.creado_en,
                "doctor": r.doctor.nombre if r.doctor else None,
                "url_adjunto": r.url_adjunto,
            }
            for r in registros
        ]
        salida["transferencias"] = [
            {
                "id_PK": t.id_PK,
                "de": t.doctor_origen.nombre if t.doctor_origen else None,
                "a": t.doctor_destino.nombre if t.doctor_destino else None,
                "motivo": t.motivo,
                "creado_en": t.creado_en,
            }
            for t in transferencias
        ]
    return salida


# ------------------------------------------------------------------ lectura
@router.get("/mi-expediente")
def mi_expediente(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Expediente del paciente autenticado (información autorizada)."""
    exigir_rol(usuario_actual, [ROL_PACIENTE])
    paciente = paciente_de_usuario(db, usuario_actual)
    if not paciente:
        raise HTTPException(status_code=404, detail="No tienes un perfil de paciente asociado")
    return _armar(db, paciente, vista_paciente=True)


@router.get("/alergias/catalogo")
def catalogo_alergias(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_DOCTOR, 4, 5])
    return [
        {"id_PK": a.id_PK, "nombre": a.nombre, "tipo_alergia": a.tipo_alergia, "severidad": a.severidad}
        for a in db.query(Alergia).order_by(Alergia.nombre).all()
    ]


@router.get("/paciente/{paciente_id}")
def expediente_de_paciente(
    paciente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = _paciente_o_404(db, paciente_id)
    _exigir_acceso(db, usuario_actual, paciente)
    vista_paciente = usuario_actual.rol_id_FK == ROL_PACIENTE

    if not vista_paciente:  # trazabilidad de accesos al expediente
        registrar_auditoria(
            db, usuario_actual, "CONSULTAR", "expediente", paciente.id_PK, None, None,
            ip=ip_desde_request(request), descripcion="Consulta de expediente clínico",
        )
        db.commit()
    return _armar(db, paciente, vista_paciente=vista_paciente)


# ------------------------------------------------------------------ escritura
def _exigir_clinico(db: Session, usuario: Usuario, paciente: Paciente) -> None:
    exigir_rol(usuario, [ROL_DOCTOR, ROL_ADMIN], "Solo personal médico puede modificar el expediente")
    _exigir_acceso(db, usuario, paciente)


@router.post("/paciente/{paciente_id}/antecedentes", status_code=status.HTTP_201_CREATED)
def agregar_antecedente(
    paciente_id: int,
    datos: AntecedenteCrear,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = _paciente_o_404(db, paciente_id)
    _exigir_clinico(db, usuario_actual, paciente)
    if not any(v for v in datos.model_dump().values()):
        raise HTTPException(status_code=422, detail="Captura al menos un dato")

    doctor = doctor_de_usuario(db, usuario_actual)
    registro = HistorialMedico(
        paciente_id_FK=paciente.id_PK,
        doctor_id_FK=doctor.id_PK if doctor else None,
        **datos.model_dump(),
    )
    db.add(registro)
    db.flush()
    registrar_auditoria(
        db, usuario_actual, "CREAR", "historial_medico", registro.id_PK, None,
        serializar(datos.model_dump()), ip=ip_desde_request(request),
        descripcion="Antecedente agregado al expediente",
    )
    db.commit()
    return {"id_PK": registro.id_PK, "mensaje": "Antecedente registrado"}


@router.post("/paciente/{paciente_id}/registros", status_code=status.HTTP_201_CREATED)
def agregar_registro(
    paciente_id: int,
    datos: RegistroCrear,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = _paciente_o_404(db, paciente_id)
    _exigir_clinico(db, usuario_actual, paciente)
    doctor = doctor_de_usuario(db, usuario_actual)
    registro = RegistroMedico(
        paciente_id_FK=paciente.id_PK,
        doctor_id_FK=doctor.id_PK if doctor else None,
        **datos.model_dump(),
    )
    db.add(registro)
    db.flush()
    registrar_auditoria(
        db, usuario_actual, "CREAR", "registros_medicos", registro.id_PK, None,
        {"tipo_registro": datos.tipo_registro}, ip=ip_desde_request(request),
        descripcion="Nota agregada al expediente",
    )
    db.commit()
    return {"id_PK": registro.id_PK, "mensaje": "Registro agregado"}


@router.post("/alergias/catalogo", status_code=status.HTTP_201_CREATED)
def crear_alergia_catalogo(
    datos: AlergiaCatalogoCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_DOCTOR])
    existente = db.query(Alergia).filter(Alergia.nombre.ilike(datos.nombre.strip())).first()
    if existente:
        raise HTTPException(status_code=409, detail="Esa alergia ya existe en el catálogo")
    alergia = Alergia(**{**datos.model_dump(), "nombre": datos.nombre.strip()})
    db.add(alergia)
    db.commit()
    db.refresh(alergia)
    return {"id_PK": alergia.id_PK, "nombre": alergia.nombre}


@router.post("/paciente/{paciente_id}/alergias", status_code=status.HTTP_201_CREATED)
def asignar_alergia(
    paciente_id: int,
    datos: AlergiaPacienteCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = _paciente_o_404(db, paciente_id)
    _exigir_clinico(db, usuario_actual, paciente)
    if not db.query(Alergia).filter(Alergia.id_PK == datos.alergia_id_FK).first():
        raise HTTPException(status_code=404, detail="La alergia no existe en el catálogo")
    if db.query(AlergiaPaciente).filter(
        AlergiaPaciente.paciente_id_FK == paciente.id_PK,
        AlergiaPaciente.alergia_id_FK == datos.alergia_id_FK,
    ).first():
        raise HTTPException(status_code=409, detail="El paciente ya tiene registrada esta alergia")
    ap = AlergiaPaciente(paciente_id_FK=paciente.id_PK, **datos.model_dump())
    db.add(ap)
    db.commit()
    db.refresh(ap)
    return {"id_PK": ap.id_PK, "mensaje": "Alergia registrada"}


@router.delete("/paciente/{paciente_id}/alergias/{alergia_paciente_id}")
def quitar_alergia(
    paciente_id: int,
    alergia_paciente_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    paciente = _paciente_o_404(db, paciente_id)
    _exigir_clinico(db, usuario_actual, paciente)
    ap = db.query(AlergiaPaciente).filter(
        AlergiaPaciente.id_PK == alergia_paciente_id,
        AlergiaPaciente.paciente_id_FK == paciente.id_PK,
    ).first()
    if not ap:
        raise HTTPException(status_code=404, detail="Alergia del paciente no encontrada")
    db.delete(ap)
    db.commit()
    return {"mensaje": "Alergia eliminada del expediente"}