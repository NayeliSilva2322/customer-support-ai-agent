import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "ltm"
    / "conversations.sqlite3"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            turn_count INTEGER NOT NULL DEFAULT 0,
            last_user_message TEXT NOT NULL DEFAULT '',
            last_assistant_message TEXT NOT NULL DEFAULT '',
            last_status TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS conversation_turns (
            turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES conversations(session_id)
                ON DELETE CASCADE,
            user_message TEXT NOT NULL,
            assistant_message TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
            ON conversations(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_conversation_turns_session
            ON conversation_turns(session_id, turn_id);
        """
    )


def create_conversation(session_id: str, user_id: str) -> None:
    now = _now_iso()
    with _connection() as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO conversations (session_id, user_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, now, now),
        )


def get_conversation(
    session_id: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    with _connection() as connection:
        _ensure_schema(connection)
        query = """
            SELECT session_id, user_id, created_at, updated_at, turn_count
            FROM conversations
            WHERE session_id = ?
        """
        parameters: tuple[str, ...] = (session_id,)
        if user_id is not None:
            query += " AND user_id = ?"
            parameters += (user_id,)
        row = connection.execute(query, parameters).fetchone()
    return dict(row) if row else None


def record_conversation_turn(
    session_id: str,
    user_message: str,
    assistant_message: str,
    status: str,
) -> None:
    now = _now_iso()
    with _connection() as connection:
        _ensure_schema(connection)
        cursor = connection.execute(
            """
            INSERT INTO conversation_turns
                (session_id, user_message, assistant_message, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, user_message, assistant_message, status, now),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("No se pudo guardar el turno de la conversación.")
        connection.execute(
            """
            UPDATE conversations
            SET updated_at = ?, turn_count = turn_count + 1,
                last_user_message = ?, last_assistant_message = ?, last_status = ?
            WHERE session_id = ?
            """,
            (now, user_message, assistant_message, status, session_id),
        )


def list_conversations(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with _connection() as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT session_id, user_id, created_at, updated_at, turn_count,
                   last_user_message, last_assistant_message, last_status
            FROM conversations
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation_details(
    session_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    with _connection() as connection:
        _ensure_schema(connection)
        conversation = connection.execute(
            """
            SELECT session_id, user_id, created_at, updated_at, turn_count,
                   last_user_message, last_assistant_message, last_status
            FROM conversations
            WHERE session_id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()
        if conversation is None:
            return None
        turns = connection.execute(
            """
            SELECT turn_id, user_message, assistant_message, status, created_at
            FROM conversation_turns
            WHERE session_id = ?
            ORDER BY turn_id
            """,
            (session_id,),
        ).fetchall()
    return {**dict(conversation), "turns": [dict(turn) for turn in turns]}
