"""Verificación PÚBLICA de recetas con firma electrónica SIMULADA (destino del QR).

No requiere sesión. Solo expone: identificador de receta, médico ficticio, fecha de
firma y resultado de la validación. NO expone datos del paciente ni de la receta.
"""
import html
import io
import re
import secrets

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.firma_receta import FirmaReceta
from app.models.receta import Receta
from app.services import firma_simulada_service as svc
from app.services.pdf_receta_firmada_service import _fecha_utc_y_local
from app.utils.auditoria import ip_desde_request

router = APIRouter(prefix="/api/verificar-receta", tags=["Verificación pública de firma simulada"])

_CODIGO = re.compile(r"^[0-9a-f]{32}$")
MAX_PDF_BYTES = 5 * 1024 * 1024


def _firma_publica(db: Session, codigo: str) -> FirmaReceta | None:
    if not _CODIGO.match(codigo):
        return None
    return db.query(FirmaReceta).filter(FirmaReceta.codigo_verificacion == codigo).first()


def _datos_publicos(db: Session, firma: FirmaReceta, resultado: dict) -> dict:
    ident = firma.identidad
    receta = db.query(Receta).filter(Receta.id_PK == firma.receta_id_FK).first()
    utc, local = _fecha_utc_y_local(firma.fecha_firma)
    return {
        "resultado": resultado["resultado"],
        "valida": resultado["valida"],
        "mensaje": resultado["mensaje"],
        "receta_id": firma.receta_id_FK,
        "identificador": firma.identificador,
        "medico": {
            "nombre_ficticio": ident.nombre_ficticio,
            "cedula_ficticia": ident.cedula_ficticia,
            "especialidad_ficticia": ident.especialidad_ficticia,
        },
        "fecha_firma_utc": svc.fecha_iso_utc(firma.fecha_firma),
        "fecha_firma_texto": utc,
        "fecha_firma_hora_servidor": local,
        "algoritmo": firma.algoritmo_firma,
        "huella_clave_publica": ident.huella_sha256,
        "estado_receta": receta.estado if receta else None,
        "verificaciones": resultado["verificaciones"],
        "fallos": resultado["fallos"],
        "pdf_comparado": resultado["pdf_comparado"],
        "leyenda": svc.LEYENDA,
    }


