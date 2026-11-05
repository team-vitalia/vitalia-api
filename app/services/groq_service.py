import json
import logging
from datetime import date
from typing import Any, Dict
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.alergia_paciente import AlergiaPaciente
from app.models.cita import Cita
from app.models.paciente import Paciente
from app.schemas.asistente_ia import AsistenteIAResponse

logger = logging.getLogger("vitalia.asistente_ia")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _calcular_edad(fecha_nacimiento: date | None) -> int | None:
    if not fecha_nacimiento:
        return None
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


class GroqClinicalService:
    def __init__(self, db: Session):
        self.db = db

    def construir_payload_anonimo(
        self,
        cita: Cita,
        sintomas_doctor: str,
        incluir_notas: bool
    ) -> Dict[str, Any]:
        """
        REGLA CRÍTICA DE PRIVACIDAD:
        Construye un payload clínico despojado de Identificadores Personales Directos (PII/PHI).
        PROHIBIDO: Nombres, Apellidos, CURP, RFC, Teléfono, Dirección, Correo Electrónico, IDs de BD.
        PERMITIDO: Edad, Sexo Biológico, Alergias registradas, Síntomas redactados y antecedentes clínicos.
        """
        paciente: Paciente = cita.paciente
        if not paciente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El paciente asociado a la cita no existe"
            )

        edad = _calcular_edad(paciente.fecha_nacimiento)
        sexo = paciente.genero or "No especificado"

        alergias_db = (
            self.db.query(AlergiaPaciente)
            .options(joinedload(AlergiaPaciente.alergia))
            .filter(AlergiaPaciente.paciente_id_FK == paciente.id_PK)
            .all()
        )

        lista_alergias = []
        for ap in alergias_db:
            nombre_alergia = ap.alergia.nombre if ap.alergia else "Alergia no clasificada"
            lista_alergias.append({
                "sustancia_alergeno": nombre_alergia,
                "severidad": ap.severidad or "desconocida",
                "notas_reaccion": ap.notas or "sin notas"
            })

        historial_contextual = ""
        if incluir_notas and cita.notas:
            historial_contextual = cita.notas

        return {
            "perfil_paciente_anonimizado": {
                "edad_en_anos": edad,
                "sexo_biologico": sexo,
                "alergias_conocidas": lista_alergias
            },
            "contexto_consulta": {
                "sintomas_actuales": sintomas_doctor,
                "motivo_consulta": cita.motivo or "No especificado",
                "notas_clinicas_previas": historial_contextual
            }
        }

    async def consultar_asistente_clinico(
        self,
        cita: Cita,
        sintomas: str,
        incluir_notas: bool
    ) -> AsistenteIAResponse:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            logger.error("GROQ_API_KEY no está configurada en settings ni en .env.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="El servicio de Asistente IA no se encuentra configurado en el servidor."
            )

        payload_clinico = self.construir_payload_anonimo(cita, sintomas, incluir_notas)

        system_prompt = (
            "Eres el Asistente Clínico de Soporte al Diagnóstico de VITALIA, un sistema hospitalario.\n"
            "Tu objetivo es asistir al médico tratante proporcionando diagnósticos diferenciales razonados y sugerencias terapéuticas.\n\n"
            "PROTOCOLO CRÍTICO DE SEGURIDAD FARMACOLÓGICA (OBLIGATORIO):\n"
            "1. Revisa minuciosamente la lista 'alergias_conocidas' del paciente.\n"
            "2. Por CADA medicamento que sugieras, evalúa si el paciente es alérgico a él, a su familia farmacológica o a sus excipientes comunes (ej. Penicilinas/Cefalosporinas, AINEs/Ácido Acetilsalicílico, Sulfas, Macrólidos).\n"
            "3. Si existe riesgo alérgico o reactividad cruzada:\n"
            "   - 'alerta_alergia' DEBE SER true.\n"
            "   - 'nivel_riesgo' DEBE SER 'contraindicado' o 'alto_riesgo'.\n"
            "   - En 'detalle_alergia' explica con precisión el riesgo (ej. 'Contraindicado: Paciente con alergia previa a Penicilinas').\n"
            "4. Si es completamente seguro:\n"
            "   - 'alerta_alergia' DEBE SER false.\n"
            "   - 'nivel_riesgo' DEBE SER 'seguro'.\n"
            "   - 'detalle_alergia' DEBE SER null.\n\n"
            "FORMATO DE SALIDA:\n"
            "Debes responder EXCLUSIVAMENTE con un documento JSON válido con la siguiente estructura exacta:\n"
            "{\n"
            '  "diagnosticos_probables": [\n'
            '    {\n'
            '      "diagnostico": "Nombre diagnóstico",\n'
            '      "codigo_cie10": "A00.0",\n'
            '      "probabilidad": "alta" | "media" | "baja",\n'
            '      "justificacion_clinica": "Explicación breve"\n'
            '    }\n'
            '  ],\n'
            '  "medicamentos_sugeridos": [\n'
            '    {\n'
            '      "nombre_generico": "Nombre Fármaco",\n'
            '      "presentacion_dosis": "500 mg",\n'
            '      "frecuencia": "Cada 8 horas",\n'
            '      "duracion_dias": "7 días",\n'
            '      "justificacion": "Motivo",\n'
            '      "alerta_alergia": true | false,\n'
            '      "nivel_riesgo": "seguro" | "precaucion" | "alto_riesgo" | "contraindicado",\n'
            '      "detalle_alergia": "Motivo de la alerta o null"\n'
            '    }\n'
            '  ],\n'
            '  "observaciones_farmacologicas": "Comentarios adicionales o precauciones"\n'
            "}"
        )

        user_content = json.dumps(payload_clinico, ensure_ascii=False)

        # Modelos candidatos con fallback automático
        candidate_models = []
        if settings.GROQ_MODEL:
            candidate_models.append(settings.GROQ_MODEL)
        for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        ultimo_error = None
        for model_name in candidate_models:
            request_body = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }

            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    res = await client.post(
                        GROQ_API_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json=request_body
                    )

                if res.status_code == 200:
                    data = res.json()
                    raw_content = data["choices"][0]["message"]["content"]
                    parsed_json = json.loads(raw_content)

                    return AsistenteIAResponse(
                        cita_id=cita.id_PK,
                        diagnosticos_probables=parsed_json.get("diagnosticos_probables", []),
                        medicamentos_sugeridos=parsed_json.get("medicamentos_sugeridos", []),
                        observaciones_farmacologicas=parsed_json.get("observaciones_farmacologicas")
                    )
                else:
                    logger.warning("Modelo Groq '%s' falló con HTTP %s: %s", model_name, res.status_code, res.text)
                    ultimo_error = f"Groq HTTP {res.status_code}: {res.text}"
                    continue

            except httpx.TimeoutException:
                logger.warning("Timeout con modelo Groq '%s'", model_name)
                ultimo_error = "Tiempo de espera agotado al consultar Groq."
                continue
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Error al decodificar respuesta JSON de Groq (%s): %s", model_name, e)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="La respuesta del asistente de inteligencia artificial no tuvo la estructura clínica esperada."
                )

        logger.error("Todos los modelos de Groq fallaron. Último error: %s", ultimo_error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con el proveedor de IA (Groq): {ultimo_error or 'Servicio no disponible'}"
        )
