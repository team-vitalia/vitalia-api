"""Firma electrónica SIMULADA de recetas — USO ACADÉMICO, SIN VALIDEZ JURÍDICA.

NO usa e.firma del SAT ni certificados reales: todas las identidades y llaves son
FICTICIAS y se generan automáticamente.

Cómo funciona
-------------
1. Cada médico obtiene (al firmar por primera vez) una identidad ficticia y un par
   de llaves RSA-2048. La llave PRIVADA se guarda cifrada (PKCS#8, AES-256) en la
   base y NUNCA se expone por la API; solo este módulo la descifra, en memoria.
2. Al firmar una receta se genera su PDF (con QR) y se construye un *manifiesto*
   con: código público, id de receta, SHA-256 del PDF, SHA-256 del contenido de la
   receta, fecha de firma (UTC) y huella de la clave pública.
3. Se firma el manifiesto con RSASSA-PSS + SHA-256 (firma separada del PDF).
4. Verificar = (a) comprobar la firma con la clave PÚBLICA, (b) comprobar que el
   manifiesto coincide con los datos guardados, (c) recalcular el SHA-256 del PDF
   guardado y, opcionalmente, del PDF que presenta quien verifica, y (d) comprobar
   que el contenido de la receta no cambió. Cualquier diferencia => INVÁLIDA.

Limitación (es una simulación): la confianza descansa en la propia base de datos;
quien pudiera reescribir llaves y firmas a la vez podría fabricar firmas, cosa que
una PKI real evitaría con una autoridad certificadora externa.
"""
import base64
import binascii
import hashlib
import json
import secrets
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.firma_receta import FirmaReceta
from app.models.historial_firma_receta import HistorialFirmaReceta
from app.models.identidad_firma_simulada import IdentidadFirmaSimulada
from app.models.item_receta import ItemReceta
from app.models.receta import Receta

LEYENDA = "FIRMA ELECTRÓNICA SIMULADA - USO ACADÉMICO - SIN VALIDEZ JURÍDICA"
TIPO_MANIFIESTO = "VITALIA-RECETA-FIRMA-SIMULADA"
ALGORITMO_FIRMA = "RSASSA-PSS-SHA256"
ALGORITMO_LLAVE = "RSA-2048"
RUTA_VERIFICACION = "/api/verificar-receta"

_PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32)

# Nombres inventados (no corresponden a personas reales)
_NOMBRES = [
    "Dr. Alejandro Simulado Ruiz", "Dra. Elena Prueba Montoya", "Dr. Ricardo Ficticio Almazán",
    "Dra. Sofía Académica Lerma", "Dr. Mateo Demostración Cuevas", "Dra. Valeria Ejemplo Ibarra",
]
_ESPECIALIDADES = ["Medicina General (simulada)", "Medicina Familiar (simulada)", "Medicina Interna (simulada)"]


class FirmaError(Exception):
    """Error de regla de negocio; el router lo convierte en HTTPException."""

    def __init__(self, detalle: str, status_code: int = 400):
        super().__init__(detalle)
        self.detalle = detalle
        self.status_code = status_code


# ------------------------------------------------------------------ utilidades
def sha256_hex(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _json_canonico(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def ahora_utc() -> datetime:
    """Hora UTC sin zona y sin microsegundos (así coincide exactamente con lo guardado en la BD)."""
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)


def fecha_iso_utc(fecha: datetime) -> str:
    return fecha.strftime("%Y-%m-%dT%H:%M:%SZ")


def _frase_cifrado() -> bytes:
    """Frase para cifrar llaves privadas: FIRMA_SIM_CLAVE o, si falta, derivada de SECRET_KEY."""
    base = (settings.FIRMA_SIM_CLAVE or settings.SECRET_KEY).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", base, b"vitalia-firma-simulada", 100_000).hex().encode("ascii")


def huella_de_pem(clave_publica_pem: str) -> str:
    pub = serialization.load_pem_public_key(clave_publica_pem.encode("ascii"))
    der = pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return sha256_hex(der)


# ------------------------------------------------------------------ identidad ficticia
def generar_identidad(db: Session, usuario) -> IdentidadFirmaSimulada:
    """Crea identidad ficticia + llaves RSA-2048 para el usuario (el commit lo hace el llamador)."""
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_privada = privada.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(_frase_cifrado()),
    ).decode("ascii")
    pem_publica = privada.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")

    identidad = IdentidadFirmaSimulada(
        clinica_id_FK=getattr(usuario, "clinica_id_FK", None),
        usuario_id_FK=usuario.id_PK,
        nombre_ficticio=secrets.choice(_NOMBRES),
        # El prefijo «SIM-ACAD» garantiza que no es una cédula profesional real
        cedula_ficticia=f"SIM-ACAD-{secrets.randbelow(10_000_000):07d}",
        especialidad_ficticia=secrets.choice(_ESPECIALIDADES),
        algoritmo=ALGORITMO_LLAVE,
        clave_publica_pem=pem_publica,
        huella_sha256=huella_de_pem(pem_publica),
        clave_privada_cifrada=pem_privada,
        activa=True,
    )
    db.add(identidad)
    db.flush()
    return identidad


