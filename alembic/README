# 🩺 VITALIA

## Sistema Integral para la Gestión y Automatización de Clínicas

**Nombre del equipo:** TEAM VITALIA
**Proyecto:** VITALIA
**Fecha de vencimiento:** **PENDIENTE**

---

## 📋 Descripción del proyecto

VITALIA es una aplicación web y móvil orientada a la gestión integral de clínicas.

El sistema busca centralizar y automatizar procesos relacionados con:

* Usuarios y roles.
* Citas.
* Consultas médicas.
* Expedientes clínicos.
* Recetas.
* Medicamentos.
* Inventario.
* Disponibilidad de medicamentos.
* Gestión administrativa.

---

# 🎯 Objetivo general

Desarrollar una plataforma que permita organizar y automatizar los principales procesos de una clínica, facilitando la administración de usuarios, atención médica, expedientes, citas, recetas e inventario.

---

# 🔄 Flujo principal

```text
CITA
  ↓
CONSULTA
  ↓
EXPEDIENTE CLÍNICO
  ↓
RECETA
  ↓
CONSULTA DE INVENTARIO
  ↓
DISPONIBILIDAD
  ↓
┌───────────────────────┐
│                       │
▼                       ▼
DISPENSACIÓN       NO DISPONIBLE
                        ↓
                 AVISO DE NO
                 DISPONIBILIDAD
```

---

# 👤 Roles del sistema

| Rol           | Función                                                    |
| ------------- | ---------------------------------------------------------- |
| Administrador | Administración general del sistema y usuarios.             |
| Médico        | Gestión de consultas, expedientes, diagnósticos y recetas. |
| Paciente      | Consulta y seguimiento de su información y citas.          |
| Recepción     | Gestión de citas y procesos administrativos.               |

---

# 🖥️ Frontend

El frontend está desarrollado con:

* React Native
* Expo
* Expo Router
* AuthContext

### Funcionalidades desarrolladas

* Pantalla de inicio de sesión.
* Inicio de sesión mediante correo y contraseña.
* Validación de contraseña de mínimo 8 caracteres.
* Mostrar/ocultar contraseña.
* Manejo de carga durante el inicio de sesión.
* Manejo de autenticación mediante `AuthContext`.
* Redirección dependiendo del rol.
* Estructura administrativa.
* Administración de usuarios.
* Creación de usuarios.
* Selección de roles.
* Sidebar para versión web.
* Diseño visual de VITALIA.
* Logo y lema: **“Tu salud, en un solo lugar.”**

---

# ⚙️ Backend

El backend está desarrollado utilizando:

* Python
* FastAPI
* API REST
* Bearer Token
* Pytest

### Endpoint de autenticación

```text
POST /api/auth/login
```

### Endpoint de usuarios

```text
/api/usuarios/
```

---

# 🔐 Autenticación

El sistema utiliza autenticación mediante correo electrónico y contraseña.

```text
Correo electrónico
        +
Contraseña
        ↓
Validación
        ↓
Token
        ↓
Acceso al sistema
```

---

# 👥 Administración de usuarios

Actualmente se contempla:

* Visualización de usuarios.
* Creación de usuarios.
* Selección de rol.
* Validación de contraseña.
* Protección de rutas mediante autenticación.

Rutas trabajadas:

```text
/admin
/admin/usuarios
/admin/usuarios/crear
```

---

# 🏥 Expediente clínico

El expediente clínico contempla:

* Datos del paciente.
* Antecedentes.
* Alergias.
* Enfermedades.
* Consultas anteriores.
* Diagnósticos.
* Tratamientos.
* Medicamentos.
* Estudios.
* Notas médicas.

---

# 📅 Citas

VITALIA contempla la gestión de citas médicas.

También se considera la integración con **Google Calendar** para registrar o enviar información relacionada con las citas.

---

# 💊 Recetas e inventario

El sistema contempla la relación entre las recetas médicas y el inventario.

```text
Médico
  ↓
Receta
  ↓
Medicamento
  ↓
Consulta de inventario
  ↓
¿Disponible?
  ├── Sí → Dispensación
  └── No → Aviso de no disponibilidad
```

También se contempla:

* Disponibilidad de medicamentos.
* Contraindicaciones.
* Dispensación.
* Avisos de medicamentos no disponibles.
* Transferencias entre médicos.

---

# 🧪 Pruebas automatizadas

Se han realizado pruebas automatizadas utilizando **pytest** para validar el funcionamiento de la autenticación y el acceso a usuarios.

### Pruebas realizadas

1. ✅ Login con correo inválido.
2. ✅ Login sin datos.
3. ✅ Acceso sin token.
4. ✅ Login correcto.
5. ✅ Contraseña incorrecta.
6. ✅ Usuario inactivo.
7. ✅ Administrador puede consultar usuarios.
8. ✅ Usuario normal no puede consultar usuarios.
9. ✅ La respuesta contiene los usuarios esperados.

### Resultado

Las pruebas de acceso no autenticado trabajadas hasta ahora fueron ejecutadas correctamente.

### Comando utilizado

```bash
pytest
```

**Autor de esta actividad:** Iris Jaqueline Cruz Clemente

---

# 🧰 Tecnologías utilizadas

| Tecnología   | Uso                           |
| ------------ | ----------------------------- |
| React Native | Aplicación                    |
| Expo         | Desarrollo del frontend       |
| Expo Router  | Navegación                    |
| Python       | Backend                       |
| FastAPI      | API                           |
| Pytest       | Pruebas                       |
| Git          | Control de versiones          |
| GitHub       | Repositorios                  |
| API REST     | Comunicación frontend/backend |

---

# 📁 Repositorios

### Frontend

```text
team-vitalia/vitalia-app
```

### Backend

```text
team-vitalia/vitalia-api
```

---

# 🌿 Git y GitHub

El proyecto utiliza Git y GitHub para el control de versiones y trabajo colaborativo.

Se utilizan commits para registrar los avances realizados por los integrantes.

---

# 📊 Estado actual del proyecto

### Realizado

* [x] Estructura inicial del proyecto.
* [x] Repositorios de frontend y backend.
* [x] Login.
* [x] Autenticación.
* [x] Bearer Token.
* [x] Manejo de roles.
* [x] Estructura administrativa.
* [x] Consulta de usuarios.
* [x] Creación de usuarios.
* [x] Pruebas iniciales con pytest.
* [x] Control de versiones con Git/GitHub.

### Pendiente

* [ ] Completar expediente clínico.
* [ ] Completar módulo de citas.
* [ ] Integración con Google Calendar.
* [ ] Completar recetas.
* [ ] Completar inventario.
* [ ] Disponibilidad de medicamentos.
* [ ] Dispensación.
* [ ] Contraindicaciones.
* [ ] Transferencias entre médicos.
* [ ] Ampliar pruebas automatizadas.
* [ ] Documentación final.
* [ ] Fecha de vencimiento.

---

# 📅 Fecha de vencimiento

**PENDIENTE**

---

# 🩺 VITALIA

> **“Tu salud, en un solo lugar.”**

**Proyecto académico — TEAM VITALIA**
