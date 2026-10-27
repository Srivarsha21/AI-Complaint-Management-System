"""Test configuration.

Tests run against a separate PostgreSQL database (`<dbname>_test`, e.g.
complaints_test) so development data is never touched. Tables are created
fresh for the session and emptied after every test.
"""

import os
import re

from sqlalchemy.engine import make_url

# Must happen before the app (and its engine) is imported.
from app.core.config import get_settings

_dev_url = make_url(get_settings().database_url)
os.environ["DATABASE_URL"] = (
    os.environ.get("TEST_DATABASE_URL")
    or _dev_url.set(database=f"{_dev_url.database}_test").render_as_string(hide_password=False)
)
os.environ["ENVIRONMENT"] = "test"
get_settings.cache_clear()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings as _get_settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Category, Department, User, UserRole  # noqa: E402

TEST_PASSWORD = "Passw0rd!test"


@pytest.fixture(autouse=True)
def _isolated_uploads(tmp_path, monkeypatch):
    """Every test writes uploads to its own temporary folder."""
    monkeypatch.setattr(_get_settings(), "upload_dir", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    # Accepts "<name>_test" and suffixed variants such as "<name>_test_e" (parallel worktrees).
    assert re.search(r"_test(_[a-z0-9]+)?$", engine.url.database or ""), "refusing to run tests against a non-test database"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_state():
    yield
    limiter.reset()
    table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def make_user(
    db, *, email: str = "user@example.com", full_name: str = "Test User",
    role: UserRole = UserRole.USER, password: str = TEST_PASSWORD, is_active: bool = True,
) -> User:
    user = User(
        email=email, full_name=full_name, role=role, hashed_password=hash_password(password), is_active=is_active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_category(db, *, name: str = "Drainage & Sewerage", slug: str = "drainage", department: str = "Sewerage Dept",
                  is_active: bool = True) -> Category:
    dept = db.query(Department).filter_by(name=department).one_or_none() or Department(name=department)
    category = Category(name=name, slug=slug, department=dept, is_active=is_active)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
