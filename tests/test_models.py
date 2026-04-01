"""Tests for engram.models — memory types, records, and query results."""

import json
from datetime import datetime, timezone

from engram.models import MemoryRecord, MemoryType, QueryResult


class TestMemoryType:
    def test_values(self):
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"

    def test_from_string(self):
        assert MemoryType("episodic") == MemoryType.EPISODIC
        assert MemoryType("semantic") == MemoryType.SEMANTIC
        assert MemoryType("procedural") == MemoryType.PROCEDURAL

    def test_all_types(self):
        assert len(MemoryType) == 3


class TestMemoryRecord:
    def test_create_minimal(self):
        rec = MemoryRecord(
            id="abc123",
            project="test",
            type=MemoryType.SEMANTIC,
            content="User prefers dark mode",
        )
        assert rec.id == "abc123"
        assert rec.project == "test"
        assert rec.type == MemoryType.SEMANTIC
        assert rec.content == "User prefers dark mode"
        assert rec.title is None
        assert rec.importance == 0.5
        assert rec.access_count == 0
        assert rec.embedding is None

    def test_create_full(self):
        now = datetime.now(timezone.utc).isoformat()
        rec = MemoryRecord(
            id="abc123",
            project="myapp",
            type=MemoryType.EPISODIC,
            title="Fixed the bug",
            content="Resolved pagination issue in API",
            importance=0.8,
            created_at=now,
            accessed_at=now,
            access_count=5,
        )
        assert rec.title == "Fixed the bug"
        assert rec.importance == 0.8
        assert rec.access_count == 5

    def test_to_dict(self):
        rec = MemoryRecord(
            id="abc123",
            project="test",
            type=MemoryType.SEMANTIC,
            content="some fact",
        )
        d = rec.to_dict()
        assert d["id"] == "abc123"
        assert d["type"] == "semantic"
        assert d["content"] == "some fact"
        assert "embedding" not in d  # should be excluded from dict output

    def test_to_dict_is_json_serializable(self):
        rec = MemoryRecord(
            id="abc123",
            project="test",
            type=MemoryType.PROCEDURAL,
            title="Deploy steps",
            content="Run make deploy",
        )
        result = json.dumps(rec.to_dict())
        assert isinstance(result, str)

    def test_defaults_have_timestamps(self):
        rec = MemoryRecord(
            id="x",
            project="p",
            type=MemoryType.SEMANTIC,
            content="c",
        )
        assert rec.created_at is not None
        assert rec.accessed_at is not None


class TestQueryResult:
    def test_create(self):
        rec = MemoryRecord(
            id="abc",
            project="test",
            type=MemoryType.SEMANTIC,
            content="fact",
        )
        qr = QueryResult(record=rec, score=0.85)
        assert qr.score == 0.85
        assert qr.record.id == "abc"

    def test_to_dict(self):
        rec = MemoryRecord(
            id="abc",
            project="test",
            type=MemoryType.SEMANTIC,
            content="fact",
        )
        qr = QueryResult(record=rec, score=0.85)
        d = qr.to_dict()
        assert d["score"] == 0.85
        assert d["id"] == "abc"
        assert d["content"] == "fact"
