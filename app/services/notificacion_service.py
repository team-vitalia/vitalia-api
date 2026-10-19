from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notificacion import Notificacion


class NotificacionService:
    """Servicio de notificaciones (C2).

    Usa los mismos valores de estado que el resto del proyecto
    ("no_leido" / "leido") para ser compatible con los endpoints
    existentes y con citas_notification_service.
    """

    ESTADO_NO_LEIDO = "no_leido"
    ESTADO_LEIDO = "leido"

    def __init__(self, db: Session):
        self.db = db

    def listar_de_usuario(self, usuario_id: int) -> list[Notificacion]:
        return list(
            self.db.scalars(
                select(Notificacion)
                .where(Notificacion.usuario_id_FK == usuario_id)
                .order_by(Notificacion.creado_en.desc())
            ).all()
        )

    def marcar_leida(self, notif_id: int, usuario_id: int) -> Notificacion | None:
        """Marca como leída; valida que la notificación pertenezca al usuario."""
        notif = self.db.get(Notificacion, notif_id)
        if not notif or notif.usuario_id_FK != usuario_id:
            return None
        notif.estado = self.ESTADO_LEIDO
        notif.leido_en = datetime.now()
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def crear(
        self,
        usuario_id: int,
        mensaje: str,
        tipo: str | None = None,
        enlace: str | None = None,
    ) -> Notificacion:
        notif = Notificacion(
            usuario_id_FK=usuario_id,
            mensaje=mensaje,
            tipo=tipo,
            enlace=enlace,
            estado=self.ESTADO_NO_LEIDO,
            creado_en=datetime.now(),
            leido_en=None,
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif
