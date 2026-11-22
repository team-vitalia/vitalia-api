import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.medicamento import Medicamento
from app.models.interaccion_medicamento import InteraccionMedicamento
from app.models.inventario import Inventario
from app.models.item_receta import ItemReceta
from app.models.presentacion_medicamento import PresentacionMedicamento
from app.models.usuario import Usuario
from app.core.dependencies import get_current_user
from app.core.roles import ROL_ADMIN, ROL_ALMACEN, ROL_DOCTOR, ROL_RECEPCION, exigir_rol
from app.core.codigo_barras import variantes_codigo
from app.schemas.medicamento import (
    ImportacionMedicamentosResponse,
    MedicamentoCreate,
    MedicamentoImportar,
    MedicamentoResponse,
    MedicamentoUpdate,
)
from app.services import medicamentos_io as mio
from app.services.inventario_service import expresion_stock_vigente
from app.utils.auditoria import ip_desde_request, registrar_auditoria, serializar

router = APIRouter(prefix="/api/medicamentos", tags=["Medicamentos"])


def _serializar(med: Medicamento, stock: int) -> dict:
    return {
        "id_PK": med.id_PK,
        "nombre": med.nombre,
        "presentacion": med.presentacion,
        "requiere_receta": med.requiere_receta,
        "principio_activo": med.principio_activo,
        "descripcion": med.descripcion,
        "codigo_barras": med.codigo_barras,
        "categoria": med.categoria,
        "tipo_articulo": med.tipo_articulo or "medicamento",
        "unidad_medida": med.unidad_medida,
        "stock_minimo": med.stock_minimo or 0,
        "stock_actual": int(stock) if stock else 0,
    }


def _consultar_catalogo(
    db: Session,
    usuario_actual: Usuario,
    q: str | None,
    tipo: str | None,
    limite: int | None,
) -> list[dict]:
    # `stock_actual` = unidades en lotes NO vencidos (existencia realmente disponible)
    query = (
        db.query(Medicamento, expresion_stock_vigente().label("total_stock"))
        .outerjoin(Inventario, Inventario.medicamento_id_FK == Medicamento.id_PK)
        .group_by(Medicamento.id_PK)
    )

    if usuario_actual.clinica_id_FK is not None:
        query = query.filter(Medicamento.clinica_id_FK == usuario_actual.clinica_id_FK)
    # Los médicos solo recetan medicamentos; los insumos/equipo no aparecen en su buscador
    if usuario_actual.rol_id_FK == ROL_DOCTOR and not tipo:
        tipo = "medicamento"
    if tipo:
        query = query.filter(Medicamento.tipo_articulo == tipo)
    if q:
        query = query.filter(
            Medicamento.nombre.ilike(f"%{q}%")
            | Medicamento.principio_activo.ilike(f"%{q}%")
            | Medicamento.codigo_barras.ilike(f"%{q}%")
        )

    query = query.order_by(Medicamento.nombre)
    if limite:
        query = query.limit(limite)
    return [_serializar(med, stock) for med, stock in query.all()]


def _descripcion_filtro(q: str | None, tipo: str | None) -> str | None:
    partes = []
    if tipo:
        partes.append(f"tipo {tipo}")
    if q:
        partes.append(f"búsqueda «{q}»")
    return ", ".join(partes) or None


@router.get("/", response_model=list[MedicamentoResponse])
def buscar_medicamentos(
    q: str | None = Query(None, description="Término de búsqueda por nombre, principio activo o código"),
    tipo: str | None = Query(None, description="medicamento | insumo | equipo (el doctor ve solo medicamentos)"),
    limite: int = Query(50, ge=1, le=5000, description="Máximo de resultados (la administración del catálogo usa 5000)"),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user)
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_DOCTOR, ROL_RECEPCION, ROL_ALMACEN], "No tienes permiso")
    return _consultar_catalogo(db, usuario_actual, q, tipo, limite)


