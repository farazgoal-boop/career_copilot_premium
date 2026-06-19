"""SQLite-backed persistence helpers for desktop session state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .encryption import decrypt_json_payload, encrypt_json_payload


def _ensure_session_schema(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "microphone_enabled" not in existing_columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN microphone_enabled INTEGER NOT NULL DEFAULT 0"
        )
    if "session_worker_state_path" not in existing_columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN session_worker_state_path TEXT NOT NULL DEFAULT ''"
        )
    if "worker_status" not in existing_columns:
        connection.execute(
            "ALTER TABLE sessions ADD COLUMN worker_status TEXT NOT NULL DEFAULT 'stopped'"
        )


def initialize_session_database(path: str | Path) -> Path:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                profile_directory TEXT NOT NULL,
                profile_name TEXT NOT NULL,
                company_name TEXT NOT NULL,
                role_title TEXT NOT NULL,
                microphone_enabled INTEGER NOT NULL DEFAULT 0,
                session_state_path TEXT NOT NULL,
                session_command_queue_path TEXT NOT NULL,
                session_database_path TEXT NOT NULL,
                session_worker_state_path TEXT NOT NULL DEFAULT '',
                worker_status TEXT NOT NULL DEFAULT 'stopped',
                tags_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_session_schema(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS session_states (
                session_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        connection.commit()
    return database_path


def upsert_session_entry(path: str | Path, entry: dict[str, object]) -> Path:
    database_path = initialize_session_database(path)
    tags = entry.get("tags", [])
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO sessions (
                session_id,
                profile_directory,
                profile_name,
                company_name,
                role_title,
                microphone_enabled,
                session_state_path,
                session_command_queue_path,
                session_database_path,
                session_worker_state_path,
                worker_status,
                tags_json,
                notes,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                profile_directory=excluded.profile_directory,
                profile_name=excluded.profile_name,
                company_name=excluded.company_name,
                role_title=excluded.role_title,
                microphone_enabled=excluded.microphone_enabled,
                session_state_path=excluded.session_state_path,
                session_command_queue_path=excluded.session_command_queue_path,
                session_database_path=excluded.session_database_path,
                session_worker_state_path=excluded.session_worker_state_path,
                worker_status=excluded.worker_status,
                tags_json=excluded.tags_json,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                str(entry["session_id"]),
                str(entry["profile_directory"]),
                str(entry["profile_name"]),
                str(entry["company_name"]),
                str(entry["role_title"]),
                1 if bool(entry.get("microphone_enabled", False)) else 0,
                str(entry["session_state_path"]),
                str(entry["session_command_queue_path"]),
                str(entry["session_database_path"]),
                str(entry.get("session_worker_state_path", "")),
                str(entry.get("worker_status", "stopped")),
                json.dumps(tags),
                str(entry.get("notes", "")),
                str(entry["updated_at"]),
            ),
        )
        connection.commit()
    return database_path


def upsert_session_state(path: str | Path, session_id: str, payload: dict[str, object]) -> Path:
    database_path = initialize_session_database(path)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO session_states (session_id, payload_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                session_id,
                encrypt_json_payload(payload),
                str(payload.get("updated_at", "")),
            ),
        )
        connection.commit()
    return database_path


def list_session_entries(path: str | Path) -> dict[str, dict[str, object]]:
    database_path = Path(path)
    if not database_path.exists():
        return {}
    initialize_session_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                session_id,
                profile_directory,
                profile_name,
                company_name,
                role_title,
                microphone_enabled,
                session_state_path,
                session_command_queue_path,
                session_database_path,
                session_worker_state_path,
                worker_status,
                tags_json,
                notes,
                updated_at
            FROM sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()

    entries: dict[str, dict[str, object]] = {}
    for row in rows:
        tags = json.loads(row[11]) if row[11] else []
        entries[row[0]] = {
            "session_id": row[0],
            "profile_directory": row[1],
            "profile_name": row[2],
            "company_name": row[3],
            "role_title": row[4],
            "microphone_enabled": bool(row[5]),
            "session_state_path": row[6],
            "session_command_queue_path": row[7],
            "session_database_path": row[8],
            "session_worker_state_path": row[9],
            "worker_status": row[10],
            "tags": tags,
            "notes": row[12],
            "updated_at": row[13],
        }
    return entries


def get_session_entry(path: str | Path, session_id: str) -> dict[str, object] | None:
    return list_session_entries(path).get(session_id)


def get_session_entry_by_state_path(path: str | Path, state_path: str | Path) -> dict[str, object] | None:
    database_path = Path(path)
    if not database_path.exists():
        return None
    initialize_session_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT
                session_id,
                profile_directory,
                profile_name,
                company_name,
                role_title,
                microphone_enabled,
                session_state_path,
                session_command_queue_path,
                session_database_path,
                session_worker_state_path,
                worker_status,
                tags_json,
                notes,
                updated_at
            FROM sessions
            WHERE session_state_path = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (str(state_path),),
        ).fetchone()
    if row is None:
        return None
    tags = json.loads(row[11]) if row[11] else []
    return {
        "session_id": row[0],
        "profile_directory": row[1],
        "profile_name": row[2],
        "company_name": row[3],
        "role_title": row[4],
        "microphone_enabled": bool(row[5]),
        "session_state_path": row[6],
        "session_command_queue_path": row[7],
        "session_database_path": row[8],
        "session_worker_state_path": row[9],
        "worker_status": row[10],
        "tags": tags,
        "notes": row[12],
        "updated_at": row[13],
    }


def get_session_state(path: str | Path, session_id: str) -> dict[str, object] | None:
    database_path = Path(path)
    if not database_path.exists():
        return None
    initialize_session_database(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM session_states WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    return decrypt_json_payload(row[0])


def get_session_state_by_path(path: str | Path, state_path: str | Path) -> dict[str, object] | None:
    entry = get_session_entry_by_state_path(path, state_path)
    if entry is None:
        return None
    return get_session_state(path, str(entry["session_id"]))


def delete_session(path: str | Path, session_id: str) -> Path:
    database_path = initialize_session_database(path)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("DELETE FROM session_states WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        connection.commit()
    return database_path
