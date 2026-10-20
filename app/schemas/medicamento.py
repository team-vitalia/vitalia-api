from pydantic import BaseModel, ConfigDict

class MedicamentoResponse(BaseModel):
    id_PK: int
    nombre: str
    presentacion: str | None = None
    requiere_receta: bool | None = None
    stock_actual: int = 0  # 👈 AGREGA ESTA LÍNEA

    model_config = ConfigDict(from_attributes=True)