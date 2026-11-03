import re
import unicodedata
from datetime import date

_ENTIDADES = (
    "AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|"
    "SR|TC|TS|TL|VZ|YN|ZS|NE"
)
CURP_REGEX = re.compile(
    r"^[A-Z][AEIOUX][A-Z]{2}"         
    r"(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])"  
    r"[HMX]"                           
    rf"({_ENTIDADES})"                 
    r"[B-DF-HJ-NP-TV-Z]{3}"            
    r"[A-Z\d]\d$"                      
)

RFC_REGEX = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z\d]{3}$")
_LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
NOMBRE_REGEX = re.compile(
    rf"^[{_LETRAS}]+(?:(?:\.? |['\-])[{_LETRAS}]+)*\.?$"
)

LONGITUD_MAX_NOMBRE = 100


def _espacios(valor: str) -> str:
    """Quita espacios de los extremos y colapsa los repetidos."""
    return re.sub(r"\s+", " ", valor).strip()


def normalizar_correo(valor: str) -> str:
    """Correo en minúsculas y sin espacios en los extremos."""
    return valor.strip().lower()


def normalizar_curp(valor: str) -> str:
    """CURP en mayúsculas, sin espacios ni guiones."""
    return re.sub(r"[\s\-]", "", valor).upper()


def normalizar_rfc(valor: str) -> str:
    """RFC en mayúsculas, sin espacios ni guiones."""
    return re.sub(r"[\s\-]", "", valor).upper()


def normalizar_nombre(valor: str) -> str:
    """Nombre/apellido sin espacios sobrantes y con unicode compuesto (NFC)."""
    return unicodedata.normalize("NFC", _espacios(valor))


def validar_nombre_persona(valor: str, etiqueta: str) -> str:
    """Valida y normaliza un nombre o apellido. Lanza ValueError con mensaje claro."""
    limpio = normalizar_nombre(valor)
    if not limpio:
        raise ValueError(f"{etiqueta} es obligatorio")
    if len(limpio) > LONGITUD_MAX_NOMBRE:
        raise ValueError(f"{etiqueta} no puede exceder {LONGITUD_MAX_NOMBRE} caracteres")
    if not NOMBRE_REGEX.match(limpio):
        raise ValueError(
            f"{etiqueta} solo puede contener letras, espacios, apóstrofos, puntos y guiones"
        )
    return limpio


def validar_curp(valor: str) -> str:
    """Devuelve la CURP normalizada o lanza ValueError si no es válida."""
    curp = normalizar_curp(valor)
    if len(curp) != 18:
        raise ValueError("La CURP debe tener exactamente 18 caracteres")

    coincidencia = CURP_REGEX.match(curp)
    if not coincidencia:
        raise ValueError("El formato de la CURP no es válido")

    anio = int(coincidencia.group(1)) + (1900 if curp[16].isdigit() else 2000)
    try:
        nacimiento = date(anio, int(coincidencia.group(2)), int(coincidencia.group(3)))
    except ValueError:
        raise ValueError("La fecha de nacimiento contenida en la CURP no es válida")
    if nacimiento > date.today():
        raise ValueError("La fecha de nacimiento contenida en la CURP no es válida")

    return curp


def validar_rfc(valor: str) -> str:
    """Devuelve el RFC normalizado (12 o 13 caracteres) o lanza ValueError."""
    rfc = normalizar_rfc(valor)
    if len(rfc) not in (12, 13):
        raise ValueError("El RFC debe tener 12 o 13 caracteres")
    if not RFC_REGEX.match(rfc):
        raise ValueError("El formato del RFC no es válido")
    return rfc


def componer_apellido(paterno: str | None, materno: str | None) -> str:
    """Apellido completo ('paterno materno') para la columna heredada `pacientes.apellido`."""
    return " ".join(p for p in (paterno, materno) if p).strip()


def fecha_nacimiento_de_curp(curp: str) -> date:
    """
    Fecha de nacimiento contenida en una CURP VÁLIDA (ya normalizada).
    Posición 17: dígito = nacidos en 1900-1999, letra = 2000 en adelante.
    """
    anio = int(curp[4:6]) + (1900 if curp[16].isdigit() else 2000)
    return date(anio, int(curp[6:8]), int(curp[8:10]))