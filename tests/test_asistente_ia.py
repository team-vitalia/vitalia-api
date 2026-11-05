"""
Pruebas unitarias para el Asistente Médico IA (Groq).
Verifica:
1. Control de acceso RBAC (Solo doctor asignado o administrador).
2. Anonimización estricta del payload clínico (Sin nombres, CURP, teléfono, etc.).
3. Extracción de alergias y detección de advertencias farmacológicas.
4. Trazabilidad en registros_auditoria sin almacenamiento de datos sensibles.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.usuario import Usuario
from app.models.doctor import Doctor
from app.models.paciente import Paciente
from app.models.alergia import Alergia
from app.models.alergia_paciente import AlergiaPaciente
from app.models.cita import Cita
from app.services.groq_service import GroqClinicalService

client = TestClient(app)


def _crear_usuario(id_pk: int, rol_id: int, nombre="Usuario Test"):
    return Usuario(
        id_PK=id_pk,
        nombre=nombre,
        correo_electronico=f"user{id_pk}@vitalia.com",
        hash_contrasena="hash",
        rol_id_FK=rol_id,
        estado="activo",
    )


def test_anonimizacion_estricta_payload():
    """Verifica que el payload enviado a Groq no contenga PII (nombres, curp, etc.)."""
    db_mock = MagicMock()

    paciente = Paciente(
        id_PK=10,
        nombre="Juan Carlos",
        apellido="Pérez Gómez",
        apellido_paterno="Pérez",
        apellido_materno="Gómez",
        curp="PEPJ800101HDFRRN01",
        telefono="5512345678",
        direccion="Av. Siempre Viva 123, CDMX",
        correo_electronico="juan.perez@privado.com",
        fecha_nacimiento=date(1990, 5, 15),
        genero="Masculino",
        estado="activo",
    )

    alergia = Alergia(id_PK=1, nombre="Penicilina", severidad="Grave")
    alergia_paciente = AlergiaPaciente(
        id_PK=1,
        paciente_id_FK=10,
        alergia_id_FK=1,
        severidad="Grave",
        notas="Anafilaxia previa",
    )
    alergia_paciente.alergia = alergia

    cita = Cita(
        id_PK=50,
        paciente_id_FK=10,
        doctor_id_FK=5,
        fecha=date.today(),
        motivo="Fiebre y dolor de garganta",
        notas="Faringitis recurrente",
    )
    cita.paciente = paciente

    db_mock.query().options().filter().all.return_value = [alergia_paciente]

    servicio = GroqClinicalService(db_mock)
    payload = servicio.construir_payload_anonimo(
        cita=cita,
        sintomas_doctor="Odinofagia severa y placas blanquecinas",
        incluir_notas=True,
    )

    perfil = payload["perfil_paciente_anonimizado"]
    contexto = payload["contexto_consulta"]

    # No debe existir ninguna PII
    str_payload = str(payload).lower()
    assert "juan" not in str_payload
    assert "carlos" not in str_payload
    assert "pérez" not in str_payload
    assert "perez" not in str_payload
    assert "pepj800101hdfrrn01" not in str_payload
    assert "5512345678" not in str_payload
    assert "siempre viva" not in str_payload
    assert "juan.perez@privado.com" not in str_payload

    # Debe incluir datos clínicos autorizados
    assert perfil["edad_en_anos"] is not None
    assert perfil["edad_en_anos"] > 0
    assert perfil["sexo_biologico"] == "Masculino"
    assert len(perfil["alergias_conocidas"]) == 1
    assert perfil["alergias_conocidas"][0]["sustancia_alergeno"] == "Penicilina"
    assert contexto["sintomas_actuales"] == "Odinofagia severa y placas blanquecinas"
    assert contexto["motivo_consulta"] == "Fiebre y dolor de garganta"


def test_asistente_ia_prohibido_para_paciente_o_recepcion():
    """Un paciente o personal de recepción no puede invocar el asistente."""
    usuario_paciente = _crear_usuario(id_pk=30, rol_id=3)
    app.dependency_overrides[get_current_user] = lambda: usuario_paciente

    try:
        response = client.post(
            "/api/citas/50/asistente-ia",
            json={"sintomas": "Dolor de cabeza intenso"},
        )
        assert response.status_code == 403
        assert "Solo los médicos" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_asistente_ia_prohibido_para_doctor_no_asignado():
    """Un médico no puede consultar el asistente para una cita asignada a otro médico."""
    doctor_usuario = _crear_usuario(id_pk=15, rol_id=2)
    doctor_perfil = Doctor(id_PK=2, usuario_id_FK=15)

    cita_otro_doctor = Cita(
        id_PK=80,
        paciente_id_FK=10,
        doctor_id_FK=99,
        fecha=date.today(),
        estado="programada",
    )

    db_mock = MagicMock()

    def _query_side_effect(modelo):
        mock_q = MagicMock()
        if modelo == Cita:
            mock_q.filter().first.return_value = cita_otro_doctor
        elif modelo == Doctor:
            mock_q.filter().first.return_value = doctor_perfil
        return mock_q

    db_mock.query.side_effect = _query_side_effect

    app.dependency_overrides[get_current_user] = lambda: doctor_usuario
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        response = client.post(
            "/api/citas/80/asistente-ia",
            json={"sintomas": "Fiebre persistente"},
        )
        assert response.status_code == 403
        assert "asignada a otro médico" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_asistente_ia_flujo_exitoso_y_auditoria():
    """Flujo exitoso que valida respuesta de Groq y registro en auditoría."""
    doctor_usuario = _crear_usuario(id_pk=20, rol_id=2)
    doctor_perfil = Doctor(id_PK=5, usuario_id_FK=20)

    paciente = Paciente(
        id_PK=10,
        nombre="Paciente",
        apellido="Prueba",
        fecha_nacimiento=date(1995, 1, 1),
        genero="Femenino",
    )

    cita = Cita(
        id_PK=90,
        paciente_id_FK=10,
        doctor_id_FK=5,
        fecha=date.today(),
        estado="programada",
        motivo="Infección respiratoria",
        notas=None,
    )
    cita.paciente = paciente

    db_mock = MagicMock()

    def _query_side_effect(modelo):
        mock_q = MagicMock()
        if modelo == Cita:
            mock_q.filter().first.return_value = cita
        elif modelo == Doctor:
            mock_q.filter().first.return_value = doctor_perfil
        return mock_q

    db_mock.query.side_effect = _query_side_effect

    mock_respuesta_groq = {
        "diagnosticos_probables": [
            {
                "diagnostico": "Faringoamigdalitis estreptocócica",
                "codigo_cie10": "J02.0",
                "probabilidad": "alta",
                "justificacion_clinica": "Compatible con cuadro febril agudo y odinofagia",
            }
        ],
        "medicamentos_sugeridos": [
            {
                "nombre_generico": "Amoxicilina",
                "presentacion_dosis": "500 mg",
                "frecuencia": "Cada 8 horas",
                "duracion_dias": "7 días",
                "justificacion": "Antibiótico de primera línea",
                "alerta_alergia": True,
                "nivel_riesgo": "contraindicado",
                "detalle_alergia": "Contraindicado por alergia reportada a betalactámicos",
            }
        ],
        "observaciones_farmacologicas": "Considerar macrólido alternativo (ej. Claritromicina).",
    }

    app.dependency_overrides[get_current_user] = lambda: doctor_usuario
    app.dependency_overrides[get_db] = lambda: db_mock

    with patch.object(
        GroqClinicalService,
        "consultar_asistente_clinico",
        new_callable=AsyncMock,
    ) as mock_groq, patch(
        "app.routers.asistente_ia.registrar_auditoria"
    ) as mock_auditoria:
        from app.schemas.asistente_ia import AsistenteIAResponse

        mock_groq.return_value = AsistenteIAResponse(
            cita_id=90,
            diagnosticos_probables=mock_respuesta_groq["diagnosticos_probables"],
            medicamentos_sugeridos=mock_respuesta_groq["medicamentos_sugeridos"],
            observaciones_farmacologicas=mock_respuesta_groq[
                "observaciones_farmacologicas"
            ],
        )

        try:
            response = client.post(
                "/api/citas/90/asistente-ia",
                json={"sintomas": "Odinofagia severa y fiebre de 39 grados"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["cita_id"] == 90
            assert len(data["diagnosticos_probables"]) == 1
            assert data["medicamentos_sugeridos"][0]["alerta_alergia"] is True
            assert (
                data["medicamentos_sugeridos"][0]["nivel_riesgo"]
                == "contraindicado"
            )

            # Verificar que se llamó a registrar_auditoria con metadata SIN PII
            assert mock_auditoria.called
            _, kwargs = mock_auditoria.call_args
            assert kwargs["accion"] == "CONSULTA_ASISTENTE_IA"
            assert kwargs["tabla"] == "citas"
            assert kwargs["id_registro"] == 90
            nuevos = kwargs["nuevos"]
            # Debe registrar métricas numéricas sin almacenar diagnósticos ni síntomas
            assert "total_diagnosticos_propuestos" in nuevos
            assert "alertas_alergias_detectadas" in nuevos
            assert nuevos["alertas_alergias_detectadas"] == 1
            assert "sintomas" not in nuevos
            assert "diagnosticos" not in nuevos

        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
