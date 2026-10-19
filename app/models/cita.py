from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Cita(Base):
    __tablename__ = "citas"

    id_PK: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    paciente_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("pacientes.id_PK")
    )

    doctor_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("doctores.id_PK")
    )

    fecha: Mapped[date | None] = mapped_column(Date)

    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fin: Mapped[time | None] = mapped_column(Time)

    evento_calendario_id: Mapped[int | None] = mapped_column(
        ForeignKey("eventos_calendario.id_PK")
    )

    google_event_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    estado: Mapped[str | None] = mapped_column(
        String(50)
    )

    sala_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("salas.id_PK"), nullable=True
    )

    requiere_equipo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    equipo_id_FK: Mapped[int | None] = mapped_column(
        ForeignKey("equipamiento_sala.id_PK"), nullable=True
    )

    accion_equipo: Mapped[str | None] = mapped_column(Text, nullable=True)

    motivo: Mapped[str | None] = mapped_column(Text)
    notas: Mapped[str | None] = mapped_column(Text)

    creado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_PK")
    )

    paciente = relationship("Paciente")
    doctor = relationship("Doctor")
    evento_calendario = relationship("EventoCalendario")
    usuario_creador = relationship("Usuario")
    sala = relationship("Sala")
    equipo = relationship("EquipamientoSala")

    @property
    def sala_nombre(self) -> str | None:
        return self.sala.nombre if self.sala else None

    @property
    def equipo_nombre(self) -> str | None:
        return self.equipo.nombre_equipo if self.equipo else None

    @property
    def no_realizada(self) -> bool:
        """True si la cita no se llevó a cabo: marcada como no asistió/cancelada
        o con fecha vencida sin haberse completado."""
        estado = (self.estado or "").lower()
        if estado in ("no_asistio", "cancelada"):
            return True
        if estado in ("completada", "en_curso", "atendida"):
            return False
        if self.fecha:
            fin = datetime.combine(self.fecha, self.hora_fin or time.max)
            return fin < datetime.now()
        return False