def _verificar_y_registrar(db: Session, firma: FirmaReceta, request: Request, *, origen: str,
                           pdf: bytes | None = None) -> dict:
    resultado = svc.verificar_firma(db, firma, pdf)
    svc.registrar_evento(
        db, firma, "VERIFICACION_PDF" if pdf is not None else "VERIFICACION",
        resultado=resultado["resultado"],
        detalle=f"origen={origen}; fallos={','.join(resultado['fallos']) or 'ninguno'}",
        ip=ip_desde_request(request), user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return resultado


# ------------------------------------------------------------------ página HTML (la que abre el QR)
_CSS = """
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f3f7f6;color:#17302c}
header{background:#247F76;color:#fff;padding:14px 18px;font-weight:700;font-size:17px}
.aviso{background:#FFF3C4;border-top:2px solid #B7791F;border-bottom:2px solid #B7791F;color:#6B4200;font-weight:800;text-align:center;padding:10px 12px;font-size:13px;letter-spacing:.2px}
main{max-width:640px;margin:0 auto;padding:16px}
.res{border-radius:16px;padding:20px 16px;text-align:center;color:#fff;margin-bottom:16px}
.res.ok{background:#1E8E5A}.res.mal{background:#C0392B}.res.nf{background:#6B7B77}
.res .ic{font-size:44px;line-height:1}.res h1{margin:6px 0 4px;font-size:22px}.res p{margin:0;font-size:14px;opacity:.95}
.card{background:#fff;border:1px solid #d8e5e2;border-radius:14px;padding:14px 16px;margin-bottom:14px}
.card h2{margin:0 0 8px;font-size:14px;color:#247F76;text-transform:uppercase;letter-spacing:.4px}
dl{margin:0;font-size:14px}dt{color:#5B6B67;margin-top:9px;font-size:12.5px}dd{margin:1px 0 0;font-weight:600;word-break:break-word}
@supports (display:grid){dl{display:grid;grid-template-columns:128px 1fr;gap:7px 10px}dt{margin-top:0;font-size:14px}dd{margin:0}}
ul{list-style:none;margin:0;padding:0}li{position:relative;padding:7px 0 7px 26px;border-top:1px solid #edf3f1;font-size:13.5px}li:first-child{border-top:0}
li .b{position:absolute;left:2px;top:6px;font-size:16px}.b{font-weight:800}.b.ok{color:#1E8E5A}.b.mal{color:#C0392B}
input[type=file]{width:100%;margin:8px 0}button{background:#247F76;color:#fff;border:0;border-radius:10px;padding:11px 16px;font-size:15px;font-weight:700;width:100%}
button:disabled{opacity:.6}#resp{margin-top:12px}.rbox{border-radius:12px;padding:12px;font-weight:700;font-size:14px}.rbox.ok{background:#E3F5EC;color:#14653F}.rbox.mal{background:#FBE5E2;color:#8E2A1F}
.pie{font-size:12px;color:#5B6B67;text-align:center;padding:6px 16px 28px}code{font-size:12px;word-break:break-all}
"""

_JS = """
(function(){
  var btn=document.getElementById('comparar'),inp=document.getElementById('archivo'),out=document.getElementById('resp');
  if(!btn){return;}
  btn.addEventListener('click',function(){
    var f=inp.files&&inp.files[0]; out.textContent='';
    if(!f){out.textContent='Selecciona el archivo PDF a comprobar.';return;}
    btn.disabled=true; btn.textContent='Comprobando…';
    fetch(window.location.pathname.replace(/\\/+$/,'')+'/documento',{method:'POST',headers:{'Content-Type':'application/pdf'},body:f})
      .then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});})
      .then(function(x){
        var box=document.createElement('div'); var ok=x.j&&x.j.valida===true;
        box.className='rbox '+(ok?'ok':'mal');
        box.textContent=(ok?'✓ PDF AUTÉNTICO: ':'✗ PDF NO VÁLIDO: ')+(x.j.mensaje||x.j.detail||'Error de verificación');
        out.textContent=''; out.appendChild(box);
      })
      .catch(function(){out.textContent='No se pudo comprobar el PDF.';})
      .finally(function(){btn.disabled=false;btn.textContent='Comprobar este PDF';});
  });
})();
"""


def _e(valor) -> str:
    return html.escape("—" if valor in (None, "") else str(valor), quote=True)


def _pagina(titulo_estado: str, clase: str, icono: str, mensaje: str, datos: dict | None, nonce: str) -> str:
    detalle = ""
    if datos:
        medico = datos["medico"]
        filas = [
            ("Receta", f"No. {datos['receta_id']:06d}"),
            ("Identificador de firma", datos["identificador"]),
            ("Médico (ficticio)", medico["nombre_ficticio"]),
            ("Cédula (ficticia)", medico["cedula_ficticia"]),
            ("Especialidad", medico["especialidad_ficticia"]),
            ("Fecha de firma", datos["fecha_firma_texto"]),
            ("Hora del servidor", datos["fecha_firma_hora_servidor"]),
            ("Algoritmo", datos["algoritmo"]),
            ("Huella clave pública", datos["huella_clave_publica"][:32] + "…"),
            ("Estado de la receta", datos["estado_receta"]),
        ]
        dl = "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in filas)
        lis = "".join(
            f'<li><span class="b {"ok" if v["ok"] else "mal"}">{"✓" if v["ok"] else "✗"}</span><span>{_e(v["descripcion"])}</span></li>'
            for v in datos["verificaciones"]
        )
        detalle = (
            f'<section class="card"><h2>Datos de la firma</h2><dl>{dl}</dl></section>'
            f'<section class="card"><h2>Comprobaciones criptográficas</h2><ul>{lis}</ul></section>'
            '<section class="card"><h2>¿Tienes el PDF? Compruébalo</h2>'
            '<div style="font-size:13px;color:#5B6B67">Selecciona el PDF de la receta para confirmar que es idéntico al original firmado.</div>'
            '<input type="file" id="archivo" accept="application/pdf,.pdf"><button id="comparar" type="button">Comprobar este PDF</button>'
            '<div id="resp" role="status"></div></section>'
        )
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Verificación de receta · VITALIA</title><style>{_CSS}</style></head><body>
<header>VITALIA · Verificación de firma de receta</header>
<div class="aviso">{_e(svc.LEYENDA)}</div>
<main>
<section class="res {clase}" role="status"><div class="ic">{icono}</div><h1>{_e(titulo_estado)}</h1><p>{_e(mensaje)}</p></section>
{detalle}
<p class="pie">Simulación académica con datos y llaves ficticios. No usa e.firma ni certificados reales y no tiene validez jurídica.
Esta página no muestra datos del paciente.</p>
</main><script nonce="{nonce}">{_JS}</script></body></html>"""


def _respuesta_html(contenido: str, nonce: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        contenido,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (
                f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
            ),
        },
    )


@router.get("/{codigo}", response_class=HTMLResponse)
def pagina_verificacion(codigo: str, request: Request, db: Session = Depends(get_db)):
    """Página que se abre al escanear el QR."""
    nonce = secrets.token_urlsafe(16)
    firma = _firma_publica(db, codigo)
    if not firma:
        return _respuesta_html(
            _pagina("FIRMA NO ENCONTRADA", "nf", "?", "No existe una firma con ese código. Verifica que el QR sea el de una receta de VITALIA.", None, nonce),
            nonce, 404,
        )
    resultado = _verificar_y_registrar(db, firma, request, origen="pagina_qr")
    datos = _datos_publicos(db, firma, resultado)
    if resultado["valida"]:
        contenido = _pagina("FIRMA VÁLIDA", "ok", "✓", resultado["mensaje"], datos, nonce)
    else:
        contenido = _pagina("FIRMA INVÁLIDA — DOCUMENTO ALTERADO", "mal", "✗", resultado["mensaje"], datos, nonce)
    return _respuesta_html(contenido, nonce)


@router.get("/{codigo}/json")
def verificacion_json(codigo: str, request: Request, db: Session = Depends(get_db)):
    firma = _firma_publica(db, codigo)
    if not firma:
        return JSONResponse(
            {"resultado": "NO_ENCONTRADA", "valida": False, "mensaje": "No existe una firma con ese código.", "leyenda": svc.LEYENDA},
            status_code=404,
        )
    resultado = _verificar_y_registrar(db, firma, request, origen="json")
    return _datos_publicos(db, firma, resultado)


@router.post("/{codigo}/documento")
async def verificar_documento(codigo: str, request: Request, db: Session = Depends(get_db)):
    """Compara un PDF (cuerpo de la petición, `application/pdf`) con el documento originalmente firmado."""
    firma = _firma_publica(db, codigo)
    if not firma:
        return JSONResponse({"resultado": "NO_ENCONTRADA", "valida": False, "mensaje": "No existe una firma con ese código."}, status_code=404)
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el máximo de 5 MB")
    contenido = await request.body()
    if len(contenido) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el máximo de 5 MB")
    if not contenido:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo")
    resultado = _verificar_y_registrar(db, firma, request, origen="carga_pdf", pdf=contenido)
    return _datos_publicos(db, firma, resultado)


@router.get("/{codigo}/qr.png")
def qr_png(codigo: str, db: Session = Depends(get_db)):
    """PNG del QR de esta receta (solo contiene la URL pública de validación)."""
    firma = _firma_publica(db, codigo)
    if not firma:
        raise HTTPException(status_code=404, detail="Firma no encontrada")
    img = qrcode.make(firma.url_verificacion, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
