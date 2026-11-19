"""Traduce los registros técnicos de auditoría a frases claras para personal sin conocimientos de sistemas."""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipamiento_sala import EquipamientoSala
from app.models.inventario import Inventario
from app.models.medicamento import Medicamento
from app.models.registro_auditoria import RegistroAuditoria
from app.models.role import Role
from app.models.sala import Sala
from app.models.usuario import Usuario
from app.utils.textos_auditoria import frase_cambios, lista_cambios, valor_legible

# ------------------------------------------------------------------ catálogos
# Tipos de acción (lo que ve el usuario) -> códigos guardados en la base
TIPOS_ACCION = {
    "crear": {"etiqueta": "Creó / registró", "codigos": ["CREATE", "CREAR"], "tono": "ok", "icono": "add-circle-outline"},
    "modificar": {"etiqueta": "Modificó", "codigos": ["UPDATE", "ACTUALIZAR"], "tono": "info", "icono": "create-outline"},
    "estado": {"etiqueta": "Cambió un estado", "codigos": ["UPDATE_ESTADO"], "tono": "info", "icono": "swap-horizontal-outline"},
    "eliminar": {"etiqueta": "Eliminó", "codigos": ["DELETE", "ELIMINAR"], "tono": "danger", "icono": "trash-outline"},
    "consultar": {"etiqueta": "Consultó", "codigos": ["CONSULTAR"], "tono": "neutral", "icono": "eye-outline"},
    "sala": {"etiqueta": "Reservó / cambió sala", "codigos": ["ASIGNAR_SALA", "CAMBIAR_SALA"], "tono": "ok", "icono": "business-outline"},
    "ia": {"etiqueta": "Usó el asistente IA", "codigos": ["CONSULTA_ASISTENTE_IA"], "tono": "info", "icono": "sparkles-outline"},
}
CODIGO_A_TIPO = {c: k for k, v in TIPOS_ACCION.items() for c in v["codigos"]}

# Áreas (lo que ve el usuario) -> tablas
AREAS = {
    "salas": {"etiqueta": "Salas y equipos", "tablas": ["salas", "equipamiento_sala", "doctor_salas"], "icono": "business-outline"},
    "inventario": {"etiqueta": "Inventario", "tablas": ["inventario", "analitica_inventario", "movimientos_inventario"], "icono": "cube-outline"},
    "citas": {"etiqueta": "Citas", "tablas": ["citas", "lista_espera"], "icono": "calendar-outline"},
    "clinico": {"etiqueta": "Pacientes y consultas", "tablas": ["recetas", "consultas", "expediente", "transferencias_paciente"], "icono": "medkit-outline"},
}
TABLA_A_AREA = {t: k for k, v in AREAS.items() for t in v["tablas"]}

ENTIDADES = {
    "salas": "la sala",
    "equipamiento_sala": "el equipo de sala",
    "doctor_salas": "la asignación de sala a un doctor",
    "inventario": "el lote de inventario",
    "analitica_inventario": "el análisis de inventario",
    "citas": "la cita",
    "lista_espera": "la lista de espera",
    "recetas": "una receta",
    "consultas": "una consulta",
    "expediente": "el expediente clínico",
    "transferencias_paciente": "una transferencia de paciente",
}


def _u(n: int, singular: str = "unidad", plural: str = "unidades") -> str:
    return f"{n} {singular if n == 1 else plural}"


