from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class AsistenteIARequest(BaseModel):
    sintomas: str = Field(
        ...,
        min_length=5,
        max_length=3000,
        description="Descripción clínica de los síntomas redactados o referidos por el médico",
    )
    incluir_notas_previas: bool = Field(
        default=True,
        description="Indica si se deben considerar las notas iniciales y motivo de la cita médica",
    )


class DiagnosticoSugerido(BaseModel):
    diagnostico: str = Field(..., description="Nombre del diagnóstico clínico propuesto")
    codigo_cie10: Optional[str] = Field(None, description="Código CIE-10 sugerido si aplica")
    probabilidad: Literal["alta", "media", "baja"] = Field(..., description="Nivel de compatibilidad clínica")
    justificacion_clinica: str = Field(..., description="Sustento fisiopatológico según síntomas y antecedentes")


class MedicamentoSugerido(BaseModel):
    nombre_generico: str = Field(..., description="Nombre genérico o principio activo sugerido")
    presentacion_dosis: str = Field(..., description="Dosis y posología sugerida estándar")
    frecuencia: str = Field(..., description="Intervalo de administración")
    duracion_dias: str = Field(..., description="Duración recomendada del esquema")
    justificacion: str = Field(..., description="Indicación terapéutica")
    alerta_alergia: bool = Field(
        ...,
        description="True si el fármaco presenta riesgo directo o reactividad cruzada con las alergias del paciente",
    )
    nivel_riesgo: Literal["seguro", "precaucion", "alto_riesgo", "contraindicado"] = Field(
        default="seguro",
        description="Evaluación de bioseguridad contra el historial de alergias",
    )
    detalle_alergia: Optional[str] = Field(
        None,
        description="Explicación del riesgo alérgico o reactividad cruzada detectada",
    )


class AsistenteIAResponse(BaseModel):
    cita_id: int
    diagnosticos_probables: List[DiagnosticoSugerido]
    medicamentos_sugeridos: List[MedicamentoSugerido]
    observaciones_farmacologicas: Optional[str] = Field(
        None,
        description="Comentarios adicionales sobre interacciones o cuidados generales",
    )
    disclaimer_legal: str = Field(
        default=(
            "HERRAMIENTA DE ASISTENCIA CLÍNICA EXCLUSIVA PARA PROFESIONALES DE LA SALUD. "
            "Este resultado fue generado por un modelo de Inteligencia Artificial como soporte analítico. "
            "No sustituye el juicio clínico, diagnóstico formal ni la prescripción médica facultativa."
        )
    )
    fecha_analisis: datetime = Field(default_factory=datetime.now)