def obtener_identidad(db: Session, usuario) -> IdentidadFirmaSimulada | None:
    return db.query(IdentidadFirmaSimulada).filter(IdentidadFirmaSimulada.usuario_id_FK == usuario.id_PK).first()


def obtener_o_crear_identidad(db: Session, usuario) -> IdentidadFirmaSimulada:
    return obtener_identidad(db, usuario) or generar_identidad(db, usuario)


def _cargar_llave_privada(identidad: IdentidadFirmaSimulada):
    return serialization.load_pem_private_key(
        identidad.clave_privada_cifrada.encode("ascii"), password=_frase_cifrado()
    )


def datos_publicos_identidad(identidad: IdentidadFirmaSimulada) -> dict:
    """Solo datos públicos: NUNCA incluye la llave privada."""
    return {
        "nombre_ficticio": identidad.nombre_ficticio,
        "cedula_ficticia": identidad.cedula_ficticia,
        "especialidad_ficticia": identidad.especialidad_ficticia,
        "algoritmo": identidad.algoritmo,
        "huella_sha256": identidad.huella_sha256,
        "clave_publica_pem": identidad.clave_publica_pem,
        "creado_en": identidad.creado_en,
        "leyenda": LEYENDA,
    }


# ------------------------------------------------------------------ contenido de la receta
def hash_contenido_receta(receta: Receta, items: list[ItemReceta]) -> str:
    """Huella de lo que el médico recetó. Cambiar dosis, cantidades, medicamentos, etc. la altera.

    No incluye el estado ni lo ya dispensado: esos datos cambian legítimamente después de firmar.
    """
    contenido = {
        "receta_id": receta.id_PK,
        "paciente_id": receta.paciente_id_FK,
        "doctor_id": receta.doctor_id_FK,
        "items": [
            {
                "medicamento_id": it.medicamento_id_FK,
                "dosis": it.dosis,
                "frecuencia": it.frecuencia,
                "duracion": it.duracion,
                "cantidad": it.cantidad,
                "instrucciones": it.instrucciones,
                "via_administracion": it.via_administracion,
                "recargas_permitidas": it.recargas_permitidas,
            }
            for it in sorted(items, key=lambda i: i.id_PK)
        ],
    }
    return sha256_hex(_json_canonico(contenido).encode("utf-8"))


def construir_manifiesto(*, codigo: str, identificador: str, receta_id: int, hash_pdf: str,
                         hash_contenido: str, fecha: datetime, huella: str) -> str:
    return _json_canonico(
        {
            "tipo": TIPO_MANIFIESTO,
            "version": 1,
            "codigo": codigo,
            "identificador": identificador,
            "receta_id": receta_id,
            "hash_pdf_sha256": hash_pdf,
            "hash_contenido_sha256": hash_contenido,
            "fecha_firma_utc": fecha_iso_utc(fecha),
            "huella_clave_publica": huella,
            "algoritmo": f"{ALGORITMO_FIRMA}/{ALGORITMO_LLAVE}",
            "leyenda": LEYENDA,
        }
    )


