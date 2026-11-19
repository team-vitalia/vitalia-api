"""Control de acceso por plan de suscripción en el SERVIDOR.

Antes, «Reportes» (plan Profesional) y «Auditoría» (plan Empresarial) solo se bloqueaban en la app:
cualquiera con un plan inferior podía llamar a la API directamente y ver esos datos.
"""
import unicodedata
from typing import Callable

from fastapi import Depends, HTTPException, status

from app.core.dependencies import require_roles
from app.models.usuario import Usuario


def _normalizar(texto: str | None) -> str:
    return unicodedata.normalize("NFD", texto or "").encode("ascii", "ignore").decode().lower().strip()


def require_plan(planes: list[str], roles: list[str], funcion: str) -> Callable:
    """Exige uno de los `roles` y que el plan de la clínica sea uno de `planes`."""
    permitidos = {_normalizar(p) for p in planes}
    requerido = planes[0]

    def _checker(current: Usuario = Depends(require_roles(roles))) -> Usuario:
        clinica = getattr(current, "clinica", None)
        plan = getattr(clinica, "plan", None) if clinica else None
        if _normalizar(getattr(plan, "nombre", None)) not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{funcion} está disponible a partir del plan {requerido}. Actualiza tu suscripción para usarlo.",
            )
        return current

    return _checker
