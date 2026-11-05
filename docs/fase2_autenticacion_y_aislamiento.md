# Documentacion Tecnica: Fase 2 - Autenticacion Multi-Tenant y Aislamiento Logico en CRUD

## 1. Resumen de la Implementacion
La Fase 2 consolida la seguridad multi-inquilino en la capa de autenticacion y en las operaciones de lectura y escritura de la API RESTful. Se garantiza que cada usuario opere exclusivamente dentro de los limites de su clinica y de acuerdo a los cupos de su plan de suscripcion.

## 2. Actualizacion de Autenticacion (JWT y Dependencias)
### 2.1 Emision del Token (`app.core.security` y `app.services.auth_service`)
- La funcion `crear_access_token` ahora admite e inyecta obligatoriamente la clave `clinica_id` dentro del payload JWT.
- El servicio `autenticar_usuario` extrae `usuario.clinica_id_FK` y lo transfiere al payload durante el inicio de sesion exitoso.

### 2.2 Resolucion del Inquilino Actual (`app.core.dependencies`)
- La dependencia `get_current_user` decodifica `payload.get("clinica_id")` y lo asigna directamente a `usuario.clinica_id_FK` (y por extension a su sinonimo `usuario.clinica_id`).
- De este modo, todas las rutas que inyectan `usuario_actual = Depends(get_current_user)` reciben el identificador del tenant directamente en el contexto de ejecucion.

## 3. Servicio de Validacion de Limites de Suscripcion (`app.services.suscripcion_service`)
Se implemento el modulo `suscripcion_service.py` con dos funciones clave:
- `validar_limite_personal(db, clinica_id)`: Consulta la cantidad actual de usuarios registrados para la clinica (`db.query(Usuario).filter(Usuario.clinica_id_FK == clinica_id).count()`) y la compara contra `plan.limite_personal`. Si `total >= limite`, emite un `HTTPException` con codigo de estado 403.
- `validar_limite_pacientes(db, clinica_id)`: Consulta el total de pacientes del tenant (`db.query(Paciente).filter(Paciente.clinica_id_FK == clinica_id).count()`) y lo compara contra `plan.limite_pacientes`. Si se excede, lanza un `HTTPException` 403.

## 4. Aislamiento Logico en Endpoints CRUD
### 4.1 Endpoints de Usuarios (`app.routers.usuarios`)
- `GET /api/usuarios/`: Aplica obligatoriamente `.filter(Usuario.clinica_id_FK == usuario_actual.clinica_id_FK)`.
- `GET /api/usuarios/{usuario_id}`: Filtra por clave primaria y tenant del usuario en sesion. Retorna 404 si el usuario pertenece a otra clinica.
- `POST /api/usuarios/`: Invoca `validar_limite_personal` antes de la creacion y asigna forzosamente `clinica_id = usuario_actual.clinica_id_FK`, ignorando cualquier parametro externo en el cuerpo de la peticion.
- `PATCH /api/usuarios/{usuario_id}`: Restringe modificaciones al inquilino del usuario autenticado.

### 4.2 Endpoints de Pacientes (`app.routers.pacientes`)
- `GET /api/pacientes/`: Aplica `.filter(Paciente.clinica_id_FK == usuario_actual.clinica_id_FK)`.
- `GET /api/pacientes/{paciente_id}`: Consulta vinculando `Paciente.id_PK == paciente_id` y `Paciente.clinica_id_FK == usuario_actual.clinica_id_FK`. Devuelve 404 si el registro no pertenece al inquilino.
- `POST /api/pacientes/`: Valida `validar_limite_pacientes` y asigna automaticamente `clinica_id_FK = usuario_actual.clinica_id_FK`.
- `POST /api/pacientes/{paciente_id}/alergias`: Impide la modificacion de expedientes de pacientes ajenos a la clinica del usuario en sesion.

## 5. Pruebas Unitarias Pytest (`tests/test_fase2_multitenant.py`)
Se desarrollaron casos de prueba que certifican:
1. Inyeccion de `clinica_id` en JWT y extraccion exacta en `get_current_user`.
2. Bloqueo con HTTP 403 al intentar registrar un 4to usuario en una clinica con plan "Basico" (limite de 3 cuentas de personal).
3. Bloqueo con HTTP 403 al superar el limite de pacientes del plan de la clinica.
4. Aislamiento total: un usuario autenticado en la Clinica 2 no puede listar al Paciente A de la Clinica 1 (listado vacio) ni consultarlo por ID (HTTP 404).
5. Asignacion forzosa del tenant en endpoints POST independientemente de valores suministrados en el payload.
