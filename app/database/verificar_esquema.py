import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from app.database.seeds import sembrar_planes_y_clinica_demo

logger = logging.getLogger("vitalia.database")


def asegurar_esquema_y_seeds(engine: Engine, session_factory) -> None:
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            tablas = insp.get_table_names()

            if "planes_suscripcion" in tablas:
                cols_planes = [c["name"] for c in insp.get_columns("planes_suscripcion")]
                if "limite_pacientes_mes" not in cols_planes:
                    conn.execute(text("ALTER TABLE planes_suscripcion ADD COLUMN limite_pacientes_mes INT NULL DEFAULT NULL"))
                if "incluye_salas" not in cols_planes:
                    conn.execute(text("ALTER TABLE planes_suscripcion ADD COLUMN incluye_salas TINYINT(1) NOT NULL DEFAULT 1"))
                if "incluye_almacen" not in cols_planes:
                    conn.execute(text("ALTER TABLE planes_suscripcion ADD COLUMN incluye_almacen TINYINT(1) NOT NULL DEFAULT 1"))
                if "incluye_reportes" not in cols_planes:
                    conn.execute(text("ALTER TABLE planes_suscripcion ADD COLUMN incluye_reportes TINYINT(1) NOT NULL DEFAULT 1"))
                if "incluye_auditoria" not in cols_planes:
                    conn.execute(text("ALTER TABLE planes_suscripcion ADD COLUMN incluye_auditoria TINYINT(1) NOT NULL DEFAULT 1"))
                if "incluye_roles" not in cols_planes:
                    conn.execute(text("ALTER TABLE planes_suscripcion ADD COLUMN incluye_roles TINYINT(1) NOT NULL DEFAULT 1"))
                conn.commit()

            if "clinicas" in tablas:
                cols_clinicas = [c["name"] for c in insp.get_columns("clinicas")]
                if "fecha_inicio_suscripcion" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN fecha_inicio_suscripcion DATETIME NULL DEFAULT NULL"))
                if "ultimo_pago_capture_id" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN ultimo_pago_capture_id VARCHAR(100) NULL DEFAULT NULL"))
                if "limite_pacientes_extra" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN limite_pacientes_extra INT NOT NULL DEFAULT 0"))
                if "limite_personal_extra" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN limite_personal_extra INT NOT NULL DEFAULT 0"))
                if "dias_gracia" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN dias_gracia INT NOT NULL DEFAULT 0"))
                if "fecha_fin_gracia" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN fecha_fin_gracia DATETIME NULL DEFAULT NULL"))
                if "motivo_excepcion" not in cols_clinicas:
                    conn.execute(text("ALTER TABLE clinicas ADD COLUMN motivo_excepcion VARCHAR(255) NULL DEFAULT NULL"))
                conn.commit()

            if "pacientes" in tablas:
                cols_pacientes = [c["name"] for c in insp.get_columns("pacientes")]
                if "creado_en" not in cols_pacientes:
                    conn.execute(text("ALTER TABLE pacientes ADD COLUMN creado_en DATETIME NULL DEFAULT CURRENT_TIMESTAMP"))
                    conn.execute(text("UPDATE pacientes SET creado_en = NOW() WHERE creado_en IS NULL"))
                    conn.commit()

            if "avisos_superadmin" not in tablas and "clinicas" in tablas:
                conn.execute(text(
                    "CREATE TABLE avisos_superadmin ("
                    "id_PK INT AUTO_INCREMENT PRIMARY KEY, "
                    "clinica_id_FK INT NULL, "
                    "titulo VARCHAR(150) NOT NULL, "
                    "mensaje TEXT NOT NULL, "
                    "tipo VARCHAR(30) NOT NULL DEFAULT 'informativo', "
                    "activo TINYINT(1) NOT NULL DEFAULT 1, "
                    "fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "fecha_expiracion DATETIME NULL DEFAULT NULL, "
                    "creado_por_usuario_id_FK INT NULL, "
                    "CONSTRAINT fk_aviso_clinica FOREIGN KEY (clinica_id_FK) REFERENCES clinicas(id_PK) ON DELETE CASCADE, "
                    "CONSTRAINT fk_aviso_usuario FOREIGN KEY (creado_por_usuario_id_FK) REFERENCES usuarios(id_PK) ON DELETE SET NULL"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                conn.commit()

            if "cancelaciones_suscripcion" not in tablas and "clinicas" in tablas and "planes_suscripcion" in tablas:
                conn.execute(text(
                    "CREATE TABLE cancelaciones_suscripcion ("
                    "id_PK INT AUTO_INCREMENT PRIMARY KEY, "
                    "clinica_id_FK INT NOT NULL, "
                    "plan_anterior_id_FK INT NOT NULL, "
                    "fecha_cancelacion DATETIME NOT NULL, "
                    "motivo_categoria VARCHAR(50) NOT NULL, "
                    "comentarios_adicionales TEXT NULL, "
                    "aplica_reembolso TINYINT(1) NOT NULL DEFAULT 0, "
                    "estado_reembolso VARCHAR(30) NOT NULL DEFAULT 'NO_APLICA', "
                    "paypal_refund_id VARCHAR(100) NULL, "
                    "CONSTRAINT fk_cancelacion_clinica FOREIGN KEY (clinica_id_FK) REFERENCES clinicas(id_PK) ON DELETE CASCADE, "
                    "CONSTRAINT fk_cancelacion_plan FOREIGN KEY (plan_anterior_id_FK) REFERENCES planes_suscripcion(id_PK)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                ))
                conn.commit()

        db: Session = session_factory()
        try:
            sembrar_planes_y_clinica_demo(db)
            db.commit()
        except Exception as seed_err:
            db.rollback()
            logger.warning(f"Advertencia sembrando datos: {seed_err}")
        finally:
            db.close()
    except Exception as err:
        logger.warning(f"Advertencia en sincronizacion de esquema: {err}")
