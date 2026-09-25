from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.role import Role


router = APIRouter(
    prefix="/api/roles",
    tags=["Roles"]
)


@router.get("/")
def obtener_roles(
    db: Session = Depends(get_db)
):
    roles = (
        db.query(Role)
        .filter(Role.esta_activo == True)
        .order_by(Role.id_PK)
        .all()
    )

    return [
        {
            "id_PK": rol.id_PK,
            "nombre": rol.nombre,
            "descripcion": rol.descripcion
        }
        for rol in roles
    ]