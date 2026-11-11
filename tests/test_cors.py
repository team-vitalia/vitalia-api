from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_cors_preflight_landing_produccion():
    headers = {
        "Origin": "https://landing-ten-sigma-42.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/api/suscripciones/pre-registro", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://landing-ten-sigma-42.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_app_produccion():
    headers = {
        "Origin": "https://vitalia-app-fowe.vercel.app",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    response = client.options("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://vitalia-app-fowe.vercel.app"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_vercel_preview_regex():
    headers = {
        "Origin": "https://landing-preview-git-feature.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/api/suscripciones/pre-registro", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://landing-preview-git-feature.vercel.app"


def test_cors_preflight_admin_vitalia():
    headers = {
        "Origin": "https://admin.vitalia.software",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/api/auth/login", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://admin.vitalia.software"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_vitalia_subdomain_regex():
    headers = {
        "Origin": "https://app.vitalia.software",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    response = client.options("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://app.vitalia.software"
    assert response.headers.get("access-control-allow-credentials") == "true"
