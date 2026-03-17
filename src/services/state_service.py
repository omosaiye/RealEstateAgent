"""SQLite-backed state storage for listing deduplication."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path("listing_state.db")
LISTING_STATE_TABLE = "listing_state"
_UNSET = object()


class StateError(RuntimeError):
    """Raised when reading or writing listing state fails."""


@dataclass(slots=True, frozen=True)
class ListingState:
    """Persisted state for a listing within a single search."""

    listing_id: str
    search_name: str
    last_seen_price: int | None
    last_seen_status: str | None
    last_sent_at: str | None
    first_seen_at: str
    updated_at: str


class SQLiteStateService:
    """Small SQLite service for listing state reads and writes."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)

    @property
    def db_path(self) -> Path:
        """Return the configured SQLite database path."""

        return self._db_path

    def bootstrap(self) -> None:
        """Ensure the SQLite database and listing state table exist."""

        bootstrap_database(self._db_path)

    def get_listing_state(
        self,
        *,
        listing_id: str,
        search_name: str,
    ) -> ListingState | None:
        """Fetch persisted state for one listing within one search."""

        with _open_connection(self._db_path) as connection:
            _ensure_listing_state_table(connection, self._db_path)
            return _fetch_listing_state(
                connection,
                listing_id=listing_id,
                search_name=search_name,
            )

    def upsert_listing_state(
        self,
        *,
        listing_id: str,
        search_name: str,
        last_seen_price: int | None,
        last_seen_status: str | None,
        last_sent_at: object = _UNSET,
        first_seen_at: str | None = None,
        updated_at: str | None = None,
    ) -> ListingState:
        """Insert or update persisted state for a listing."""

        with _open_connection(self._db_path) as connection:
            _ensure_listing_state_table(connection, self._db_path)
            existing_state = _fetch_listing_state(
                connection,
                listing_id=listing_id,
                search_name=search_name,
            )
            resolved_updated_at = updated_at or _current_timestamp()
            resolved_first_seen_at = (
                existing_state.first_seen_at
                if existing_state is not None
                else first_seen_at or resolved_updated_at
            )
            resolved_last_sent_at = _resolve_last_sent_at(existing_state, last_sent_at)

            try:
                connection.execute(
                    f"""
                    INSERT INTO {LISTING_STATE_TABLE} (
                        listing_id,
                        search_name,
                        last_seen_price,
                        last_seen_status,
                        last_sent_at,
                        first_seen_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(listing_id, search_name) DO UPDATE SET
                        last_seen_price = excluded.last_seen_price,
                        last_seen_status = excluded.last_seen_status,
                        last_sent_at = excluded.last_sent_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        listing_id,
                        search_name,
                        last_seen_price,
                        last_seen_status,
                        resolved_last_sent_at,
                        resolved_first_seen_at,
                        resolved_updated_at,
                    ),
                )
                connection.commit()
            except sqlite3.Error as exc:
                raise StateError(
                    "Unable to upsert listing state for "
                    f"listing '{listing_id}' in search '{search_name}' "
                    f"at database '{self._db_path}'."
                ) from exc

            return ListingState(
                listing_id=listing_id,
                search_name=search_name,
                last_seen_price=last_seen_price,
                last_seen_status=last_seen_status,
                last_sent_at=resolved_last_sent_at,
                first_seen_at=resolved_first_seen_at,
                updated_at=resolved_updated_at,
            )


def bootstrap_database(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Create the SQLite database and listing state table if needed."""

    resolved_db_path = Path(db_path)

    with _open_connection(resolved_db_path) as connection:
        _ensure_listing_state_table(connection, resolved_db_path)

    return resolved_db_path


def _resolve_last_sent_at(
    existing_state: ListingState | None,
    last_sent_at: object,
) -> str | None:
    if last_sent_at is _UNSET:
        return existing_state.last_sent_at if existing_state is not None else None

    if last_sent_at is not None and not isinstance(last_sent_at, str):
        raise StateError("Listing state field 'last_sent_at' must be a string or None.")

    return last_sent_at


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_parent_directory(db_path: Path) -> None:
    parent_directory = db_path.parent
    if parent_directory == Path("."):
        return

    try:
        parent_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StateError(
            f"Unable to create database directory for '{db_path}'."
        ) from exc


@contextmanager
def _open_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    _ensure_parent_directory(db_path)

    try:
        connection = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        raise StateError(f"Unable to connect to SQLite database '{db_path}'.") from exc

    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _ensure_listing_state_table(
    connection: sqlite3.Connection,
    db_path: Path,
) -> None:
    try:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {LISTING_STATE_TABLE} (
                listing_id TEXT NOT NULL,
                search_name TEXT NOT NULL,
                last_seen_price INTEGER,
                last_seen_status TEXT,
                last_sent_at TEXT,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (listing_id, search_name)
            )
            """
        )
        connection.commit()
    except sqlite3.Error as exc:
        raise StateError(
            f"Unable to create listing state table in database '{db_path}'."
        ) from exc


def _fetch_listing_state(
    connection: sqlite3.Connection,
    *,
    listing_id: str,
    search_name: str,
) -> ListingState | None:
    try:
        row = connection.execute(
            f"""
            SELECT
                listing_id,
                search_name,
                last_seen_price,
                last_seen_status,
                last_sent_at,
                first_seen_at,
                updated_at
            FROM {LISTING_STATE_TABLE}
            WHERE listing_id = ? AND search_name = ?
            """,
            (listing_id, search_name),
        ).fetchone()
    except sqlite3.Error as exc:
        raise StateError(
            "Unable to read listing state for "
            f"listing '{listing_id}' in search '{search_name}'."
        ) from exc

    if row is None:
        return None

    return ListingState(
        listing_id=row["listing_id"],
        search_name=row["search_name"],
        last_seen_price=row["last_seen_price"],
        last_seen_status=row["last_seen_status"],
        last_sent_at=row["last_sent_at"],
        first_seen_at=row["first_seen_at"],
        updated_at=row["updated_at"],
    )
