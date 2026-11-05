"""
Script de sembrado de datos de prueba para el Asistente Clínico IA (Groq).
Crea un Doctor, un Paciente con alergia a la Penicilina, una Cita activa y Medicamentos.
"""
import sys
import os
from datetime import date, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database.connection import SessionLocal, engine
from app.core.security import generar_hash_password

def sembrar_datos():
    print("[VITALIA] Iniciando siembra de datos de prueba para Asistente IA...")
    
    try:
        with engine.connect() as conn:
            print("[VITALIA] Conexión a la base de datos MySQL exitosa.")
    except Exception as e:
        print("[VITALIA] Error: No se pudo conectar a MySQL. Asegúrate de tener XAMPP / MySQL encendido.")
        print(f"Detalle del error: {e}")
        return False

    db = SessionLocal()
    try:
        # 1. Asegurar Roles
        db.execute(text("""
            INSERT IGNORE INTO roles (id_PK, nombre, descripcion, esta_activo) VALUES
            (1, 'Administrador', 'Administración general del sistema', 1),
            (2, 'Doctor', 'Consultas, expedientes y recetas', 1),
            (3, 'Paciente', 'Consulta de sus citas e información', 1),
            (4, 'Recepción', 'Gestión de citas y pacientes', 1);
        """))

        # 2. Asegurar Especialidad
        db.execute(text("""
            INSERT IGNORE INTO especialidades (id_PK, nombre, descripcion, codigo, esta_activo) VALUES
            (1, 'Medicina General', 'Atención médica integral', 'MG-01', 1);
        """))

        # 3. Usuario Doctor de Prueba
        hash_pass = generar_hash_password("Password123!")
        db.execute(text("""
            INSERT INTO usuarios (id_PK, nombre, apellido_paterno, apellido_materno, correo_electronico, hash_contrasena, rol_id_FK, estado)
            VALUES (101, 'Dr. Roberto', 'Hernández', 'Sánchez', 'doctor.prueba@vitalia.com', :hash_pass, 2, 'activo')
            ON DUPLICATE KEY UPDATE 
                nombre = 'Dr. Roberto',
                hash_contrasena = :hash_pass,
                rol_id_FK = 2,
                estado = 'activo';
        """), {"hash_pass": hash_pass})

        # 4. Doctor perfil
        db.execute(text("""
            INSERT INTO doctores (id_PK, usuario_id_FK, especialidad_id_FK, numero_licencia, rfc, estado, costo_consulta)
            VALUES (101, 101, 1, 'MED-778899-DF', 'HESR850101XYZ', 'activo', 600.00)
            ON DUPLICATE KEY UPDATE
                usuario_id_FK = 101,
                especialidad_id_FK = 1,
                estado = 'activo';
        """))

        # 5. Catálogo de Alergias
        db.execute(text("""
            INSERT INTO alergias (id_PK, nombre, descripcion, severidad, tipo_alergia) VALUES
            (1, 'Penicilina', 'Hipersensibilidad y riesgo de anafilaxia con betalactámicos', 'grave', 'medicamentosa'),
            (2, 'Ácido Acetilsalicílico (Aspirina / AINEs)', 'Broncoespasmo o urticaria inducida por AINEs', 'moderada', 'medicamentosa')
            ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
        """))

        # 6. Paciente de Prueba (alérgico a Penicilina)
        db.execute(text("""
            INSERT INTO pacientes (id_PK, nombre, apellido, apellido_paterno, apellido_materno, curp, fecha_nacimiento, genero, telefono, correo_electronico, estado)
            VALUES (201, 'Juan Carlos', 'Pérez López', 'Pérez', 'López', 'PELJ900315HDFR01', '1990-03-15', 'Masculino', '5512345678', 'juan.perez@correo.com', 'activo')
            ON DUPLICATE KEY UPDATE
                nombre = 'Juan Carlos',
                apellido = 'Pérez López',
                fecha_nacimiento = '1990-03-15',
                genero = 'Masculino';
        """))

        # 7. Asignar Alergia al Paciente
        db.execute(text("DELETE FROM alergias_paciente WHERE paciente_id_FK = 201 AND alergia_id_FK = 1;"))
        db.execute(text("""
            INSERT INTO alergias_paciente (paciente_id_FK, alergia_id_FK, severidad, fecha_diagnostico, notas)
            VALUES (201, 1, 'grave', '2021-05-10', 'Reacción anafiláctica severa previa con amoxicilina y penicilinas.');
        """))

        # 8. Cita Médica Activa
        hoy = date.today().isoformat()
        db.execute(text("""
            INSERT INTO citas (id_PK, paciente_id_FK, doctor_id_FK, fecha, hora_inicio, hora_fin, estado, motivo, notas, creado_por)
            VALUES (
                301, 
                201, 
                101, 
                :hoy, 
                '10:00:00', 
                '10:45:00', 
                'programada', 
                'Fiebre de 39°C, odinofagia intensa con placas exudativas purulentas en amígdalas y malestar general.', 
                'Paciente acude por dolor severo de garganta de 48 horas de evolución. Dificultad para deglutir alimentos.',
                101
            )
            ON DUPLICATE KEY UPDATE
                paciente_id_FK = 201,
                doctor_id_FK = 101,
                fecha = :hoy,
                estado = 'programada',
                motivo = 'Fiebre de 39°C, odinofagia intensa con placas exudativas purulentas en amígdalas y malestar general.';
        """), {"hoy": hoy})

        # 9. Medicamentos en catálogo
        db.execute(text("""
            INSERT INTO medicamentos (id_PK, nombre, principio_activo, presentacion, requiere_receta, descripcion, categoria) VALUES
            (1, 'Amoxicilina 500mg', 'Amoxicilina', 'Caja con 12 cápsulas 500mg', 1, 'Antibiótico betalactámico', 'Antibiótico'),
            (2, 'Claritromicina 500mg', 'Claritromicina', 'Caja con 10 tabletas 500mg', 1, 'Macrólido alternativo para alérgicos a penicilina', 'Antibiótico'),
            (3, 'Paracetamol 500mg', 'Paracetamol', 'Caja con 20 tabletas 500mg', 0, 'Analgésico y antipirético', 'Analgésico'),
            (4, 'Ibuprofeno 400mg', 'Ibuprofeno', 'Caja con 10 tabletas 400mg', 0, 'Antiinflamatorio no esteroideo (AINE)', 'Antiinflamatorio')
            ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
        """))

        db.commit()
        print("==================================================================")
        print("[OK] DATOS DE PRUEBA SEMBRADOS CON EXITO")
        print("==================================================================")
        print("Credenciales de Acceso Médico:")
        print("  - Correo: doctor.prueba@vitalia.com")
        print("  - Contraseña: Password123!")
        print("  - Rol: Doctor (ID: 2)")
        print("Cita de Prueba creada:")
        print("  - Cita ID: 301")
        print("  - Paciente: Juan Carlos Pérez López (34 años)")
        print("  - Alergia crítica: PENICILINA (severidad grave)")
        print("  - Síntomas: Fiebre de 39°C, odinofagia con placas en amígdalas")
        print("==================================================================")
        return True
    except Exception as e:
        db.rollback()
        print(f"[VITALIA] Error sembrando datos: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    sembrar_datos()
