from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import (
    ROL_ADMIN, ROL_ALMACEN, ROL_COORDINADOR, ROL_DOCTOR, ROL_RECEPCION,
    clinica_de, exigir_rol,
)
from app.database.connection import get_db
from app.models.dispensacion import Dispensacion
from app.models.inventario import Inventario
from app.models.item_receta import ItemReceta
from app.models.medicamento import Medicamento
from app.models.movimiento_inventario import MovimientoInventario
from app.models.paciente import Paciente
from app.models.presentacion_medicamento import PresentacionMedicamento
from app.models.receta import Receta
from app.models.usuario import Usuario
from app.schemas.almacen import (
    CaducidadOut,
    ConsumoRequest,
    ConsumoResponse,
    DispensacionHistorialOut,
    DispensacionOut,
    DispensarRequest,
    DispensarResponse,
    EvaluarInteraccionRequest,
    EvaluarInteraccionResponse,
    InteraccionResultado,
    InventarioCreate,
    InventarioResponse,
    MedicamentoResponse,
    MovimientoManualRequest,
    MovimientoOut,
    PresentacionCreate,
    PresentacionOut,
    ResumenAlmacen,
)
from app.schemas.receta import RecetaDetalle
from app.services import inventario_service as inv
from app.services.acceso_clinico import nombre_completo
from app.services.interacciones_service import evaluar_interacciones as servicio_interacciones
from app.services.notificacion_service import NotificacionService
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar

router = APIRouter(prefix="/api/almacen", tags=["Almacén e Interacciones"])

ROLES_ALMACEN = [ROL_ADMIN, ROL_ALMACEN]
ROLES_LECTURA_ALMACEN = [ROL_ADMIN, ROL_ALMACEN, ROL_COORDINADOR]


def _error(e: inv.InventarioError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.detalle)


