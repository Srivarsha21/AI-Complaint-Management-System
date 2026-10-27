"""Load verified Hyderabad offices / complaint channels into the database.

Usage (from backend/):
    python -m app.scripts.load_offices                 # default data file
    python -m app.scripts.load_offices --file other.json --dry-run
    python -m app.scripts.load_offices --deactivate-missing

Idempotent: records are upserted by (name, organisation). The whole file is
rejected if any record lacks `source_url` / `verified_on` or is otherwise invalid.
"""

import argparse
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.location.office_loader import DEFAULT_DATA_FILE, OfficeDataError, load_records, read_file, validate_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=DEFAULT_DATA_FILE, help="JSON data file")
    parser.add_argument("--dry-run", action="store_true", help="validate only; do not touch the database")
    parser.add_argument("--deactivate-missing", action="store_true",
                        help="mark active records that are not in the file as inactive")
    args = parser.parse_args(argv)

    try:
        records = validate_records(read_file(args.file))
    except (OSError, ValueError) as exc:
        print(f"Could not read {args.file}: {exc}")
        return 1
    except OfficeDataError as exc:
        print(f"Rejected {args.file}: {len(exc.problems)} problem(s)")
        for problem in exc.problems:
            print(f"  - {problem}")
        return 1

    if args.dry_run:
        print(f"OK: {len(records)} valid record(s) in {args.file} (dry run, nothing written)")
        return 0

    with SessionLocal() as db:
        result = load_records(db, records, deactivate_missing=args.deactivate_missing)
    print(
        f"Loaded {len(records)} record(s): {result.created} created, {result.updated} updated, "
        f"{result.unchanged} unchanged, {result.deactivated} deactivated."
    )
    if result.unknown_slugs:
        print(f"Warning: no active category with slug(s): {', '.join(sorted(result.unknown_slugs))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
