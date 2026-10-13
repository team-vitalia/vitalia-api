from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user
from app.schemas.notificacion import NotificacionResponse, NotificacionesLote

router = APIRouter(
    prefix="/api/notificaciones",
    tags=["Notificaciones"]
)


@router.get("/", response_model=List[NotificacionResponse])
def listar_notificaciones(
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Devuelve el listado de notificaciones asociadas al usuario autenticado, ordenadas cronológicamente."""
    consulta = db.query(Notificacion).filter(
        Notificacion.usuario_id_FK == usuario_actual.id_PK
    )

    if estado and estado != "todos":
        consulta = consulta.filter(Notificacion.estado == estado)

    return consulta.order_by(Notificacion.creado_en.desc()).all()


@router.put("/{notificacion_id}/leer", response_model=NotificacionResponse)
def marcar_como_leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Marca una notificación específica como leída."""
    notif = db.query(Notificacion).filter(
        Notificacion.id_PK == notificacion_id,
        Notificacion.usuario_id_FK == usuario_actual.id_PK
    ).first()

    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )

    notif.estado = "leido"
    notif.leido_en = datetime.now()
    db.commit()
    db.refresh(notif)
    return notif


@router.put("/marcar-todas-leidas")
def marcar_todas_como_leidas(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Marca todas las notificaciones pendientes del usuario autenticado como leídas."""
    db.query(Notificacion).filter(
        Notificacion.usuario_id_FK == usuario_actual.id_PK,
        Notificacion.estado == "no_leido"
    ).update(
        {
            Notificacion.estado: "leido",
            Notificacion.leido_en: datetime.now()
        },
        synchronize_session=False
    )
    db.commit()
    return {"mensaje": "Todas las notificaciones han sido marcadas como leídas"}


@router.post("/marcar-leidas-lote")
def marcar_lote_leidas(
    lote: NotificacionesLote,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Marca un conjunto seleccionado de notificaciones como leídas."""
    if not lote.ids:
        return {"mensaje": "No se enviaron identificadores", "actualizadas": 0}

    actualizadas = db.query(Notificacion).filter(
        Notificacion.id_PK.in_(lote.ids),
        Notificacion.usuario_id_FK == usuario_actual.id_PK
    ).update(
        {
            Notificacion.estado: "leido",
            Notificacion.leido_en: datetime.now()
        },
        synchronize_session=False
    )
    db.commit()
    return {"mensaje": f"{actualizadas} notificaciones marcadas como leídas", "actualizadas": actualizadas}


@router.delete("/{notificacion_id}")
def eliminar_notificacion(
    notificacion_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Elimina permanentemente una notificación del usuario autenticado."""
    notif = db.query(Notificacion).filter(
        Notificacion.id_PK == notificacion_id,
        Notificacion.usuario_id_FK == usuario_actual.id_PK
    ).first()

    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada"
        )

    db.delete(notif)
    db.commit()
    return {"mensaje": f"Notificación #{notificacion_id} eliminada correctamente"}


@router.post("/eliminar-lote")
def eliminar_notificaciones_lote(
    lote: NotificacionesLote,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Elimina en lote una lista de notificaciones seleccionadas."""
    if not lote.ids:
        return {"mensaje": "No se enviaron identificadores", "eliminadas": 0}

    eliminadas = db.query(Notificacion).filter(
        Notificacion.id_PK.in_(lote.ids),
        Notificacion.usuario_id_FK == usuario_actual.id_PK
    ).delete(synchronize_session=False)

    db.commit()
    return {"mensaje": f"{eliminadas} notificaciones eliminadas", "eliminadas": eliminadas}


@router.delete("/limpiar-todas")
def limpiar_todas_notificaciones(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    """Elimina la totalidad de notificaciones del usuario autenticado."""
    eliminadas = db.query(Notificacion).filter(
        Notificacion.usuario_id_FK == usuario_actual.id_PK
    ).delete(synchronize_session=False)

    db.commit()
    return {"mensaje": f"Se eliminaron {eliminadas} notificaciones"}
