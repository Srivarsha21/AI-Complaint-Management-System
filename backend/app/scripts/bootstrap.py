"""Prepare the database when a hosted server starts (safe to run on every start).

    python -m app.scripts.bootstrap

1. Apply Alembic migrations (creates tables, seeds categories/departments).
2. Load the verified Hyderabad office records (idempotent upsert).
3. Create the first administrator when SEED_ADMIN_EMAIL/NAME/PASSWORD are set
   (an existing account with that email is promoted, its password is not changed).
4. Load the FICTIONAL demo data only when SEED_DEMO_DATA=true and the database
   has no complaints yet (never overwrites real complaints).

Steps 2-4 log and continue on failure so a hosting restart never loops on them.
"""

import logging
import os
import subprocess
import sys

from sqlalchemy import select

from app.core.config import BACKEND_DIR
from app.core.logging import configure_logging

logger = logging.getLogger("bootstrap")


def _run(module: str, *args: str) -> int:
    logger.info("running %s %s", module, " ".join(args))
    return subprocess.call([sys.executable, "-m", module, *args], cwd=BACKEND_DIR)


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))

    if _run("alembic", "upgrade", "head") != 0:
        logger.error("migrations failed; not starting")
        return 1

    if _run("app.scripts.load_offices") != 0:
        logger.warning("office data could not be loaded; the assistant will fall back to generic guidance")

    if all(os.environ.get(name) for name in ("SEED_ADMIN_EMAIL", "SEED_ADMIN_NAME", "SEED_ADMIN_PASSWORD")):
        if _run("app.scripts.create_admin") != 0:
            logger.warning("administrator could not be created")

    if os.environ.get("SEED_DEMO_DATA", "").lower() == "true":
        from app.db.session import SessionLocal
        from app.models import Complaint

        with SessionLocal() as db:
            empty = db.scalar(select(Complaint.id).limit(1)) is None
        if empty:
            _run("app.scripts.seed_demo")
        else:
            logger.info("complaints already exist; demo data not loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
