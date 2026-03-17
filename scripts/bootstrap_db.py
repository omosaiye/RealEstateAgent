"""Create the SQLite database used for persisted listing state."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from src.services.state_service import DEFAULT_DB_PATH, StateError, bootstrap_database


def main(argv: Sequence[str] | None = None) -> int:
    """Create the listing state database and table."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite database file to create.",
    )
    args = parser.parse_args(argv)

    try:
        db_path = bootstrap_database(Path(args.db_path))
    except StateError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"SQLite listing state database is ready at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
