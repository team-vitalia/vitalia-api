-- ============================================================================
-- VITALIA - DATOS DE PRUEBA PARA VALIDACIÓN DEL ASISTENTE CLÍNICO IA (GROQ)
-- ============================================================================
-- Este script inserta:
-- 1. Un Doctor de prueba (correo: doctor.prueba@vitalia.com / pass: Password123!)
-- 2. Alergias comunes en catálogo (Penicilina, AINEs, Sulfas)
-- 3. Un Paciente alérgico a la Penicilina (Juan Pérez)
-- 4. Una Cita activa asignada al Doctor para probar la alerta de alergia
-- 5. Medicamentos comunes en inventario para probar la generación de recetas
-- ============================================================================

USE vitalia;

-- 1. ASEGURAR ROLES BÁSICOS
INSERT IGNORE INTO roles (id_PK, nombre, descripcion, esta_activo) VALUES
(1, 'Administrador', 'Administración general del sistema', 1),
(2, 'Doctor', 'Consultas, expedientes y recetas', 1),
(3, 'Paciente', 'Consulta de sus citas e información', 1),
(4, 'Recepción', 'Gestión de citas y pacientes', 1);

-- 2. ASEGURAR ESPECIALIDAD MÉDICA
INSERT IGNORE INTO especialidades (id_PK, nombre, descripcion, codigo, esta_activo) VALUES
(1, 'Medicina General', 'Atención médica integral de primer contacto', 'MG-01', 1);

-- 3. CREAR USUARIO DOCTOR DE PRUEBA (password: Password123!)
-- Hash bcrypt generado para 'Password123!'
INSERT INTO usuarios (id_PK, nombre, apellido_paterno, apellido_materno, correo_electronico, hash_contrasena, rol_id_FK, estado)
VALUES (101, 'Dr. Roberto', 'Hernández', 'Sánchez', 'doctor.prueba@vitalia.com', '$2b$12$XTTP.4N5EAFdqIs0PmkIVOFq05VMw1astj1wNNmZvU6r1IXFuANfS', 2, 'activo')
ON DUPLICATE KEY UPDATE 
    nombre = 'Dr. Roberto',
    hash_contrasena = '$2b$12$XTTP.4N5EAFdqIs0PmkIVOFq05VMw1astj1wNNmZvU6r1IXFuANfS',
    rol_id_FK = 2,
    estado = 'activo';

-- 4. VINCULAR EN TABLA DOCTORES
INSERT INTO doctores (id_PK, usuario_id_FK, especialidad_id_FK, numero_licencia, rfc, estado, costo_consulta)
VALUES (101, 101, 1, 'MED-778899-DF', 'HESR850101XYZ', 'activo', 600.00)
ON DUPLICATE KEY UPDATE
    usuario_id_FK = 101,
    especialidad_id_FK = 1,
    estado = 'activo';

-- 5. CREAR CATÁLOGO DE ALERGIAS
INSERT INTO alergias (id_PK, nombre, descripcion, severidad, tipo_alergia) VALUES
(1, 'Penicilina', 'Hipersensibilidad y riesgo de anafilaxia con betalactámicos', 'grave', 'medicamentosa'),
(2, 'Ácido Acetilsalicílico (Aspirina / AINEs)', 'Broncoespasmo o urticaria inducida por AINEs', 'moderada', 'medicamentosa'),
(3, 'Sulfamidas (Sulfas)', 'Erupción cutánea y reacción inmunitaria', 'grave', 'medicamentosa')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

-- 6. CREAR PACIENTE DE PRUEBA (Juan Carlos Pérez, 34 años)
INSERT INTO pacientes (id_PK, nombre, apellido, apellido_paterno, apellido_materno, curp, fecha_nacimiento, genero, telefono, correo_electronico, estado)
VALUES (201, 'Juan Carlos', 'Pérez López', 'Pérez', 'López', 'PELJ900315HDFR01', '1990-03-15', 'Masculino', '5512345678', 'juan.perez@correo.com', 'activo')
ON DUPLICATE KEY UPDATE
    nombre = 'Juan Carlos',
    apellido = 'Pérez López',
    fecha_nacimiento = '1990-03-15',
    genero = 'Masculino';

-- 7. ASIGNAR ALERGIA GRAVE A PENICILINA AL PACIENTE (Para disparar la alerta de la IA)
DELETE FROM alergias_paciente WHERE paciente_id_FK = 201 AND alergia_id_FK = 1;
INSERT INTO alergias_paciente (paciente_id_FK, alergia_id_FK, severidad, fecha_diagnostico, notas)
VALUES (201, 1, 'grave', '2021-05-10', 'Reacción anafiláctica severa previa con amoxicilina y penicilina G benzatínica.');

-- 8. CREAR CITA ACTIVA PARA CONSULTA (CITA #301)
INSERT INTO citas (id_PK, paciente_id_FK, doctor_id_FK, fecha, hora_inicio, hora_fin, estado, motivo, notas, creado_por)
VALUES (
    301, 
    201, 
    101, 
    CURDATE(), 
    '10:00:00', 
    '10:45:00', 
    'programada', 
    'Fiebre alta de 39°C, odinofagia intensa con placas exudativas blanquecinas en amígdalas y cefalea de 48 horas de evolución.', 
    'Paciente refiere que el dolor de garganta comenzó hace 2 días. Sin tos ni rinorrea evidente.',
    101
)
ON DUPLICATE KEY UPDATE
    paciente_id_FK = 201,
    doctor_id_FK = 101,
    fecha = CURDATE(),
    estado = 'programada',
    motivo = 'Fiebre alta de 39°C, odinofagia intensa con placas exudativas blanquecinas en amígdalas y cefalea de 48 horas de evolución.';

-- 9. INSERTAR MEDICAMENTOS COMUNES EN EL CATÁLOGO PARA RECETAS
INSERT INTO medicamentos (id_PK, nombre, principio_activo, presentacion, requiere_receta, descripcion, categoria) VALUES
(1, 'Amoxicilina 500mg', 'Amoxicilina', 'Caja con 12 cápsulas 500mg', 1, 'Antibiótico betalactámico', 'Antibiótico'),
(2, 'Claritromicina 500mg', 'Claritromicina', 'Caja con 10 tabletas 500mg', 1, 'Macrólido alternativo para alérgicos a penicilina', 'Antibiótico'),
(3, 'Paracetamol 500mg', 'Paracetamol', 'Caja con 20 tabletas 500mg', 0, 'Analgésico y antipirético', 'Analgésico'),
(4, 'Ibuprofeno 400mg', 'Ibuprofeno', 'Caja con 10 tabletas 400mg', 0, 'Antiinflamatorio no esteroideo (AINE)', 'Antiinflamatorio'),
(5, 'Azitromicina 500mg', 'Azitromicina', 'Caja con 3 tabletas 500mg', 1, 'Macrólido de amplio espectro', 'Antibiótico')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
