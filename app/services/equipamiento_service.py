from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.cita import Cita
from app.models.equipamiento_sala import EquipamientoSala
from app.models.sala import Sala
from app.models.usuario import Usuario
from app.schemas.equipamiento import EquipamientoUpdate, validar_fechas_equipo
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar
from app.utils.textos_auditoria import frase_cambios


def _columnas(obj) -> dict:
    return serializar({c.name: getattr(obj, c.name) for c in obj.__table__.columns})


class EquipamientoService:
    def __init__(self, db: Session, clinica_id: int | None = None):
        self.db = db
        self.clinica_id = clinica_id

    def obtener(self, equipo_id: int) -> EquipamientoSala | None:
        """Devuelve el equipo solo si su sala es de la clínica del usuario (aislamiento entre clínicas)."""
        equipo = self.db.get(EquipamientoSala, equipo_id)
        if not equipo:
            return None
        if self.clinica_id is not None:
            sala = self.db.get(Sala, equipo.sala_id_FK) if equipo.sala_id_FK else None
            if not sala or sala.clinica_id_FK != self.clinica_id:
                return None
        return equipo

    def _sala_nombre(self, equipo: EquipamientoSala) -> str:
        sala = self.db.get(Sala, equipo.sala_id_FK) if equipo.sala_id_FK else None
        return sala.nombre if sala else "sin sala"

    def actualizar(
        self, equipo_id: int, payload: EquipamientoUpdate, usuario: Usuario, request: Request
    ) -> EquipamientoSala | None:
        equipo = self.obtener(equipo_id)
        if not equipo:
            return None

        cambios = payload.model_dump(exclude_unset=True)
        if "nombre_equipo" in cambios and not (cambios["nombre_equipo"] or "").strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El nombre del equipo no puede quedar vacío.")

        # CORREGIDO: al editar no se validaban las fechas (solo al crear)
        try:
            validar_fechas_equipo(
                cambios.get("fecha_compra", equipo.fecha_compra),
                cambios.get("ultimo_mantenimiento", equipo.ultimo_mantenimiento),
                cambios.get("proximo_mantenimiento", equipo.proximo_mantenimiento),
            )
        except ValueError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

        if "numero_serie" in cambios:
            serie = (cambios["numero_serie"] or "").strip() or None
            cambios["numero_serie"] = serie
            if serie:
                consulta = self.db.query(EquipamientoSala).filter(
                    EquipamientoSala.numero_serie == serie, EquipamientoSala.id_PK != equipo.id_PK
                )
                if self.clinica_id is not None:
                    consulta = consulta.join(Sala, Sala.id_PK == EquipamientoSala.sala_id_FK).filter(
                        Sala.clinica_id_FK == self.clinica_id
                    )
                if consulta.first():
                    raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un equipo con el número de serie «{serie}».")

        antes = _columnas(equipo)
        for k, v in cambios.items():
            setattr(equipo, k, v)
        self.db.flush()
        despues = _columnas(equipo)

        registrar_auditoria(
            db=self.db, usuario=usuario, accion="UPDATE", tabla="equipamiento_sala", id_registro=equipo.id_PK,
            antiguos=antes, nuevos=despues, ip=ip_desde_request(request),
            descripcion=(
                f"Se modificó el equipo «{equipo.nombre_equipo}» de la sala «{self._sala_nombre(equipo)}»: "
                f"{frase_cambios(antes, despues)}"
            ),
        )
        self.db.commit()
        self.db.refresh(equipo)
        return equipo

    def eliminar(self, equipo_id: int, usuario: Usuario, request: Request) -> bool:
        equipo = self.obtener(equipo_id)
        if not equipo:
            return False

        # CORREGIDO: si una cita usaba este equipo la base devolvía error 500
        en_citas = self.db.query(Cita).filter(Cita.equipo_id_FK == equipo.id_PK).count()
        if en_citas:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"No se puede eliminar «{equipo.nombre_equipo}» porque está ligado a {en_citas} cita(s). "
                "Cámbialo a «Fuera de servicio» para conservar el historial.",
            )

        antes = _columnas(equipo)
        nombre, sala = equipo.nombre_equipo, self._sala_nombre(equipo)
        self.db.delete(equipo)
        registrar_auditoria(
            db=self.db, usuario=usuario, accion="DELETE", tabla="equipamiento_sala", id_registro=equipo_id,
            antiguos=antes, nuevos=None, ip=ip_desde_request(request),
            descripcion=f"Se eliminó el equipo «{nombre}» de la sala «{sala}»",
        )
        self.db.commit()
        return True