def firmar_bytes(identidad: IdentidadFirmaSimulada, datos: bytes) -> str:
    try:
        llave = _cargar_llave_privada(identidad)
    except (ValueError, TypeError):
        # Cambió SECRET_KEY / FIRMA_SIM_CLAVE: la llave guardada ya no se puede descifrar
        raise FirmaError(
            "No se pudo descifrar la llave privada ficticia del médico (¿cambió SECRET_KEY o FIRMA_SIM_CLAVE?). "
            "Las firmas ya emitidas siguen siendo verificables; para firmar nuevas recetas hay que regenerar la identidad de prueba.",
            500,
        )
    firma = llave.sign(datos, _PSS, hashes.SHA256())
    return base64.b64encode(firma).decode("ascii")


# ------------------------------------------------------------------ firmar
def firmar_receta(
    db: Session,
    receta: Receta,
    items: list[ItemReceta],
    nombre_paciente: str | None,
    usuario,
    base_url: str,
) -> FirmaReceta:
    """Genera el PDF con QR, lo firma y guarda todo (el commit lo hace el llamador)."""
    from app.services.pdf_receta_firmada_service import generar_pdf_receta_firmada

    if db.query(FirmaReceta.id_PK).filter(FirmaReceta.receta_id_FK == receta.id_PK).first():
        raise FirmaError("Esta receta ya fue firmada", 409)

    identidad = obtener_o_crear_identidad(db, usuario)
    codigo = secrets.token_hex(16)  # 128 bits: no adivinable
    identificador = f"FSIM-{receta.id_PK:06d}-{codigo[:8].upper()}"
    fecha = ahora_utc()
    url = f"{base_url.rstrip('/')}{RUTA_VERIFICACION}/{codigo}"
    hash_contenido = hash_contenido_receta(receta, items)

    pdf = generar_pdf_receta_firmada(
        receta=receta,
        items=items,
        nombre_paciente=nombre_paciente,
        identidad=identidad,
        identificador=identificador,
        fecha_firma=fecha,
        url_verificacion=url,
    )
    hash_pdf = sha256_hex(pdf)
    manifiesto = construir_manifiesto(
        codigo=codigo, identificador=identificador, receta_id=receta.id_PK, hash_pdf=hash_pdf,
        hash_contenido=hash_contenido, fecha=fecha, huella=identidad.huella_sha256,
    )
    firma = FirmaReceta(
        codigo_verificacion=codigo,
        identificador=identificador,
        receta_id_FK=receta.id_PK,
        identidad_id_FK=identidad.id_PK,
        firmado_por_usuario_id_FK=usuario.id_PK,
        fecha_firma=fecha,
        algoritmo_firma=f"{ALGORITMO_FIRMA}/{ALGORITMO_LLAVE}",
        hash_pdf_sha256=hash_pdf,
        hash_contenido_sha256=hash_contenido,
        manifiesto_json=manifiesto,
        firma_b64=firmar_bytes(identidad, manifiesto.encode("utf-8")),
        pdf_original=pdf,
        tamano_pdf=len(pdf),
        url_verificacion=url,
    )
    db.add(firma)
    db.flush()
    return firma


# ------------------------------------------------------------------ historial
def registrar_evento(db: Session, firma: FirmaReceta, accion: str, *, resultado: str | None = None,
                     detalle: str | None = None, usuario_id: int | None = None,
                     ip: str | None = None, user_agent: str | None = None) -> None:
    db.add(
        HistorialFirmaReceta(
            firma_id_FK=firma.id_PK,
            receta_id_FK=firma.receta_id_FK,
            accion=accion,
            resultado=resultado,
            detalle=detalle,
            usuario_id_FK=usuario_id,
            ip=ip,
            user_agent=(user_agent or "")[:255] or None,
        )
    )


