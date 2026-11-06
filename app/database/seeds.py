"""Semillas de base de datos para planes de suscripcion y clinica demo con identificadores de planes de PayPal."""

from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.clinica import Clinica
from app.models.plan_suscripcion import PlanSuscripcion

PLANES_INICIALES: Sequence[dict] = [
    {
        "nombre": "Básico",
        "precio_mensual": 599.0,
        "precio_anual": 5990.0,
        "limite_personal": 3,
        "limite_pacientes": 100,
        "incluye_calendar": False,
        "incluye_correos": False,
        "limite_ia_mensual": 0,
        "limite_sucursales": 1,
        "incluye_contratos": False,
        "paypal_plan_id": "P-61L31376NX417651DNLWUKSQ",
    },
    {
        "nombre": "Clínica",
        "precio_mensual": 1199.0,
        "precio_anual": 11990.0,
        "limite_personal": 10,
        "limite_pacientes": 500,
        "incluye_calendar": True,
        "incluye_correos": True,
        "limite_ia_mensual": 0,
        "limite_sucursales": 1,
        "incluye_contratos": False,
        "paypal_plan_id": "P-5CC29855SK5899208NLWUMWI",
    },
    {
        "nombre": "Profesional",
        "precio_mensual": 2199.0,
        "precio_anual": 21990.0,
        "limite_personal": 20,
        "limite_pacientes": 1500,
        "incluye_calendar": True,
        "incluye_correos": True,
        "limite_ia_mensual": 100,
        "limite_sucursales": 1,
        "incluye_contratos": False,
        "paypal_plan_id": "P-5J121652NS326140HNLWUNNI",
    },
    {
        "nombre": "Empresarial",
        "precio_mensual": 4499.0,
        "precio_anual": 44990.0,
        "limite_personal": 30,
        "limite_pacientes": 5000,
        "incluye_calendar": True,
        "incluye_correos": True,
        "limite_ia_mensual": 500,
        "limite_sucursales": 1,
        "incluye_contratos": True,
        "paypal_plan_id": "P-64643939B6992035JNLWUOCY",
    },
]


def sembrar_planes_y_clinica_demo(db: Session) -> tuple[list[PlanSuscripcion], Clinica]:
    """Crea o actualiza los planes de suscripcion iniciales vinculando los IDs de PayPal y asegura la clinica demo."""
    planes: list[PlanSuscripcion] = []
    for item in PLANES_INICIALES:
        plan = db.query(PlanSuscripcion).filter(
            PlanSuscripcion.nombre == item["nombre"]
        ).first()
        if not plan:
            plan = PlanSuscripcion(**item)
            db.add(plan)
            db.flush()
        else:
            if item.get("paypal_plan_id") and plan.paypal_plan_id != item["paypal_plan_id"]:
                plan.paypal_plan_id = item["paypal_plan_id"]
                db.flush()
        planes.append(plan)

    plan_empresarial = db.query(PlanSuscripcion).filter(
        PlanSuscripcion.nombre == "Empresarial"
    ).first()

    clinica_demo = db.query(Clinica).filter(
        Clinica.nombre_comercial == "Clínica Demo"
    ).first()
    if not clinica_demo:
        clinica_demo = Clinica(
            nombre_comercial="Clínica Demo",
            plan_id_FK=plan_empresarial.id_PK,
            fecha_registro=datetime.now(),
            activa=True,
            paypal_subscription_id=None,
        )
        db.add(clinica_demo)
        db.flush()

    db.commit()
    db.refresh(clinica_demo)
    for p in planes:
        db.refresh(p)
    return planes, clinica_demo


if __name__ == "__main__":
    from app.database.connection import SessionLocal

    with SessionLocal() as db_session:
        sembrar_planes_y_clinica_demo(db_session)
