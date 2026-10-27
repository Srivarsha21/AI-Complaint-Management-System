"""Validate and upsert verified office records from the JSON seed file.

Every record must carry `source_url` and `verified_on`; the whole file is
rejected if any record is invalid, so a partially verified dataset is never
loaded. Upserts are keyed by (name, organisation), so re-running is safe.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.office import Office
from app.repositories import office_repository
from app.schemas.office import OfficeRecord

DEFAULT_DATA_FILE = Path(__file__).resolve().parent / "data" / "hyderabad_offices.json"


class OfficeDataError(Exception):
    """The seed data is invalid; `problems` lists every issue found."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class LoadResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    unknown_slugs: set[str] = field(default_factory=set)


def read_file(path: Path = DEFAULT_DATA_FILE) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise OfficeDataError(["the file must contain a list of records (or an object with a 'records' list)"])
    return records


def validate_records(raw_records: list[dict[str, Any]]) -> list[OfficeRecord]:
    problems: list[str] = []
    records: list[OfficeRecord] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_records, start=1):
        label = f"record {index} ({raw.get('name', '?') if isinstance(raw, dict) else '?'})"
        try:
            record = OfficeRecord.model_validate(raw)
        except ValidationError as exc:
            for error in exc.errors():
                location = ".".join(str(p) for p in error["loc"]) or "record"
                problems.append(f"{label}: {location}: {error['msg']}")
            continue
        key = (record.name, record.organisation)
        if key in seen:
            problems.append(f"{label}: duplicate name + organisation")
        seen.add(key)
        records.append(record)
    if problems:
        raise OfficeDataError(problems)
    return records


def _values(record: OfficeRecord) -> dict[str, Any]:
    values = record.model_dump()
    values["website"] = str(record.website) if record.website else None
    values["source_url"] = str(record.source_url)
    return values


def load_records(db: Session, records: list[OfficeRecord], *, deactivate_missing: bool = False) -> LoadResult:
    """Upsert `records` by (name, organisation) and commit."""
    result = LoadResult()
    known_slugs = set(office_repository.active_category_slugs(db))
    keys: set[tuple[str, str]] = set()

    for record in records:
        keys.add((record.name, record.organisation))
        result.unknown_slugs.update(s for s in record.category_slugs if s != "*" and s not in known_slugs)
        values = _values(record)
        office = office_repository.get_by_identity(db, record.name, record.organisation)
        if office is None:
            office_repository.add(db, Office(**values))
            result.created += 1
            continue
        changed = False
        for key, value in values.items():
            if getattr(office, key) != value:
                setattr(office, key, value)
                changed = True
        if changed:
            result.updated += 1
        else:
            result.unchanged += 1

    if deactivate_missing:
        for office in office_repository.list_active(db):
            if (office.name, office.organisation) not in keys:
                office.is_active = False
                result.deactivated += 1

    db.commit()
    return result


def load_file(db: Session, path: Path = DEFAULT_DATA_FILE, *, deactivate_missing: bool = False) -> LoadResult:
    return load_records(db, validate_records(read_file(path)), deactivate_missing=deactivate_missing)
