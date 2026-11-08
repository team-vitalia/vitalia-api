"""Constantes de roles de VITALIA y helpers de autorización.

Los ids coinciden con los sembrados en Alembic (roles 1-5) y con la nueva
migración `h5e8almacen05` (rol 6 = Almacén).
"""
from fastapi import HTTPException, status

ROL_ADMIN = 1
ROL_DOCTOR = 2
ROL_PACIENTE = 3
ROL_RECEPCION = 4
ROL_COORDINADOR = 5
ROL_ALMACEN = 6

NOMBRES_ROL = {
    ROL_ADMIN: "Administrador",
    ROL_DOCTOR: "Doctor",
    ROL_PACIENTE: "Paciente",
    ROL_RECEPCION: "Recepción",
    ROL_COORDINADOR: "Coordinador",
    ROL_ALMACEN: "Almacén",
}


def exigir_rol(usuario, roles: list[int] | tuple[int, ...], detalle: str = "No tienes permiso para esta acción") -> None:
    """Lanza 403 si el rol del usuario no está en `roles`."""
    if getattr(usuario, "rol_id_FK", None) not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detalle)


def clinica_de(usuario) -> int | None:
    """Clínica del usuario (None = sin restricción, p. ej. superadmin)."""
    return getattr(usuario, "clinica_id_FK", None)
