"""
Keep Engine — persistence layer.

SQLite, not because it's the "real" production choice — a real deployment
needs a hosted database with encryption at rest, same caveat the ingestion
API's own README already makes about itself — but because it's the
smallest thing that actually persists across runs, which an in-memory list
can't do. Three tables: households, policies (normalized Policy objects
stored as JSON, one row per ingested policy), and gap_findings (output of
gap_rules.py, cached so /report doesn't recompute silently on every hit
without a record of what was shown when).
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

# Overridable via KEEP_ENGINE_DB_PATH — some mounted/networked filesystems
# (this project's dev sandbox included) don't support the file locking
# SQLite needs and raise "disk I/O error" on a plain relative path there.
# On a normal local machine the default below just works.
DB_PATH = Path(os.getenv("KEEP_ENGINE_DB_PATH", str(Path(__file__).resolve().parent / "keep_engine.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS households (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    state TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id INTEGER NOT NULL REFERENCES households(id),
    policy_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gap_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id INTEGER NOT NULL REFERENCES households(id),
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    exposure TEXT,
    computed_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def create_household(name: str, state: Optional[str]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO households (name, state, created_at) VALUES (?, ?, ?)",
            (name, state, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_households() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM households ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_household(household_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM households WHERE id = ?", (household_id,)).fetchone()
        return dict(row) if row else None


def save_policies(household_id: int, policies: list) -> None:
    with get_conn() as conn:
        for p in policies:
            conn.execute(
                "INSERT INTO policies (household_id, policy_json, ingested_at) VALUES (?, ?, ?)",
                (household_id, p.model_dump_json(), datetime.utcnow().isoformat()),
            )


def get_policies(household_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT policy_json FROM policies WHERE household_id = ?", (household_id,)
        ).fetchall()
        return [json.loads(r["policy_json"]) for r in rows]


def save_findings(household_id: int, findings: list[dict]) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM gap_findings WHERE household_id = ?", (household_id,))
        for f in findings:
            conn.execute(
                "INSERT INTO gap_findings "
                "(household_id, rule_id, severity, title, description, exposure, computed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    household_id,
                    f["rule_id"],
                    f["severity"],
                    f["title"],
                    f["description"],
                    f.get("exposure", ""),
                    datetime.utcnow().isoformat(),
                ),
            )


def get_findings(household_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM gap_findings WHERE household_id = ? ORDER BY "
            "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END",
            (household_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_household(household_id: int) -> bool:
    """
    Permanently removes a household and everything under it (policies,
    cached gap findings). Used by the Clients page's Remove action --
    irreversible, so the UI is expected to confirm with the user before
    ever calling this. Returns False (no-op) if the household doesn't
    exist, so callers can 404 instead of silently "succeeding."
    """
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM households WHERE id = ?", (household_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM gap_findings WHERE household_id = ?", (household_id,))
        conn.execute("DELETE FROM policies WHERE household_id = ?", (household_id,))
        conn.execute("DELETE FROM households WHERE id = ?", (household_id,))
        return True