def _entero(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _fecha_hora(v: dict, clave_f="fecha", clave_h="hora_inicio") -> str:
    f = valor_legible(v.get(clave_f)) if v.get(clave_f) else ""
    h = str(v.get(clave_h))[:5] if v.get(clave_h) else ""
    return " ".join(x for x in [f"el {f}" if f else "", f"a las {h}" if h else ""] if x)


# ------------------------------------------------------------------ contexto (consultas por lote)
class _Contexto:
    def __init__(self, db: Session, registros: list[RegistroAuditoria]):
        ids_usuario = {r.usuario_id_FK for r in registros if r.usuario_id_FK}
        self.usuarios: dict[int, dict] = {}
        if ids_usuario:
            for u, rol in db.execute(
                select(Usuario, Role.nombre).join(Role, Role.id_PK == Usuario.rol_id_FK, isouter=True)
                .where(Usuario.id_PK.in_(ids_usuario))
            ).all():
                partes = [u.nombre, getattr(u, "apellido_paterno", None), getattr(u, "apellido_materno", None)]
                self.usuarios[u.id_PK] = {"nombre": " ".join(p for p in partes if p) or u.correo_electronico, "rol": rol}

        ids_inv = {r.id_registro for r in registros if r.nombre_tabla == "inventario" and r.id_registro}
        self.lotes: dict[int, dict] = {}
        if ids_inv:
            for lote, med in db.execute(
                select(Inventario, Medicamento).join(Medicamento, Medicamento.id_PK == Inventario.medicamento_id_FK, isouter=True)
                .where(Inventario.id_PK.in_(ids_inv))
            ).all():
                self.lotes[lote.id_PK] = {
                    "articulo": med.nombre if med else None, "lote": lote.numero_lote,
                    "unidad": getattr(med, "unidad_medida", None) if med else None,
                }

        ids_sala = {r.id_registro for r in registros if r.nombre_tabla == "salas" and r.id_registro}
        for r in registros:
            for d in (r.valores_nuevos, r.valores_antiguos):
                if d and _entero(d.get("sala_id_FK")):
                    ids_sala.add(int(d["sala_id_FK"]))
        ids_equipo = {r.id_registro for r in registros if r.nombre_tabla == "equipamiento_sala" and r.id_registro}
        self.equipos: dict[int, dict] = {}
        if ids_equipo:
            for e in db.scalars(select(EquipamientoSala).where(EquipamientoSala.id_PK.in_(ids_equipo))).all():
                self.equipos[e.id_PK] = {"nombre": e.nombre_equipo, "sala_id": e.sala_id_FK}
                if e.sala_id_FK:
                    ids_sala.add(e.sala_id_FK)
        self.salas: dict[int, str] = {}
        if ids_sala:
            self.salas = {s.id_PK: s.nombre for s in db.scalars(select(Sala).where(Sala.id_PK.in_(ids_sala))).all()}

    def quien(self, uid: int | None) -> dict:
        if not uid:
            return {"nombre": "El sistema", "rol": None}
        return self.usuarios.get(uid, {"nombre": f"Usuario #{uid}", "rol": None})


# ------------------------------------------------------------------ explicación de un registro
def _inventario(reg: RegistroAuditoria, ctx: _Contexto, tipo: str) -> str | None:
    info = ctx.lotes.get(reg.id_registro or 0, {})
    nuevos, antiguos = reg.valores_nuevos or {}, reg.valores_antiguos or {}
    desc = reg.descripcion or ""
    art = info.get("articulo") or "un artículo"
    lote = info.get("lote") or nuevos.get("numero_lote")
    en_lote = f" (lote {lote})" if lote else ""
    a, d = _entero(antiguos.get("stock_actual")), _entero(nuevos.get("stock_actual"))

    if desc.startswith("Lote registrado"):
        q = _entero(nuevos.get("stock_actual"))
        return f"Se registró un lote nuevo de «{art}»{en_lote}" + (f" con {_u(q)}" if q is not None else "")
    if desc.startswith("Lote actualizado"):
        return f"Se corrigieron los datos del lote de «{art}»{en_lote}: {frase_cambios(antiguos, nuevos)}"
    if desc.startswith("Dispensación"):
        n = re.search(r"\((\d+)", desc)
        return "Se entregaron medicamentos de una receta" + (f" ({_u(int(n.group(1)), 'movimiento de lote', 'movimientos de lote')})" if n else "")
    m = re.match(r"^Consumo interno: (.*?) · (.*)$", desc)
    if m:
        area, motivo = m.group(1), m.group(2)
        q = abs(a - d) if a is not None and d is not None else None
        txt = f"Se usaron {_u(q)} de «{art}»{en_lote}" if q is not None else f"Se usó «{art}»{en_lote}"
        if area and area != "sin área":
            txt += f" en «{area}»"
        if motivo and motivo != "sin motivo":
            txt += f". Motivo: {motivo}"
        return txt
    m = re.match(r"^Movimiento (.+?): (.*)$", desc)
    if m:
        mov, motivo = m.group(1).strip().lower(), m.group(2).strip()
        q = abs(a - d) if a is not None and d is not None else None
        cant = _u(q) if q is not None else "unidades"
        frases = {
            "entrada": f"Entraron {cant} de «{art}»{en_lote} al inventario",
            "salida": f"Salieron {cant} de «{art}»{en_lote} del inventario",
            "merma": f"Se dieron de baja {cant} de «{art}»{en_lote} por merma (pérdida, daño o caducidad)",
            "ajuste": f"Se ajustó el conteo de «{art}»{en_lote}",
            "dispensación": f"Se entregaron {cant} de «{art}»{en_lote} a un paciente",
            "dispensacion": f"Se entregaron {cant} de «{art}»{en_lote} a un paciente",
            "consumo": f"Se usaron {cant} de «{art}»{en_lote}",
        }
        txt = frases.get(mov, f"Movimiento de inventario ({mov}) en «{art}»{en_lote}")
        if a is not None and d is not None:
            txt += f". Existencias: de {a} a {d}"
        if motivo and motivo != "sin motivo":
            txt += f". Motivo: {motivo}"
        return txt
    return None


def _explicar_uno(reg: RegistroAuditoria, ctx: _Contexto) -> dict:
    codigo = reg.accion or ""
    tipo = CODIGO_A_TIPO.get(codigo, "modificar")
    cfg = TIPOS_ACCION[tipo]
    tabla = reg.nombre_tabla or ""
    nuevos, antiguos = reg.valores_nuevos or {}, reg.valores_antiguos or {}
    area = "salas" if tipo == "sala" else ("ia" if tipo == "ia" else TABLA_A_AREA.get(tabla, "otros"))
    texto: str | None = None
    tono = cfg["tono"]

    # --- Salas
    if tabla == "salas":
        nombre = (nuevos.get("nombre") or antiguos.get("nombre") or ctx.salas.get(reg.id_registro or 0) or "sin nombre")
        if tipo == "crear":
            texto = f"Se creó la sala «{nombre}»"
        elif tipo == "eliminar":
            texto = f"Se eliminó la sala «{nombre}»"
        elif tipo == "estado":
            texto = (f"La sala «{nombre}» pasó de «{valor_legible(antiguos.get('estado'))}» "
                     f"a «{valor_legible(nuevos.get('estado'))}»")
            if nuevos.get("estado") in ("mantenimiento", "inactiva"):
                tono = "warn"
        else:
            texto = f"Se modificó la sala «{nombre}»: {frase_cambios(antiguos, nuevos)}"
    # --- Equipos
    elif tabla == "equipamiento_sala":
        eq = ctx.equipos.get(reg.id_registro or 0, {})
        nombre = nuevos.get("nombre_equipo") or antiguos.get("nombre_equipo") or eq.get("nombre") or "sin nombre"
        sala = ctx.salas.get(_entero(nuevos.get("sala_id_FK") or antiguos.get("sala_id_FK") or eq.get("sala_id")) or 0)
        donde = f" de la sala «{sala}»" if sala else ""
        if tipo == "crear":
            texto = f"Se agregó el equipo «{nombre}»{donde}"
        elif tipo == "eliminar":
            texto = f"Se eliminó el equipo «{nombre}»{donde}"
        else:
            texto = f"Se modificó el equipo «{nombre}»{donde}: {frase_cambios(antiguos, nuevos)}"
            if nuevos.get("estado") == "fuera_de_servicio":
                tono = "warn"
    # --- Uso de salas en citas
    elif tipo == "sala":
        sala = ctx.salas.get(_entero(nuevos.get("sala_id_FK")) or 0) or "una sala"
        cuando = _fecha_hora(nuevos)
        if codigo == "ASIGNAR_SALA":
            texto = f"Se reservó la sala «{sala}» para la cita #{reg.id_registro} {cuando}".strip()
        else:
            ant = ctx.salas.get(_entero(antiguos.get("sala_id_FK")) or 0)
            texto = (f"La cita #{reg.id_registro} cambió de sala «{ant}» a «{sala}»" if ant and ant != sala
                     else f"La cita #{reg.id_registro} en la sala «{sala}» se reprogramó {cuando}").strip()
    # --- Inventario
    elif tabla == "inventario":
        texto = _inventario(reg, ctx, tipo)
        d = (reg.descripcion or "").lower()
        if any(x in d for x in ("merma", "ajuste")):
            tono = "warn"
    elif tabla == "analitica_inventario":
        dias = nuevos.get("horizonte_dias")
        texto = "Se consultó el análisis de inventario" + (f" (próximos {dias} días)" if dias else "")
        if nuevos.get("origen") == "ia":
            texto += " con inteligencia artificial"
    elif tipo == "ia":
        texto = f"Se usó el asistente de IA durante la cita #{reg.id_registro}" if reg.id_registro else "Se usó el asistente de IA"
        if reg.descripcion and "advertencia" in reg.descripcion:
            m = re.search(r"Se detectaron (\d+) advertencias", reg.descripcion)
            if m:
                texto += f" ({m.group(1)} advertencia(s) de medicamentos)"

    # --- Respaldo genérico
    if not texto:
        entidad = ENTIDADES.get(tabla, "un registro")
        verbo = {"crear": "Se creó", "modificar": "Se modificó", "eliminar": "Se eliminó", "consultar": "Se consultó",
                 "estado": "Se cambió el estado de"}.get(tipo, "Se realizó una acción sobre")
        texto = f"{verbo} {entidad}"
        if reg.descripcion:
            texto += f" — {reg.descripcion.rstrip('.')}"
    if tipo == "eliminar":
        tono = "danger"

    modo = "alta" if tipo == "crear" else "baja" if tipo == "eliminar" else "cambio"
    cambios = (
        lista_cambios(None, nuevos, solo_cambiados=False) if modo == "alta"
        else lista_cambios(antiguos, None, solo_cambiados=False) if modo == "baja"
        else lista_cambios(antiguos, nuevos)
    )
    quien = ctx.quien(reg.usuario_id_FK)
    return {
        "usuario_nombre": quien["nombre"],
        "usuario_rol": quien["rol"],
        "area": area,
        "area_texto": AREAS.get(area, {}).get("etiqueta") or ("Inteligencia artificial" if area == "ia" else "Otros"),
        "tipo_accion": tipo,
        "accion_texto": cfg["etiqueta"],
        "resumen": texto,
        "tono": tono,
        "icono": cfg["icono"],
        "modo_cambios": modo,
        "cambios": cambios,
    }


def explicar_lote(db: Session, registros: list[RegistroAuditoria]) -> list[dict]:
    ctx = _Contexto(db, registros)
    return [_explicar_uno(r, ctx) for r in registros]


def catalogo() -> dict:
    return {
        "areas": [{"valor": "", "etiqueta": "Todas las áreas", "icono": "apps-outline"}]
        + [{"valor": k, "etiqueta": v["etiqueta"], "icono": v["icono"]} for k, v in AREAS.items()],
        "acciones": [{"valor": "", "etiqueta": "Todo tipo de acciones"}]
        + [{"valor": k, "etiqueta": v["etiqueta"], "tono": v["tono"], "icono": v["icono"]} for k, v in TIPOS_ACCION.items()],
    }
