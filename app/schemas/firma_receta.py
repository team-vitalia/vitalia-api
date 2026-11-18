from pydantic import BaseModel


class FirmarRecetaRequest(BaseModel):
    """El médico debe confirmar de forma explícita que entiende que es una simulación."""
    confirmar: bool = False
    acepto_simulacion: bool = False
