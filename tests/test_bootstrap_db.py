import sqlite3
from pathlib import Path

from scripts.bootstrap_db import main


def test_bootstrap_db_script_creates_listing_state_table(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "listing_state.db"

    exit_code = main(["--db-path", str(db_path)])

    assert exit_code == 0
    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(listing_state)"
            ).fetchall()
        }

    assert "listing_state" in table_names
    assert columns == {
        "listing_id",
        "search_name",
        "last_seen_price",
        "last_seen_status",
        "last_sent_at",
        "first_seen_at",
        "updated_at",
    }
