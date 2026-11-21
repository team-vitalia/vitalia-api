
from getpass import getpass

from app.database.connection import SessionLocal
from app.models.usuario import Usuario
from app.core.security import generar_hash_password


def crear_admin():
    db = SessionLocal()

    try:
        # Solicitar datos
        nombre = input("Nombre del administrador: ").strip()
        correo = input("Correo electrónico: ").strip()

        password = getpass("Contraseña: ")
        confirmar = getpass("Confirmar contraseña: ")

        if not nombre or not correo or not password:
            print("Todos los campos son obligatorios.")
            return

        if password != confirmar:
            print("Las contraseñas no coinciden.")
            return

        # Verificar que exista la clínica
        clinica = db.query(Usuario).filter(
            Usuario.clinica_id_FK == 1
        ).first()

        if not clinica:
            print("No se encontró ningún usuario asociado a la clínica ID 1.")
            print("Verifica que la clínica exista antes de crear el administrador.")
            return

        # Verificar correo existente
        usuario_existente = (
            db.query(Usuario)
            .filter(
                Usuario.correo_electronico == correo
            )
            .first()
        )

        if usuario_existente:
            print("Ya existe un usuario con ese correo.")
            return

        # Crear administrador
        nuevo_usuario = Usuario(
            clinica_id_FK=1,
            nombre=nombre,
            correo_electronico=correo,
            hash_contrasena=generar_hash_password(password),
            rol_id_FK=1,
            estado="activo",
            intentos_fallidos=0
        )

        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)

        print("\nUsuario administrador creado correctamente.")
        print(f"ID: {nuevo_usuario.id_PK}")
        print(f"Nombre: {nuevo_usuario.nombre}")
        print(f"Correo: {nuevo_usuario.correo_electronico}")
        print(f"Rol ID: {nuevo_usuario.rol_id_FK}")
        print(f"Clínica ID: {nuevo_usuario.clinica_id_FK}")

    except Exception as error:
        db.rollback()
        print("\nError al crear el usuario:")
        print(error)

    finally:
        db.close()


if __name__ == "__main__":
    crear_admin()