# ------------------------------------------------------------------ verificar
def verificar_firma(db: Session, firma: FirmaReceta, pdf_presentado: bytes | None = None) -> dict:
    """Verificación criptográfica completa. Nunca lanza por datos manipulados: los reporta como fallos."""
    identidad = firma.identidad
    verificaciones: list[dict] = []

    def agregar(codigo: str, descripcion: str, ok: bool) -> None:
        verificaciones.append({"codigo": codigo, "descripcion": descripcion, "ok": bool(ok)})

    try:
        manifiesto = json.loads(firma.manifiesto_json)
        if not isinstance(manifiesto, dict):
            manifiesto = {}
    except (ValueError, TypeError):
        manifiesto = {}

    # 1. Firma RSA-PSS/SHA-256 del manifiesto con la clave pública
    firma_ok = False
    try:
        pub = serialization.load_pem_public_key(identidad.clave_publica_pem.encode("ascii"))
        pub.verify(base64.b64decode(firma.firma_b64, validate=True), firma.manifiesto_json.encode("utf-8"), _PSS, hashes.SHA256())
        firma_ok = True
    except (InvalidSignature, ValueError, TypeError, binascii.Error, UnicodeError):
        firma_ok = False
    agregar("firma_criptografica", "La firma RSA (PSS + SHA-256) coincide con la clave pública del médico", firma_ok)

    # 2. La clave pública no fue reemplazada
    try:
        huella_real = huella_de_pem(identidad.clave_publica_pem)
    except (ValueError, TypeError, UnicodeError):
        huella_real = ""
    agregar(
        "clave_publica",
        "La huella de la clave pública coincide con la registrada en la firma",
        bool(huella_real) and huella_real == identidad.huella_sha256 == manifiesto.get("huella_clave_publica"),
    )

    # 3. El manifiesto firmado coincide con los datos guardados (fecha, códigos, hashes)
    coherente = (
        manifiesto.get("tipo") == TIPO_MANIFIESTO
        and manifiesto.get("codigo") == firma.codigo_verificacion
        and manifiesto.get("identificador") == firma.identificador
        and manifiesto.get("receta_id") == firma.receta_id_FK
        and manifiesto.get("hash_pdf_sha256") == firma.hash_pdf_sha256
        and manifiesto.get("hash_contenido_sha256") == firma.hash_contenido_sha256
        and manifiesto.get("fecha_firma_utc") == fecha_iso_utc(firma.fecha_firma)
    )
    agregar("manifiesto", "Los datos de la firma (fecha, identificador, hashes) no fueron modificados", coherente)

    # 4. El PDF guardado sigue siendo el que se firmó
    pdf_guardado = bytes(firma.pdf_original or b"")
    agregar(
        "pdf_original",
        "El PDF original guardado no fue modificado desde la firma",
        sha256_hex(pdf_guardado) == manifiesto.get("hash_pdf_sha256"),
    )

    # 5. La receta (medicamentos, dosis, cantidades...) no cambió después de firmar
    items = db.query(ItemReceta).filter(ItemReceta.receta_id_FK == firma.receta_id_FK).all()
    receta = db.query(Receta).filter(Receta.id_PK == firma.receta_id_FK).first()
    contenido_ok = bool(receta) and hash_contenido_receta(receta, items) == manifiesto.get("hash_contenido_sha256")
    agregar("contenido_receta", "El contenido de la receta no cambió después de la firma", contenido_ok)

    # 6. (Opcional) El PDF que presenta quien verifica es idéntico al firmado
    if pdf_presentado is not None:
        agregar(
            "pdf_presentado",
            "El PDF presentado es idéntico al documento firmado",
            sha256_hex(pdf_presentado) == manifiesto.get("hash_pdf_sha256"),
        )

    fallos = [v for v in verificaciones if not v["ok"]]
    valida = not fallos
    if valida:
        mensaje = (
            "El PDF presentado es idéntico al original firmado."
            if pdf_presentado is not None
            else "La firma es íntegra: la receta y su PDF original no han sido modificados."
        )
    elif [v["codigo"] for v in fallos] == ["pdf_presentado"]:
        mensaje = "El PDF presentado NO coincide con el original firmado: fue alterado o no es el documento firmado."
    else:
        mensaje = "Se detectaron alteraciones posteriores a la firma. Revisa las comprobaciones marcadas con ✗."

    return {
        "valida": valida,
        "resultado": "VALIDA" if valida else "INVALIDA",
        "mensaje": mensaje,
        "verificaciones": verificaciones,
        "fallos": [v["codigo"] for v in fallos],
        "pdf_comparado": pdf_presentado is not None,
    }