def _lote_de_clinica(db: Session, lote_id: int, usuario: Usuario) -> Inventario:
    lote = db.query(Inventario).filter(Inventario.id_PK == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    clinica_id = clinica_de(usuario)
    if clinica_id is not None and lote.medicamento and lote.medicamento.clinica_id_FK != clinica_id:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre este lote")
    return lote


# 1. Listar el catálogo de medicamentos (CU-34 / Requerido para la App)
@router.get("/medicamentos", response_model=List[MedicamentoResponse])
def listar_medicamentos(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    query = db.query(Medicamento)
    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if clinica_id is not None:
        query = query.filter(Medicamento.clinica_id_FK == clinica_id)
    return query.all()


# 2. Listar el inventario de almacén (CU-34 a CU-38)
@router.get("/inventario", response_model=List[InventarioResponse])
def listar_inventario(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    query = db.query(Inventario)
    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if clinica_id is not None:
        query = query.join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK).filter(Medicamento.clinica_id_FK == clinica_id)
    return query.all()


# 3. Registrar lote/entrada en almacén (CU-35)
@router.post("/inventario", response_model=InventarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_lote_inventario(
    payload: InventarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_ALMACEN, "Solo almacén o administración pueden registrar lotes")

    if payload.medicamento_id_FK:
        med = db.query(Medicamento).filter(Medicamento.id_PK == payload.medicamento_id_FK).first()
        if not med:
            raise HTTPException(status_code=404, detail="Medicamento no encontrado")
        clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
        if clinica_id is not None and getattr(med, "clinica_id_FK", None) is not None and med.clinica_id_FK != clinica_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este medicamento")

    nuevo_lote = Inventario(**payload.model_dump())
    db.add(nuevo_lote)
    db.flush()

    # La existencia inicial queda trazada como una ENTRADA
    if (nuevo_lote.stock_actual or 0) > 0:
        inv.registrar_movimiento(
            db, nuevo_lote, nuevo_lote.stock_actual, inv.TIPO_ENTRADA,
            usuario_actual.id_PK, 0, nuevo_lote.stock_actual,
        )
    registrar_auditoria(
        db, usuario_actual, "CREAR", "inventario", nuevo_lote.id_PK, None,
        serializar(payload.model_dump()), ip=ip_desde_request(request),
        descripcion="Lote registrado",
    )
    db.commit()
    db.refresh(nuevo_lote)
    return nuevo_lote


@router.put("/inventario/{lote_id}", response_model=InventarioResponse)
def actualizar_lote(
    lote_id: int,
    payload: InventarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_ALMACEN)

    lote = db.query(Inventario).filter(Inventario.id_PK == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    clinica_id = getattr(usuario_actual, "clinica_id_FK", None)
    if clinica_id is not None and lote.medicamento and lote.medicamento.clinica_id_FK != clinica_id:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre este lote")

    anterior = int(lote.stock_actual or 0)
    antiguos = {
        "stock_actual": anterior,
        "numero_lote": lote.numero_lote,
        "fecha_vencimiento": lote.fecha_vencimiento,
    }

    for campo, valor in payload.model_dump().items():
        setattr(lote, campo, valor)

    # Si cambió el stock, se registra como AJUSTE para conservar la trazabilidad
    nuevo = int(lote.stock_actual or 0)
    if nuevo != anterior:
        inv.registrar_movimiento(
            db, lote, nuevo - anterior, inv.TIPO_AJUSTE,
            usuario_actual.id_PK, anterior, nuevo,
        )
    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "inventario", lote.id_PK,
        serializar(antiguos), serializar(payload.model_dump()),
        ip=ip_desde_request(request), descripcion="Lote actualizado",
    )
    db.commit()
    db.refresh(lote)
    return lote


# 4. Evaluar Interacciones entre Medicamentos (CU-33) — ahora exige sesión
@router.post("/evaluar-interacciones", response_model=EvaluarInteraccionResponse)
def evaluar_interacciones(
    payload: EvaluarInteraccionRequest,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_DOCTOR, ROL_ALMACEN, ROL_COORDINADOR, ROL_RECEPCION])
    ids = payload.medicamentos_ids
    if len(ids) < 2:
        return {"tiene_interaccion": False, "detalles": []}

    detalles = [InteraccionResultado(**d) for d in servicio_interacciones(db, ids)]
    return {"tiene_interaccion": len(detalles) > 0, "detalles": detalles}


# 5. Movimientos manuales: entradas, salidas, mermas y ajustes
@router.post("/inventario/{lote_id}/movimientos", response_model=InventarioResponse)
def registrar_movimiento_lote(
    lote_id: int,
    payload: MovimientoManualRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_ALMACEN)
    lote = _lote_de_clinica(db, lote_id, usuario_actual)
    anterior = int(lote.stock_actual or 0)
    try:
        inv.aplicar_movimiento_manual(db, lote, payload.tipo, payload.cantidad, usuario_actual.id_PK)
    except inv.InventarioError as e:
        db.rollback()
        raise _error(e)

    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "inventario", lote.id_PK,
        {"stock_actual": anterior}, {"stock_actual": lote.stock_actual},
        ip=ip_desde_request(request),
        descripcion=f"Movimiento {payload.tipo}: {payload.motivo or 'sin motivo'}",
    )
    db.commit()
    db.refresh(lote)
    return lote


@router.get("/movimientos", response_model=List[MovimientoOut])
def listar_movimientos(
    inventario_id: int | None = Query(None),
    medicamento_id: int | None = Query(None),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_LECTURA_ALMACEN)
    q = (
        db.query(MovimientoInventario)
        .join(Inventario, MovimientoInventario.inventario_id_FK == Inventario.id_PK)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
    )
    clinica_id = clinica_de(usuario_actual)
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)
    if inventario_id:
        q = q.filter(MovimientoInventario.inventario_id_FK == inventario_id)
    if medicamento_id:
        q = q.filter(Inventario.medicamento_id_FK == medicamento_id)

    movs = q.order_by(MovimientoInventario.creado_en.desc(), MovimientoInventario.id_PK.desc()).limit(limite).all()
    return [
        {
            "id_PK": m.id_PK,
            "inventario_id_FK": m.inventario_id_FK,
            "medicamento": m.inventario.medicamento.nombre if m.inventario and m.inventario.medicamento else None,
            "numero_lote": m.inventario.numero_lote if m.inventario else None,
            "tipo": m.tipo_movimiento.nombre if m.tipo_movimiento else None,
            "cantidad": m.cantidad,
            "stock_anterior": m.stock_anterior,
            "stock_nuevo": m.stock_nuevo,
            "usuario_id_FK": m.usuario_id_FK,
            "id_referencia": m.id_referencia,
            "creado_en": m.creado_en,
        }
        for m in movs
    ]


