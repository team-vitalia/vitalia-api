from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.cita import Cita
from app.models.doctor import Doctor
from app.models.usuario import Usuario
from app.schemas.asistente_ia import AsistenteIARequest, AsistenteIAResponse
from app.services.groq_service import GroqClinicalService
from app.utils.auditoria import ip_desde_request, registrar_auditoria

router = APIRouter(prefix="/api/citas", tags=["Asistente Médico IA"])


@router.post(
    "/{cita_id}/asistente-ia",
    response_model=AsistenteIAResponse,
    status_code=status.HTTP_200_OK,
)
async def consultar_asistente_ia(
    cita_id: int,
    payload: AsistenteIARequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """
    Invoca el asistente clínico Groq para una cita médica activa.
    Restringido al médico tratante asignado a la cita (rol 2) o Administrador (rol 1).
    """
    if usuario_actual.rol_id_FK not in [1, 2]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los médicos tienen autorización para consultar el Asistente Clínico IA.",
        )

    cita = db.query(Cita).filter(Cita.id_PK == cita_id).first()
    if not cita:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cita no encontrada",
        )

    if usuario_actual.rol_id_FK == 2:
        doctor = (
            db.query(Doctor)
            .filter(Doctor.usuario_id_FK == usuario_actual.id_PK)
            .first()
        )
        if not doctor or cita.doctor_id_FK != doctor.id_PK:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder al asistente en una cita asignada a otro médico.",
            )

    servicio_groq = GroqClinicalService(db)
    respuesta_ia = await servicio_groq.consultar_asistente_clinico(
        cita=cita,
        sintomas=payload.sintomas,
        incluir_notas=payload.incluir_notas_previas,
    )

    # TRAZABILIDAD Y AUDITORÍA SIN ALMACENAR DATOS SENSIBLES
    total_alertas_alergia = sum(
        1 for m in respuesta_ia.medicamentos_sugeridos if m.alerta_alergia
    )

    metadata_auditoria = {
        "modulo": "asistente_ia_groq",
        "cita_id": cita_id,
        "doctor_usuario_id": usuario_actual.id_PK,
        "total_diagnosticos_propuestos": len(respuesta_ia.diagnosticos_probables),
        "total_medicamentos_propuestos": len(respuesta_ia.medicamentos_sugeridos),
        "alertas_alergias_detectadas": total_alertas_alergia,
        "fecha_ejecucion": datetime.now().isoformat(),
    }

    registrar_auditoria(
        db=db,
        usuario=usuario_actual,
        accion="CONSULTA_ASISTENTE_IA",
        tabla="citas",
        id_registro=cita_id,
        antiguos=None,
        nuevos=metadata_auditoria,
        ip=ip_desde_request(request),
        descripcion=(
            f"Uso de soporte IA en consulta #{cita_id}. "
            f"Se detectaron {total_alertas_alergia} advertencias farmacológicas."
        ),
    )
    db.commit()

    return respuesta_ia
