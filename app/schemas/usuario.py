from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.validaciones import (
    fecha_nacimiento_de_curp,
    normalizar_correo,
    validar_curp,
    validar_nombre_persona,
    validar_rfc,
)


GENEROS_VALIDOS = ("Femenino", "Masculino", "Otro")
FECHA_NACIMIENTO_MINIMA = date(1900, 1, 1)


def _opcional(valor: str | None) -> str | None:
    """Convierte cadenas vacías en None (campos opcionales)."""
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


class UsuarioCrear(BaseModel):
    """
    Datos para crear una cuenta desde el formulario administrativo.

    Las reglas que dependen del rol (p. ej. CURP obligatoria para pacientes) se
    aplican en `app.services.usuario_service`, que es común a este formulario y
    al registro público.
    """

    # Datos generales del usuario
    nombre: str
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    correo_electronico: EmailStr
    password: str
    rol_id_FK: int

    # Datos de paciente
    apellido: str | None = None  # Compatibilidad: apellido único anterior
    fecha_nacimiento: date | None = None
    genero: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    curp: str | None = None

    # Datos de doctor
    especialidad_id_FK: int | None = None  # Compatibilidad
    especialidad_ids: list[int] = Field(default_factory=list)
    numero_licencia: str | None = None
    rfc: str | None = None
    costo_consulta: float | None = Field(default=None, ge=0)

    @field_validator("correo_electronico", mode="before")
    @classmethod
    def _normalizar_correo(cls, v):
        return normalizar_correo(v) if isinstance(v, str) else v

    @field_validator("nombre")
    @classmethod
    def _validar_nombre(cls, v: str) -> str:
        return validar_nombre_persona(v, "El nombre")

    @field_validator("apellido_paterno")
    @classmethod
    def _validar_paterno(cls, v: str | None) -> str | None:
        v = _opcional(v)
        return validar_nombre_persona(v, "El apellido paterno") if v else None

    @field_validator("apellido_materno")
    @classmethod
    def _validar_materno(cls, v: str | None) -> str | None:
        v = _opcional(v)
        return validar_nombre_persona(v, "El apellido materno") if v else None

    @field_validator("apellido")
    @classmethod
    def _validar_apellido_heredado(cls, v: str | None) -> str | None:
        v = _opcional(v)
        return validar_nombre_persona(v, "El apellido") if v else None

    @field_validator("curp")
    @classmethod
    def _validar_curp(cls, v: str | None) -> str | None:
        v = _opcional(v)
        return validar_curp(v) if v else None

    @field_validator("rfc")
    @classmethod
    def _validar_rfc(cls, v: str | None) -> str | None:
        v = _opcional(v)
        return validar_rfc(v) if v else None

    @model_validator(mode="after")
    def _compatibilidad_apellido(self):
        # Clientes anteriores enviaban un único `apellido`: se toma como paterno.
        if not self.apellido_paterno and self.apellido:
            self.apellido_paterno = self.apellido
        return self


class PacienteRegistro(BaseModel):
    """
    Cuerpo del registro PÚBLICO de pacientes (sin sesión).

    Deliberadamente NO incluye `rol_id_FK`, `estado` ni datos de doctor:
    el rol lo fija el servidor y, con `extra="forbid"`, cualquier intento de
    enviar campos adicionales (p. ej. `rol_id_FK: 1`) se rechaza con 422.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: str
    apellido_paterno: str
    apellido_materno: str | None = None
    curp: str
    correo_electronico: EmailStr
    password: str = Field(min_length=8)

    fecha_nacimiento: date
    genero: str
    telefono: str | None = None
    direccion: str | None = None

    @field_validator("correo_electronico", mode="before")
    @classmethod
    def _normalizar_correo(cls, v):
        return normalizar_correo(v) if isinstance(v, str) else v

    @field_validator("nombre")
    @classmethod
    def _validar_nombre(cls, v: str) -> str:
        return validar_nombre_persona(v, "El nombre")

    @field_validator("apellido_paterno")
    @classmethod
    def _validar_paterno(cls, v: str) -> str:
        return validar_nombre_persona(v, "El apellido paterno")

    @field_validator("apellido_materno")
    @classmethod
    def _validar_materno(cls, v: str | None) -> str | None:
        v = _opcional(v)
        return validar_nombre_persona(v, "El apellido materno") if v else None

    @field_validator("curp")
    @classmethod
    def _validar_curp(cls, v: str) -> str:
        return validar_curp(v)

    @field_validator("password")
    @classmethod
    def _validar_password(cls, v: str) -> str:
        # bcrypt solo procesa los primeros 72 bytes: se rechaza en vez de truncar.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede exceder 72 bytes")
        return v

    @field_validator("fecha_nacimiento")
    @classmethod
    def _validar_fecha(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        if v < FECHA_NACIMIENTO_MINIMA:
            raise ValueError("La fecha de nacimiento no es válida")
        return v

    @field_validator("genero")
    @classmethod
    def _validar_genero(cls, v: str) -> str:
        v = v.strip()
        if v not in GENEROS_VALIDOS:
            raise ValueError("El sexo/género debe ser Femenino, Masculino u Otro")
        return v

    @model_validator(mode="after")
    def _fecha_coincide_con_curp(self):
        # La CURP ya viene validada: su fecha debe coincidir con la capturada.
        if self.fecha_nacimiento != fecha_nacimiento_de_curp(self.curp):
            raise ValueError("La fecha de nacimiento no coincide con la de la CURP")
        return self

    @field_validator("telefono")
    @classmethod
    def _validar_telefono(cls, v: str | None) -> str | None:
        v = _opcional(v)
        if v is None:
            return None
        digitos = sum(c.isdigit() for c in v)
        if not (7 <= digitos <= 15) or any(c not in "0123456789+-() " for c in v):
            raise ValueError("El teléfono no es válido (7 a 15 dígitos)")
        return v

    @field_validator("direccion")
    @classmethod
    def _limpiar_opcionales(cls, v: str | None) -> str | None:
        return _opcional(v)


class UsuarioResponse(BaseModel):
    id_PK: int
    nombre: str
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    correo_electronico: EmailStr
    rol_id_FK: int | None
    estado: str | None

    class Config:
        from_attributes = True


class UsuarioActualizar(BaseModel):
    nombre: str | None = None
    apellido_paterno: str | None = None
    apellido_materno: str | None = None
    correo_electronico: EmailStr | None = None
    telefono: str | None = None
    rol_id_FK: int | None = None
    estado: str | None = None