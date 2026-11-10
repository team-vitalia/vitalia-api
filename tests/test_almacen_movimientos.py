from datetime import date

from app.core.security import crear_access_token
from app.models.inventario import Inventario
from app.models.medicamento import Medicamento
from app.models.usuario import Usuario


def crear_usuario_almacen(db_session, clinica_id: int = 10) -> dict[str, str]:
    usuario = Usuario(
        id_PK=31,
        clinica_id_FK=clinica_id,
        nombre="Almacenista",
        correo_electronico="almacen@sanitas.com",
        hash_contrasena="hash",
        rol_id_FK=6,
        estado="activo",
    )
    db_session.add(usuario)
    db_session.commit()
    token = crear_access_token(
        data={
            "sub": str(usuario.id_PK),
            "correo": usuario.correo_electronico,
            "rol_id": usuario.rol_id_FK,
            "clinica_id": clinica_id,
        },
        clinica_id=clinica_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_almacen_role_can_record_clinic_scoped_stock_movements(client, db_session, setup_tenants):
    headers = crear_usuario_almacen(db_session)
    medicamento_a = Medicamento(
        clinica_id_FK=10,
        nombre="Paracetamol",
        requiere_receta=False,
    )
    medicamento_b = Medicamento(
        clinica_id_FK=20,
        nombre="Ibuprofeno",
        requiere_receta=False,
    )
    db_session.add_all([medicamento_a, medicamento_b])
    db_session.commit()

    response = client.post(
        "/api/almacen/inventario",
        headers=headers,
        json={
            "medicamento_id_FK": medicamento_a.id_PK,
            "numero_lote": "LOTE-A-01",
            "stock_actual": 8,
            "fecha_vencimiento": "2027-12-31",
            "fecha_recepcion": "2026-01-15",
        },
    )
    assert response.status_code == 201
    lote_id = response.json()["id_PK"]

    assert client.get("/api/almacen/inventario", headers=headers).json()[0]["clinica_id_FK"] == 10
    assert client.post(
        "/api/almacen/inventario",
        headers=headers,
        json={
            "medicamento_id_FK": medicamento_b.id_PK,
            "numero_lote": "LOTE-B-01",
            "stock_actual": 3,
        },
    ).status_code == 404

    dispensacion = client.post(
        "/api/almacen/movimientos",
        headers=headers,
        json={
            "inventario_id_FK": lote_id,
            "tipo": "dispensacion",
            "cantidad": 3,
            "motivo": "Paciente folio 123",
        },
    )
    assert dispensacion.status_code == 201
    assert dispensacion.json()["stock_anterior"] == 8
    assert dispensacion.json()["stock_nuevo"] == 5

    salida_excesiva = client.post(
        "/api/almacen/movimientos",
        headers=headers,
        json={"inventario_id_FK": lote_id, "tipo": "salida", "cantidad": 6},
    )
    assert salida_excesiva.status_code == 409

    entrada = client.post(
        "/api/almacen/movimientos",
        headers=headers,
        json={"inventario_id_FK": lote_id, "tipo": "entrada", "cantidad": 2},
    )
    assert entrada.status_code == 201
    assert entrada.json()["stock_nuevo"] == 7

    movimientos = client.get("/api/almacen/movimientos", headers=headers)
    assert movimientos.status_code == 200
    assert [movimiento["tipo"] for movimiento in movimientos.json()] == [
        "Entrada",
        "Dispensación",
        "Entrada",
    ]


def test_zero_stock_lot_can_be_archived_without_deleting_audit_history(
    client, db_session, setup_tenants
):
    headers = crear_usuario_almacen(db_session)
    medicamento = Medicamento(
        clinica_id_FK=10,
        nombre="Medicamento temporal",
        requiere_receta=False,
    )
    db_session.add(medicamento)
    db_session.commit()
    lote = Inventario(
        medicamento_id_FK=medicamento.id_PK,
        numero_lote="RETIRAR-01",
        stock_actual=2,
        fecha_vencimiento=date(2025, 1, 1),
    )
    db_session.add(lote)
    db_session.commit()

    respuesta = client.delete(f"/api/almacen/inventario/{lote.id_PK}", headers=headers)
    assert respuesta.status_code == 409
    assert client.post(
        "/api/almacen/movimientos",
        headers=headers,
        json={"inventario_id_FK": lote.id_PK, "tipo": "dispensacion", "cantidad": 1},
    ).status_code == 409

    salida = client.post(
        "/api/almacen/movimientos",
        headers=headers,
        json={"inventario_id_FK": lote.id_PK, "tipo": "salida", "cantidad": 2},
    )
    assert salida.status_code == 201
    assert client.delete(
        f"/api/almacen/inventario/{lote.id_PK}", headers=headers
    ).status_code == 204
    assert client.get("/api/almacen/inventario", headers=headers).json() == []
    assert len(client.get("/api/almacen/movimientos", headers=headers).json()) == 1
