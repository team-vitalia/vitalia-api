from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.dependencies import get_current_user
from app.models.usuario import Usuario
from app.models.doctor import Doctor
from app.models.receta import Receta
from app.models.item_receta import ItemReceta
from app.models.medicamento import Medicamento
from app.schemas.receta import RecetaCrear, RecetaResponse

router = APIRouter(prefix="/api/recetas", tags=["Recetas"])

@router.post("/", response_model=RecetaResponse, status_code=status.HTTP_201_CREATED)
def crear_receta(
    datos: RecetaCrear,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    # 1. Validar que sea médico
    if usuario_actual.rol_id_FK != 2:
        raise HTTPException(status_code=403, detail="Solo los médicos pueden recetar")

    doctor = db.query(Doctor).filter(Doctor.usuario_id_FK == usuario_actual.id_PK).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Perfil de médico no encontrado")

    # 2. Validar que los medicamentos existan
    for item in datos.items:
        med = db.query(Medicamento).filter(Medicamento.id_PK == item.medicamento_id_FK).first()
        if not med:
            raise HTTPException(
                status_code=404, 
                detail=f"El medicamento con ID {item.medicamento_id_FK} no existe"
            )

    try:
        # 3. Crear la cabecera de la receta
        nueva_receta = Receta(
            paciente_id_FK=datos.paciente_id_FK,
            doctor_id_FK=doctor.id_PK,
            consulta_id_FK=datos.consulta_id_FK,
            estado="activa"
        )
        db.add(nueva_receta)
        db.flush() # Para obtener el ID de la receta

        # 4. Guardar los medicamentos (items)
        for item in datos.items:
            nuevo_item = ItemReceta(
                receta_id_FK=nueva_receta.id_PK,
                medicamento_id_FK=item.medicamento_id_FK,
                dosis=item.dosis,
                frecuencia=item.frecuencia,
                duracion=item.duracion,
                cantidad=item.cantidad,
                instrucciones=item.instrucciones,
                via_administracion=item.via_administracion,
                recargas_permitidas=item.recargas_permitidas
            )
            db.add(nuevo_item)

        db.commit()
        db.refresh(nueva_receta)
        return nueva_receta

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Error al guardar la receta: {str(e)}"
        )