@router.post("/consumos", response_model=ConsumoResponse, status_code=status.HTTP_201_CREATED)
def registrar_consumo(
    payload: ConsumoRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Registra el uso interno de un artículo (guantes, jeringas, alcohol...) descontando lotes FEFO.

    Estos consumos alimentan las gráficas y la predicción de demanda.
    """
    exigir_rol(usuario_actual, ROLES_ALMACEN)
    articulo = _medicamento_de_clinica(db, payload.medicamento_id, usuario_actual)
    try:
        usados = inv.consumir_fefo(db, articulo.id_PK, payload.cantidad, inv.TIPO_CONSUMO, usuario_actual.id_PK)
    except inv.InventarioError as e:
        db.rollback()
        raise _error(e)

    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "inventario", articulo.id_PK, None,
        {"articulo": articulo.nombre, "cantidad": payload.cantidad, "area": payload.area},
        ip=ip_desde_request(request),
        descripcion=f"Consumo interno: {payload.area or 'sin área'} · {payload.motivo or 'sin motivo'}",
    )
    db.commit()
    return {
        "medicamento": articulo.nombre,
        "tipo_articulo": articulo.tipo_articulo or "medicamento",
        "cantidad": payload.cantidad,
        "lotes": [{"inventario_id": l.id_PK, "numero_lote": l.numero_lote, "cantidad": c} for l, c in usados],
        "stock_restante": inv.stock_disponible(db, articulo.id_PK),
    }


# 6. Caducidades y resumen del almacén
@router.get("/caducidades", response_model=List[CaducidadOut])
def listar_caducidades(
    dias: int = Query(60, ge=1, le=730, description="Ventana de alerta en días"),
    tipo: str | None = Query(None, description="medicamento | insumo | equipo"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Lotes con existencias que ya vencieron o vencen dentro de `dias`."""
    exigir_rol(usuario_actual, ROLES_LECTURA_ALMACEN)
    hoy = date.today()
    limite = hoy + timedelta(days=dias)

    q = (
        db.query(Inventario)
        .join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .filter(
            Inventario.stock_actual > 0,
            Inventario.fecha_vencimiento.isnot(None),
            Inventario.fecha_vencimiento <= limite,
        )
    )
    clinica_id = clinica_de(usuario_actual)
    if clinica_id is not None:
        q = q.filter(Medicamento.clinica_id_FK == clinica_id)
    if tipo:
        q = q.filter(Medicamento.tipo_articulo == tipo)

    salida = []
    for lote in q.order_by(Inventario.fecha_vencimiento.asc()).all():
        restantes = (lote.fecha_vencimiento - hoy).days
        salida.append(
            {
                "inventario_id": lote.id_PK,
                "medicamento_id": lote.medicamento_id_FK,
                "medicamento": lote.medicamento.nombre if lote.medicamento else None,
                "tipo_articulo": (lote.medicamento.tipo_articulo if lote.medicamento else None) or "medicamento",
                "unidad_medida": lote.medicamento.unidad_medida if lote.medicamento else None,
                "numero_lote": lote.numero_lote,
                "stock_actual": int(lote.stock_actual or 0),
                "ubicacion": lote.ubicacion,
                "fecha_vencimiento": lote.fecha_vencimiento,
                "dias_restantes": restantes,
                "estado": "vencido" if restantes < 0 else "por_vencer",
            }
        )
    return salida


@router.get("/resumen", response_model=ResumenAlmacen)
def resumen_almacen(
    umbral_stock_bajo: int = Query(10, ge=0),
    dias_caducidad: int = Query(60, ge=1, le=730),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Indicadores para el panel del almacén."""
    exigir_rol(usuario_actual, ROLES_LECTURA_ALMACEN)
    hoy = date.today()
    limite = hoy + timedelta(days=dias_caducidad)
    clinica_id = clinica_de(usuario_actual)

    meds_q = db.query(Medicamento)
    lotes_q = db.query(Inventario).join(Medicamento, Inventario.medicamento_id_FK == Medicamento.id_PK)
    if clinica_id is not None:
        meds_q = meds_q.filter(Medicamento.clinica_id_FK == clinica_id)
        lotes_q = lotes_q.filter(Medicamento.clinica_id_FK == clinica_id)

    con_stock = lotes_q.filter(Inventario.stock_actual > 0)
    vencidos = con_stock.filter(Inventario.fecha_vencimiento.isnot(None), Inventario.fecha_vencimiento < hoy).count()
    por_vencer = con_stock.filter(
        Inventario.fecha_vencimiento.isnot(None),
        Inventario.fecha_vencimiento >= hoy,
        Inventario.fecha_vencimiento <= limite,
    ).count()

    stock_por_med = (
        db.query(Medicamento.id_PK, inv.expresion_stock_vigente(), Medicamento.stock_minimo, Medicamento.tipo_articulo)
        .outerjoin(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .group_by(Medicamento.id_PK, Medicamento.stock_minimo, Medicamento.tipo_articulo)
    )
    if clinica_id is not None:
        stock_por_med = stock_por_med.filter(Medicamento.clinica_id_FK == clinica_id)
    filas = stock_por_med.all()
    unidades = sum(int(s or 0) for _, s, _m, _t in filas)
    # Cada artículo usa su stock mínimo; si no lo tiene, el umbral general. El equipo no se cuenta.
    stock_bajo = sum(
        1 for _, s, minimo, tipo_art in filas
        if (tipo_art or "medicamento") != "equipo" and int(s or 0) <= ((minimo or 0) or umbral_stock_bajo)
    )

    pend_q = db.query(Receta).join(Paciente, Receta.paciente_id_FK == Paciente.id_PK).filter(
        Receta.estado.in_([inv.ESTADO_RECETA_ACTIVA, inv.ESTADO_RECETA_PARCIAL])
    )
    if clinica_id is not None:
        pend_q = pend_q.filter(Paciente.clinica_id_FK == clinica_id)

    return {
        "total_medicamentos": meds_q.count(),
        "total_lotes": lotes_q.count(),
        "unidades_vigentes": unidades,
        "lotes_vencidos": vencidos,
        "lotes_por_vencer": por_vencer,
        "medicamentos_stock_bajo": stock_bajo,
        "recetas_pendientes": pend_q.count(),
        "umbral_stock_bajo": umbral_stock_bajo,
        "dias_alerta_caducidad": dias_caducidad,
    }


# 7. Dispensación de recetas
@router.get("/recetas-pendientes", response_model=List[RecetaDetalle])
def recetas_pendientes(
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Recetas activas o parcialmente dispensadas, con su disponibilidad."""
    exigir_rol(usuario_actual, ROLES_ALMACEN)
    from app.routers.recetas import _detalle  # evita import circular al cargar la app

    q = db.query(Receta).join(Paciente, Receta.paciente_id_FK == Paciente.id_PK).filter(
        Receta.estado.in_([inv.ESTADO_RECETA_ACTIVA, inv.ESTADO_RECETA_PARCIAL])
    )
    clinica_id = clinica_de(usuario_actual)
    if clinica_id is not None:
        q = q.filter(Paciente.clinica_id_FK == clinica_id)
    recetas = q.order_by(Receta.creado_en.asc()).all()
    return [_detalle(db, r) for r in recetas]


@router.post("/dispensar", response_model=DispensarResponse)
def dispensar(
    payload: DispensarRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Dispensa (total o parcialmente) una receta y descuenta el inventario (FEFO)."""
    exigir_rol(usuario_actual, ROLES_ALMACEN, "Solo almacén puede dispensar medicamentos")

    receta = db.query(Receta).filter(Receta.id_PK == payload.receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    clinica_id = clinica_de(usuario_actual)
    if clinica_id is not None and receta.paciente and receta.paciente.clinica_id_FK != clinica_id:
        raise HTTPException(status_code=403, detail="La receta no pertenece a tu clínica")

    items = (
        db.query(ItemReceta).filter(ItemReceta.receta_id_FK == receta.id_PK).order_by(ItemReceta.id_PK).all()
    )
    solicitudes = None
    if payload.items is not None:
        solicitudes = {}
        for it in payload.items:
            if it.item_receta_id in solicitudes:
                raise HTTPException(status_code=400, detail="Ítem repetido en la solicitud")
            solicitudes[it.item_receta_id] = it.cantidad

    estado_previo = receta.estado
    try:
        resultado = inv.dispensar_receta(
            db, receta, items, usuario_actual.id_PK, clinica_id,
            solicitudes=solicitudes, notas=payload.notas,
        )
        registrar_auditoria(
            db, usuario_actual, "ACTUALIZAR", "recetas", receta.id_PK,
            {"estado": estado_previo}, {"estado": receta.estado},
            ip=ip_desde_request(request),
            descripcion=f"Dispensación ({len(resultado['dispensaciones'])} movimientos de lote)",
        )
        db.commit()
    except inv.InventarioError as e:
        db.rollback()
        raise _error(e)

    # Avisos (no deben romper la respuesta si fallan)
    try:
        servicio = NotificacionService(db)
        doctor = receta.doctor
        if resultado["faltantes"] and doctor and doctor.usuario_id_FK:
            nombres = ", ".join(f["medicamento"] or "?" for f in resultado["faltantes"])
            servicio.crear(
                doctor.usuario_id_FK,
                f"Receta #{receta.id_PK}: sin existencias completas de {nombres}. Informa al paciente.",
                tipo="medication_unavailable",
                enlace="/doctor/consultas",
            )
        paciente = receta.paciente
        if paciente and paciente.usuario_id_FK:
            texto = (
                f"Tu receta #{receta.id_PK} fue dispensada."
                if not resultado["faltantes"]
                else f"Tu receta #{receta.id_PK} fue dispensada parcialmente; el resto estará pendiente."
            )
            servicio.crear(paciente.usuario_id_FK, texto, tipo="prescription_dispensed", enlace="/paciente")
    except Exception:  # noqa: BLE001
        pass

    return {
        "receta_id": receta.id_PK,
        "estado_receta": receta.estado,
        "completa": not resultado["faltantes"],
        "dispensaciones": [
            {
                "id_PK": d.id_PK,
                "item_receta_id": d.item_receta_id_FK,
                "medicamento": d.item.medicamento.nombre if d.item and d.item.medicamento else None,
                "inventario_id": d.inventario_id_FK,
                "numero_lote": d.lote.numero_lote if d.lote else None,
                "cantidad": d.cantidad,
            }
            for d in resultado["dispensaciones"]
        ],
        "faltantes": resultado["faltantes"],
    }


@router.get("/dispensaciones", response_model=List[DispensacionHistorialOut])
def historial_dispensaciones(
    receta_id: int | None = Query(None),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_LECTURA_ALMACEN)
    q = db.query(Dispensacion)
    clinica_id = clinica_de(usuario_actual)
    if clinica_id is not None:
        q = q.filter(Dispensacion.clinica_id_FK == clinica_id)
    if receta_id:
        q = q.filter(Dispensacion.receta_id_FK == receta_id)
    filas = q.order_by(Dispensacion.creado_en.desc(), Dispensacion.id_PK.desc()).limit(limite).all()
    return [
        {
            "id_PK": d.id_PK,
            "receta_id": d.receta_id_FK,
            "paciente": nombre_completo(d.receta.paciente) if d.receta else None,
            "medicamento": d.item.medicamento.nombre if d.item and d.item.medicamento else None,
            "numero_lote": d.lote.numero_lote if d.lote else None,
            "cantidad": d.cantidad,
            "usuario_id_FK": d.usuario_id_FK,
            "creado_en": d.creado_en,
        }
        for d in filas
    ]


# 8. Presentaciones (concentración / forma farmacéutica)
@router.get("/medicamentos/{medicamento_id}/presentaciones", response_model=List[PresentacionOut])
def listar_presentaciones(
    medicamento_id: int,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN, ROL_DOCTOR, ROL_COORDINADOR])
    _medicamento_de_clinica(db, medicamento_id, usuario_actual)
    return (
        db.query(PresentacionMedicamento)
        .filter(PresentacionMedicamento.medicamento_id_FK == medicamento_id, PresentacionMedicamento.esta_activo.is_(True))
        .all()
    )


@router.post(
    "/medicamentos/{medicamento_id}/presentaciones",
    response_model=PresentacionOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_presentacion(
    medicamento_id: int,
    payload: PresentacionCreate,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, ROLES_ALMACEN)
    _medicamento_de_clinica(db, medicamento_id, usuario_actual)
    if not (payload.concentracion or payload.forma_farmaceutica or payload.contenido):
        raise HTTPException(status_code=422, detail="Indica al menos concentración, forma o contenido")
    nueva = PresentacionMedicamento(medicamento_id_FK=medicamento_id, **payload.model_dump())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


def _medicamento_de_clinica(db: Session, medicamento_id: int, usuario: Usuario) -> Medicamento:
    med = db.query(Medicamento).filter(Medicamento.id_PK == medicamento_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    clinica_id = clinica_de(usuario)
    if clinica_id is not None and med.clinica_id_FK != clinica_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este medicamento")
    return med
