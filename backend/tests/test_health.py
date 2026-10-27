from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_db_reports_reachable_database():
    # Uses the real DATABASE_URL from backend/.env (PostgreSQL must be running).
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_health_db_reports_503_when_database_down():
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise ConnectionError("db down")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        response = client.get("/api/v1/health/db")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"


def test_cors_allows_configured_frontend_origin():
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers
