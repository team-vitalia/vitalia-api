"""Firma electrónica SIMULADA de recetas (uso académico, sin validez jurídica) — endpoints del médico."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.roles import ROL_ADMIN, ROL_COORDINADOR, ROL_DOCTOR, clinica_de, exigir_rol
from app.database.connection import get_db
from app.models.firma_receta import FirmaReceta
from app.models.historial_firma_receta import HistorialFirmaReceta
from app.models.item_receta import ItemReceta
from app.models.receta import Receta
from app.models.usuario import Usuario
from app.schemas.firma_receta import FirmarRecetaRequest
from app.services import firma_simulada_service as svc
from app.services.acceso_clinico import doctor_de_usuario, nombre_completo
from app.utils.auditoria import ip_desde_request, registrar_auditoria

router = APIRouter(prefix="/api/firma-recetas", tags=["Firma electrónica simulada de recetas"])

_HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _base_url(request: Request) -> str:
    """URL pública de la API: PUBLIC_API_URL o, si falta, la URL con la que se llamó."""
    return settings.PUBLIC_API_URL or str(request.base_url).rstrip("/")


def _url_alcanzable_desde_otro_dispositivo(url: str) -> bool:
    host = url.split("://", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0].strip("[]").lower()
    return host not in _HOSTS_LOCALES


def _firma_out(firma: FirmaReceta) -> dict:
    ident = firma.identidad
    externa = _url_alcanzable_desde_otro_dispositivo(firma.url_verificacion)
    return {
        "firmada": True,
        "id_PK": firma.id_PK,
        "receta_id": firma.receta_id_FK,
        "identificador": firma.identificador,
        "codigo_verificacion": firma.codigo_verificacion,
        "fecha_firma_utc": svc.fecha_iso_utc(firma.fecha_firma),
        "algoritmo": firma.algoritmo_firma,
        "hash_pdf_sha256": firma.hash_pdf_sha256,
        "tamano_pdf": firma.tamano_pdf,
        "url_verificacion": firma.url_verificacion,
        "url_accesible_desde_otro_dispositivo": externa,
        "advertencia": None if externa else (
            "La URL del QR apunta a localhost y NO se podrá abrir desde otro dispositivo. "
            "Define PUBLIC_API_URL (p. ej. http://192.168.100.14:8000) y firma de nuevo."
        ),
        "medico": {
            "nombre_ficticio": ident.nombre_ficticio,
            "cedula_ficticia": ident.cedula_ficticia,
            "especialidad_ficticia": ident.especialidad_ficticia,
            "huella_sha256": ident.huella_sha256,
        },
        "leyenda": svc.LEYENDA,
    }


def _receta_o_404(db: Session, receta_id: int) -> Receta:
    receta = db.query(Receta).filter(Receta.id_PK == receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return receta


def _exigir_acceso_a_receta(db: Session, usuario: Usuario, receta: Receta, *, solo_dueno: bool) -> None:
    clinica = clinica_de(usuario)
    if clinica is not None and receta.paciente and receta.paciente.clinica_id_FK != clinica:
        raise HTTPException(status_code=403, detail="No tienes permiso sobre esta receta")
    if usuario.rol_id_FK == ROL_DOCTOR:
        doctor = doctor_de_usuario(db, usuario)
        if not doctor or receta.doctor_id_FK != doctor.id_PK:
            raise HTTPException(status_code=403, detail="Solo el médico que emitió la receta puede hacerlo")
    elif solo_dueno or usuario.rol_id_FK not in (ROL_ADMIN, ROL_COORDINADOR):
        raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")


def _firma_de_codigo(db: Session, codigo: str) -> FirmaReceta:
    firma = db.query(FirmaReceta).filter(FirmaReceta.codigo_verificacion == codigo).first()
    if not firma:
        raise HTTPException(status_code=404, detail="Firma no encontrada")
    return firma


# ------------------------------------------------------------------ identidad ficticia
@router.get("/identidad")
def mi_identidad(db: Session = Depends(get_db), usuario_actual: Usuario = Depends(get_current_user)):
    """Identidad ficticia del médico (solo datos públicos; la llave privada nunca sale del backend)."""
    exigir_rol(usuario_actual, [ROL_DOCTOR])
    ident = svc.obtener_identidad(db, usuario_actual)
    if not ident:
        return {"existe": False, "leyenda": svc.LEYENDA}
    return {"existe": True, **svc.datos_publicos_identidad(ident)}


@router.post("/identidad")
def generar_mi_identidad(response: Response, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(get_current_user)):
    """Genera (si aún no existe) la identidad ficticia y el par de llaves RSA del médico."""
    exigir_rol(usuario_actual, [ROL_DOCTOR])
    ident = svc.obtener_identidad(db, usuario_actual)
    creada = ident is None
    if creada:
        try:
            ident = svc.generar_identidad(db, usuario_actual)
            db.commit()
        except IntegrityError:  # dos solicitudes simultáneas: gana la primera
            db.rollback()
            ident = svc.obtener_identidad(db, usuario_actual)
            creada = False
    response.status_code = status.HTTP_201_CREATED if creada else status.HTTP_200_OK
    return {"existe": True, "creada": creada, **svc.datos_publicos_identidad(ident)}


# ------------------------------------------------------------------ firmar
@router.post("/recetas/{receta_id}/firmar", status_code=status.HTTP_201_CREATED)
def firmar_receta(
    receta_id: int,
    datos: FirmarRecetaRequest,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """Confirma y firma la receta: genera el PDF con QR, lo firma (RSA-PSS/SHA-256) y guarda todo."""
    exigir_rol(usuario_actual, [ROL_DOCTOR], "Solo el médico que emitió la receta puede firmarla")
    if not (datos.confirmar and datos.acepto_simulacion):
        raise HTTPException(
            status_code=400,
            detail="Debes confirmar la firma y aceptar que es una simulación académica sin validez jurídica",
        )

    receta = _receta_o_404(db, receta_id)
    _exigir_acceso_a_receta(db, usuario_actual, receta, solo_dueno=True)
    if receta.estado == "cancelada":
        raise HTTPException(status_code=409, detail="No se puede firmar una receta cancelada")

    items = db.query(ItemReceta).filter(ItemReceta.receta_id_FK == receta.id_PK).order_by(ItemReceta.id_PK).all()
    if not items:
        raise HTTPException(status_code=409, detail="La receta no tiene medicamentos")

    try:
        firma = svc.firmar_receta(db, receta, items, nombre_completo(receta.paciente), usuario_actual, _base_url(request))
        svc.registrar_evento(
            db, firma, "FIRMADA", usuario_id=usuario_actual.id_PK,
            ip=ip_desde_request(request), user_agent=request.headers.get("user-agent"),
            detalle=f"Firma simulada creada ({firma.algoritmo_firma}); sha256 pdf={firma.hash_pdf_sha256}",
        )
        registrar_auditoria(
            db, usuario_actual, "CREAR", "firmas_recetas", firma.id_PK, None,
            {"receta_id": receta.id_PK, "identificador": firma.identificador},
            ip=ip_desde_request(request), descripcion="Firma electrónica SIMULADA de receta",
        )
        db.commit()
    except svc.FirmaError as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detalle)
    except IntegrityError:  # firma simultánea de la misma receta
        db.rollback()
        raise HTTPException(status_code=409, detail="Esta receta ya fue firmada")
    db.refresh(firma)
    return _firma_out(firma)


# ------------------------------------------------------------------ consultar
@router.get("/mias")
def mis_firmas(db: Session = Depends(get_db), usuario_actual: Usuario = Depends(get_current_user)):
    exigir_rol(usuario_actual, [ROL_DOCTOR])
    filas = (
        db.query(FirmaReceta)
        .filter(FirmaReceta.firmado_por_usuario_id_FK == usuario_actual.id_PK)
        .order_by(FirmaReceta.fecha_firma.desc())
        .all()
    )
    return [_firma_out(f) for f in filas]


@router.get("/recetas/{receta_id}")
def firma_de_receta(receta_id: int, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(get_current_user)):
    receta = _receta_o_404(db, receta_id)
    _exigir_acceso_a_receta(db, usuario_actual, receta, solo_dueno=False)
    firma = db.query(FirmaReceta).filter(FirmaReceta.receta_id_FK == receta.id_PK).first()
    return _firma_out(firma) if firma else {"firmada": False, "receta_id": receta.id_PK}


@router.get("/{codigo}/pdf")
def descargar_pdf(
    codigo: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
):
    """PDF original firmado (requiere sesión: contiene datos del paciente)."""
    firma = _firma_de_codigo(db, codigo)
    _exigir_acceso_a_receta(db, usuario_actual, _receta_o_404(db, firma.receta_id_FK), solo_dueno=False)
    svc.registrar_evento(
        db, firma, "PDF_DESCARGADO", usuario_id=usuario_actual.id_PK,
        ip=ip_desde_request(request), user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return Response(
        content=bytes(firma.pdf_original),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="receta-{firma.receta_id_FK:06d}-firma-simulada.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{codigo}/historial")
def historial(codigo: str, db: Session = Depends(get_db), usuario_actual: Usuario = Depends(get_current_user)):
    firma = _firma_de_codigo(db, codigo)
    _exigir_acceso_a_receta(db, usuario_actual, _receta_o_404(db, firma.receta_id_FK), solo_dueno=False)
    filas = (
        db.query(HistorialFirmaReceta)
        .filter(HistorialFirmaReceta.firma_id_FK == firma.id_PK)
        .order_by(HistorialFirmaReceta.id_PK.desc())
        .limit(200)
        .all()
    )
    return [
        {"id_PK": h.id_PK, "accion": h.accion, "resultado": h.resultado, "detalle": h.detalle,
         "ip": h.ip, "creado_en": h.creado_en}
        for h in filas
    ]