@router.post("/", response_model=MedicamentoResponse, status_code=status.HTTP_201_CREATED)
def crear_medicamento(
    payload: MedicamentoCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")

    datos = payload.model_dump()
    if usuario_actual.clinica_id_FK is not None:
        datos["clinica_id_FK"] = usuario_actual.clinica_id_FK
    nuevo = Medicamento(**datos)
    db.add(nuevo)
    db.flush()
    registrar_auditoria(
        db, usuario_actual, "CREAR", "medicamentos", nuevo.id_PK, None,
        serializar(payload.model_dump()), ip=ip_desde_request(request),
        descripcion="Medicamento registrado",
    )
    db.commit()
    db.refresh(nuevo)
    return _serializar(nuevo, 0)


@router.put("/{medicamento_id}", response_model=MedicamentoResponse)
def actualizar_medicamento(
    medicamento_id: int,
    payload: MedicamentoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")

    med = db.query(Medicamento).filter(Medicamento.id_PK == medicamento_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    if usuario_actual.clinica_id_FK is not None and med.clinica_id_FK != usuario_actual.clinica_id_FK:
        raise HTTPException(status_code=403, detail="No tienes acceso a este medicamento")

    cambios = payload.model_dump(exclude_unset=True)
    antiguos = {campo: getattr(med, campo) for campo in cambios}
    for campo, valor in cambios.items():
        setattr(med, campo, valor)
    registrar_auditoria(
        db, usuario_actual, "ACTUALIZAR", "medicamentos", med.id_PK,
        serializar(antiguos), serializar(cambios), ip=ip_desde_request(request),
        descripcion="Medicamento actualizado",
    )
    db.commit()
    db.refresh(med)

    stock = (
        db.query(expresion_stock_vigente())
        .filter(Inventario.medicamento_id_FK == med.id_PK)
        .scalar()
    )
    return _serializar(med, stock or 0)


@router.delete("/{medicamento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_medicamento(
    medicamento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Elimina un medicamento del catálogo.

    Se bloquea (409) si tiene lotes en almacén o si aparece en recetas, porque borrarlo
    rompería la trazabilidad de existencias y el historial clínico.
    """
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")

    med = db.query(Medicamento).filter(Medicamento.id_PK == medicamento_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicamento no encontrado")
    if usuario_actual.clinica_id_FK is not None and med.clinica_id_FK != usuario_actual.clinica_id_FK:
        raise HTTPException(status_code=403, detail="No tienes acceso a este medicamento")

    lotes = db.query(Inventario).filter(Inventario.medicamento_id_FK == medicamento_id).count()
    if lotes:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar «{med.nombre}»: tiene {lotes} lote(s) registrados en el almacén.",
        )
    recetas = db.query(ItemReceta).filter(ItemReceta.medicamento_id_FK == medicamento_id).count()
    if recetas:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar «{med.nombre}»: aparece en {recetas} receta(s) del historial.",
        )

    antiguos = _serializar(med, 0)
    # Datos de apoyo del propio medicamento (no son historial clínico)
    db.query(PresentacionMedicamento).filter(PresentacionMedicamento.medicamento_id_FK == medicamento_id).delete()
    db.query(InteraccionMedicamento).filter(
        (InteraccionMedicamento.medicamento_id_FK == medicamento_id)
        | (InteraccionMedicamento.medicamento_interactuante_id_FK == medicamento_id)
    ).delete(synchronize_session=False)
    db.delete(med)
    registrar_auditoria(
        db, usuario_actual, "ELIMINAR", "medicamentos", medicamento_id,
        serializar(antiguos), None, ip=ip_desde_request(request),
        descripcion="Medicamento eliminado",
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# EXPORTAR / IMPORTAR (Excel) · LISTA EN PDF
# ============================================================
_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _nombre_clinica(usuario: Usuario) -> str:
    clinica = getattr(usuario, "clinica", None)
    if clinica and getattr(clinica, "nombre_comercial", None):
        return str(clinica.nombre_comercial)
    return "Clínica VITALIA"


@router.get("/exportar/excel")
def exportar_medicamentos_excel(
    q: str | None = Query(None),
    tipo: str | None = Query(None),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")
    datos = _consultar_catalogo(db, usuario_actual, q, tipo, None)
    return Response(
        content=mio.a_excel(datos),
        media_type=_MIME_XLSX,
        headers={"Content-Disposition": 'attachment; filename="medicamentos.xlsx"'},
    )


@router.get("/exportar/pdf")
def exportar_medicamentos_pdf(
    q: str | None = Query(None),
    tipo: str | None = Query(None),
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")
    datos = _consultar_catalogo(db, usuario_actual, q, tipo, None)
    return Response(
        content=mio.a_pdf(datos, _nombre_clinica(usuario_actual), _descripcion_filtro(q, tipo)),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="lista_medicamentos.pdf"'},
    )


@router.get("/plantilla/excel")
def descargar_plantilla_excel(usuario_actual: Usuario = Depends(get_current_user)):
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")
    return Response(
        content=mio.plantilla_excel(),
        media_type=_MIME_XLSX,
        headers={"Content-Disposition": 'attachment; filename="plantilla_medicamentos.xlsx"'},
    )


def _clave_codigo(codigo: str | None) -> str | None:
    """Clave canónica de un código (EAN-13/UPC-A/GTIN-14 con ceros distintos = mismo producto)."""
    variantes = variantes_codigo(codigo)
    if not variantes:
        return None
    return variantes[0].lstrip("0") if variantes[0].isdigit() else variantes[0]


@router.post("/importar", response_model=ImportacionMedicamentosResponse)
def importar_medicamentos(
    payload: MedicamentoImportar,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Alta masiva desde Excel. Las filas válidas se guardan; las inválidas se reportan por número de fila."""
    exigir_rol(usuario_actual, [ROL_ADMIN, ROL_ALMACEN], "No tienes permiso")
    clinica_id = usuario_actual.clinica_id_FK
    if clinica_id is None:
        raise HTTPException(status_code=400, detail="Tu usuario no tiene una clínica asignada.")

    try:
        crudo = payload.archivo_base64.split(",", 1)[-1]  # admite el prefijo "data:...;base64,"
        contenido = base64.b64decode(crudo, validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="El archivo no llegó completo. Inténtalo de nuevo.")
    try:
        filas = mio.leer_filas_excel(contenido)
    except mio.ArchivoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))

    existentes = db.query(Medicamento).filter(Medicamento.clinica_id_FK == clinica_id).all()
    por_codigo: dict[str, Medicamento] = {}
    por_nombre: dict[str, Medicamento] = {}
    for m in existentes:
        clave = _clave_codigo(m.codigo_barras)
        if clave:
            por_codigo.setdefault(clave, m)
        por_nombre.setdefault(mio.clave_nombre(m.nombre, m.presentacion), m)

    creados = actualizados = omitidos = 0
    errores: list[dict] = []
    vistos: dict[str, int] = {}
    primer_id: int | None = None

    for numero, datos in filas:
        limpio, error = mio.normalizar_fila(datos)
        if error:
            errores.append({"fila": numero, "mensaje": error})
            continue

        clave_c = _clave_codigo(limpio["codigo_barras"])
        clave_n = mio.clave_nombre(limpio["nombre"], limpio["presentacion"])
        clave_archivo = f"c:{clave_c}" if clave_c else f"n:{clave_n}"
        if clave_archivo in vistos:
            errores.append({"fila": numero, "mensaje": f"Repetido en el archivo (igual que la fila {vistos[clave_archivo]})."})
            continue
        vistos[clave_archivo] = numero

        existente = (por_codigo.get(clave_c) if clave_c else None) or por_nombre.get(clave_n)

        if existente is not None:
            if payload.modo != "actualizar":
                omitidos += 1
                continue
            presentes = mio.campos_presentes(datos) | {"nombre"}
            hubo_cambio = False
            for campo, valor in limpio.items():
                if campo not in presentes:
                    continue  # celda vacía: no borra lo que ya existe
                if getattr(existente, campo) != valor:
                    setattr(existente, campo, valor)
                    hubo_cambio = True
            if hubo_cambio:
                actualizados += 1
                primer_id = primer_id or existente.id_PK
            else:
                omitidos += 1
            continue

        nuevo = Medicamento(clinica_id_FK=clinica_id, **limpio)
        db.add(nuevo)
        creados += 1
        if clave_c:
            por_codigo[clave_c] = nuevo
        por_nombre[clave_n] = nuevo

    if creados or actualizados:
        db.flush()
        registrar_auditoria(
            db, usuario_actual, "CREAR", "medicamentos", primer_id, None,
            {"creados": creados, "actualizados": actualizados, "omitidos": omitidos, "con_error": len(errores)},
            ip=ip_desde_request(request),
            descripcion=f"Importación de medicamentos desde Excel ({creados} nuevos, {actualizados} actualizados)",
        )
        db.commit()

    return ImportacionMedicamentosResponse(
        total_filas=len(filas),
        creados=creados,
        actualizados=actualizados,
        omitidos=omitidos,
        errores=errores,
    )
