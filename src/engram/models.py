"""Data models for engram memory records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class MemoryType(Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryRecord:
    id: str
    project: str
    type: MemoryType
    content: str
    title: Optional[str] = None
    importance: float = 0.5
    embedding: Optional[bytes] = None
    created_at: str = field(default_factory=_now_iso)
    accessed_at: str = field(default_factory=_now_iso)
    access_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project": self.project,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "importance": self.importance,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
        }


@dataclass
class QueryResult:
    record: MemoryRecord
    score: float

    def to_dict(self) -> dict:
        d = self.record.to_dict()
        d["score"] = self.score
        return d
