"""Create the first administrator, or promote an existing account.

Usage (from backend/):
    python -m app.scripts.create_admin

Reads SEED_ADMIN_EMAIL, SEED_ADMIN_NAME and SEED_ADMIN_PASSWORD from the
environment / backend/.env, prompting for any that are missing. The password
is never printed.
"""

import getpass
import os
import sys

from dotenv import dotenv_values
from pydantic import TypeAdapter, ValidationError

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.schemas.auth import RegisterRequest
from app.services import user_service


def _value(name: str, file_values: dict, prompt: str, secret: bool = False) -> str:
    value = os.environ.get(name) or file_values.get(name) or ""
    if value:
        return value
    return getpass.getpass(prompt) if secret else input(prompt)


def main() -> int:
    file_values = dotenv_values(".env")
    email = _value("SEED_ADMIN_EMAIL", file_values, "Admin email: ")
    name = _value("SEED_ADMIN_NAME", file_values, "Admin full name: ")
    password = _value("SEED_ADMIN_PASSWORD", file_values, "Admin password: ", secret=True)

    try:
        data = TypeAdapter(RegisterRequest).validate_python({"full_name": name, "email": email, "password": password})
    except ValidationError as exc:
        print("Invalid admin details:")
        for error in exc.errors():
            print(f"  - {'.'.join(str(p) for p in error['loc'])}: {error['msg']}")
        return 1

    with SessionLocal() as db:
        user, created = user_service.ensure_admin(
            db, email=data.email, full_name=data.full_name, hashed_password=hash_password(data.password)
        )
    print(f"{'Created' if created else 'Promoted existing account to'} administrator: {user.email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
