# Documentacion Tecnica: Fase 1 - Migracion Multi-Tenant (SaaS) VITALIA

## 1. Resumen de la Implementacion
La Fase 1 establece los cimientos de la arquitectura multi-inquilino (multi-tenant) para el sistema clinico VITALIA mediante el aislamiento logico de datos por identificador de clinica (`clinica_id_FK`) y la creacion del modulo de planes de suscripcion.

## 2. Modelos Creados
### 2.1 PlanSuscripcion (`planes_suscripcion`)
- `id_PK`: Clave primaria autoincremental (Integer).
- `nombre`: Nombre unico del plan (String 100).
- `precio_mensual`: Costo mensual (Float).
- `precio_anual`: Costo anual (Float).
- `limite_personal`: Limite maximo de cuentas de personal/empleados (Integer).
- `limite_pacientes`: Limite maximo de registros de pacientes (Integer).
- `incluye_calendar`: Bandera que habilita integracion de calendario (Boolean).
- `incluye_correos`: Bandera que habilita envio de correos transaccionales (Boolean).
- `limite_ia_mensual`: Cupo mensual de peticiones al asistente clinico IA (Integer).
- `limite_sucursales`: Limite de sucursales operativas (Integer).
- Relacion bidireccional con `Clinica`.

### 2.2 Clinica (`clinicas`)
- `id_PK`: Clave primaria autoincremental (Integer).
- `nombre_comercial`: Razon social o nombre del establecimiento medico (String 200).
- `plan_id_FK`: Clave foranea hacia `planes_suscripcion.id_PK` (Integer, no nulo).
- `plan_id`: Sinonimo ORM para facilitar consultas directas.
- `fecha_registro`: Marca de tiempo de alta de la clinica (DateTime).
- `activa`: Estado operativo del inquilino (Boolean, default True).
- Relaciones con `PlanSuscripcion`, `Usuario`, `Paciente`, `Cita`, `Sala` y `Medicamento`.

## 3. Modelos Existentes Modificados
Se inyecto la clave foranea `clinica_id_FK` (Integer, ForeignKey a `clinicas.id_PK`, nullable=False) y el sinonimo SQLAlchemy `clinica_id` a los modelos clave del sistema:
- `Usuario` (`usuarios`)
- `Paciente` (`pacientes`)
- `Cita` (`citas`)
- `Sala` (`salas`)
- `Medicamento` (`medicamentos`)

Se definio `clinica_id = synonym("clinica_id_FK")` para permitir consultas fluidas mediante `.filter(Modelo.clinica_id == X)` o `.filter(Modelo.clinica_id_FK == X)` sin discrepancias de nomenclatura.

## 4. Semillas y Migracion Alembic
Se creo la migracion `e2b5tenant01_crear_planes_y_clinicas_multitenant.py` vinculada a la revision `d1a4registro04` y el modulo `app.database.seeds`. Se sembraron los siguientes registros:
- Planes:
  - Basico: Mensual 599.0, Anual 5990.0, Personal 3, Pacientes 100, Calendar False, Correos False, IA 0.
  - Clinica: Mensual 1199.0, Anual 11990.0, Personal 10, Pacientes 500, Calendar True, Correos True, IA 0.
  - Profesional: Mensual 2199.0, Anual 21990.0, Personal 20, Pacientes 1500, Calendar True, Correos True, IA 100.
  - Empresarial: Mensual 4499.0, Anual 44990.0, Personal 30, Pacientes 5000, Calendar True, Correos True, IA 500.
- Clinica por defecto:
  - "Clinica Demo" vinculada al plan Empresarial, activa y con fecha de registro automatica.

## 5. Pruebas Unitarias (Pytest)
El archivo `tests/test_fase1_multitenant.py` verifica:
1. `test_creacion_planes_suscripcion`: Integridad y correspondencia exacta de los 4 planes y la clinica demo por defecto.
2. `test_restriccion_integridad_referencial_clinica_usuario`: Comprobacion estricta de claves foraneas activadas via PRAGMA en SQLite impidiendo altas con inquilinos inexistentes o valores nulos.
3. `test_aislamiento_multitenant_consultas`: Simulacion de dos clinicas independientes comprobando aislamiento logico en consultas filtradas por `.filter(Modelo.clinica_id == X)`.
