"""Database access layer using SQLite.

Provides connection handling, schema migration/initialization, and thread-safe,
parameterized SQL operations.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from app.config import settings


def get_db_path(custom_path: Optional[str] = None) -> str:
    """Return configured database path or custom path if provided."""
    return custom_path or settings.DATABASE_PATH


_INITIALIZED_DBS = set()


def get_connection(custom_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a SQLite connection with Row factory and foreign keys enabled.
    
    Automatically creates the schema if it hasn't been initialized yet.
    """
    path = get_db_path(custom_path)
    # Ensure directory exists if not an in-memory database
    if path != ":memory:":
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    if path not in _INITIALIZED_DBS:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    message TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    assigned_team TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    draft_response TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    classification_explanation TEXT NOT NULL,
                    needs_human_review INTEGER NOT NULL DEFAULT 0,
                    approved_by TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);")
        _INITIALIZED_DBS.add(path)

    return conn


def init_db(custom_path: Optional[str] = None) -> None:
    """Initialize database tables with parameterized DDL."""
    conn = get_connection(custom_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    message TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    assigned_team TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    draft_response TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    classification_explanation TEXT NOT NULL,
                    needs_human_review INTEGER NOT NULL DEFAULT 0,
                    approved_by TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
            """)
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert an sqlite3.Row to a dictionary with boolean conversion."""
    d = dict(row)
    d["needs_human_review"] = bool(d.get("needs_human_review", 0))
    return d


def insert_ticket(ticket_data: Dict[str, Any], custom_path: Optional[str] = None) -> Dict[str, Any]:
    """Insert a new ticket record into SQLite using parameterized queries.

    Raises:
        sqlite3.IntegrityError: If ticket_id already exists.
    """
    now = datetime.now(timezone.utc).isoformat()
    record = {
        **ticket_data,
        "needs_human_review": 1 if ticket_data.get("needs_human_review") else 0,
        "created_at": ticket_data.get("created_at", now),
        "updated_at": ticket_data.get("updated_at", now),
    }

    query = """
        INSERT INTO tickets (
            ticket_id, message, category, priority, assigned_team,
            summary, draft_response, status, confidence_score,
            classification_explanation, needs_human_review,
            approved_by, approved_at, created_at, updated_at
        ) VALUES (
            :ticket_id, :message, :category, :priority, :assigned_team,
            :summary, :draft_response, :status, :confidence_score,
            :classification_explanation, :needs_human_review,
            :approved_by, :approved_at, :created_at, :updated_at
        );
    """
    conn = get_connection(custom_path)
    try:
        with conn:
            conn.execute(query, record)
        return get_ticket(record["ticket_id"], custom_path) or record
    finally:
        conn.close()


def get_ticket(ticket_id: str, custom_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single ticket by its ticket_id."""
    conn = get_connection(custom_path)
    try:
        cursor = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ? LIMIT 1;",
            (ticket_id,)
        )
        row = cursor.fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def list_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    custom_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List tickets with optional status and category filtering."""
    query = "SELECT * FROM tickets WHERE 1=1"
    params: List[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY created_at DESC;"

    conn = get_connection(custom_path)
    try:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_ticket_approval(
    ticket_id: str,
    reviewer_name: str = "Support Lead",
    custom_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Transition ticket to 'Ready' status and record approval metadata."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(custom_path)
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE tickets
                SET status = 'Ready',
                    approved_by = ?,
                    approved_at = ?,
                    updated_at = ?
                WHERE ticket_id = ?;
                """,
                (reviewer_name, now, now, ticket_id)
            )
            if cursor.rowcount == 0:
                return None
        return get_ticket(ticket_id, custom_path)
    finally:
        conn.close()


def check_db_health(custom_path: Optional[str] = None) -> bool:
    """Verify database connection and query readiness."""
    try:
        conn = get_connection(custom_path)
        cursor = conn.execute("SELECT 1;")
        res = cursor.fetchone()
        conn.close()
        return bool(res and res[0] == 1)
    except Exception:
        return False
