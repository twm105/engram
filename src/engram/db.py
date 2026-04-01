"""SQLite + FTS5 storage layer for engram."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from engram.models import MemoryRecord, MemoryType

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id           TEXT PRIMARY KEY,
    project      TEXT NOT NULL,
    type         TEXT NOT NULL CHECK(type IN ('episodic','semantic','procedural')),
    title        TEXT,
    content      TEXT NOT NULL,
    importance   REAL DEFAULT 0.5,
    embedding    BLOB,
    created_at   TEXT NOT NULL,
    accessed_at  TEXT NOT NULL,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memories_project_type ON memories(project, type);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    title, content, type, project,
    content='memories', content_rowid='rowid'
);
"""

FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, title, content, type, project)
    VALUES (new.rowid, new.title, new.content, new.type, new.project);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, title, content, type, project)
    VALUES ('delete', old.rowid, old.title, old.content, old.type, old.project);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, title, content, type, project)
    VALUES ('delete', old.rowid, old.title, old.content, old.type, old.project);
    INSERT INTO memories_fts(rowid, title, content, type, project)
    VALUES (new.rowid, new.title, new.content, new.type, new.project);
END;
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        project=row["project"],
        type=MemoryType(row["type"]),
        title=row["title"],
        content=row["content"],
        importance=row["importance"],
        embedding=row["embedding"],
        created_at=row["created_at"],
        accessed_at=row["accessed_at"],
        access_count=row["access_count"],
    )


class EngramDB:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(SCHEMA)
        self._conn.executescript(FTS_SCHEMA)
        self._conn.executescript(FTS_TRIGGERS)

    def close(self) -> None:
        self._conn.close()

    def insert(
        self,
        project: str,
        type: MemoryType,
        content: str,
        title: Optional[str] = None,
        importance: float = 0.5,
    ) -> str:
        id_ = uuid.uuid4().hex
        now = _now_iso()
        self._conn.execute(
            """INSERT INTO memories (id, project, type, title, content, importance, created_at, accessed_at, access_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (id_, project, type.value, title, content, importance, now, now),
        )
        self._conn.commit()
        return id_

    def get(self, id_: str) -> Optional[MemoryRecord]:
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (id_,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def list(
        self,
        project: str,
        type: Optional[MemoryType] = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        if type is not None:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE project = ? AND type = ? ORDER BY created_at DESC LIMIT ?",
                (project, type.value, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE project = ? ORDER BY created_at DESC LIMIT ?",
                (project, limit),
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    def delete(self, id_: str) -> bool:
        cursor = self._conn.execute("DELETE FROM memories WHERE id = ?", (id_,))
        self._conn.commit()
        return cursor.rowcount > 0

    def touch(self, id_: str) -> None:
        self._conn.execute(
            "UPDATE memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
            (_now_iso(), id_),
        )
        self._conn.commit()

    def stats(self, project: str) -> dict:
        rows = self._conn.execute(
            "SELECT type, COUNT(*) as cnt FROM memories WHERE project = ? GROUP BY type",
            (project,),
        ).fetchall()
        by_type = {row["type"]: row["cnt"] for row in rows}
        total = sum(by_type.values())
        return {"total": total, "by_type": by_type}

    def search(
        self,
        query: str,
        project: str,
        types: Optional[list[MemoryType]] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        # Build FTS5 query with project filter
        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []

        sql = """
            SELECT m.*, fts.rank
            FROM memories_fts fts
            JOIN memories m ON m.rowid = fts.rowid
            WHERE memories_fts MATCH ?
              AND m.project = ?
        """
        params: list = [fts_query, project]

        if types:
            placeholders = ",".join("?" for _ in types)
            sql += f" AND m.type IN ({placeholders})"
            params.extend(t.value for t in types)

        sql += " ORDER BY fts.rank LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_record(r) for r in rows]


def _sanitize_fts_query(query: str) -> str:
    """Escape special FTS5 characters and build a safe query."""
    # Remove FTS5 special characters that could cause syntax errors
    special = set('"*():-^{}[]|&!')
    cleaned = "".join(c if c not in special else " " for c in query)
    tokens = cleaned.split()
    if not tokens:
        return ""
    # Quote each token to prevent FTS5 syntax issues
    return " ".join(f'"{t}"' for t in tokens)
