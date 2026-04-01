"""Tests for engram.db — SQLite + FTS5 storage layer."""

import sqlite3

import pytest

from engram.db import EngramDB
from engram.models import MemoryType


class TestSchema:
    def test_creates_tables(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        conn = sqlite3.connect(tmp_db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "memories" in table_names
        assert "memories_fts" in table_names
        conn.close()
        db.close()

    def test_idempotent_init(self, tmp_db_path):
        db1 = EngramDB(tmp_db_path)
        db1.close()
        db2 = EngramDB(tmp_db_path)
        db2.close()


class TestInsert:
    def test_insert_returns_id(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(
            project="test",
            type=MemoryType.SEMANTIC,
            content="User prefers dark mode",
        )
        assert isinstance(id_, str)
        assert len(id_) == 32  # uuid4 hex
        db.close()

    def test_insert_with_title(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(
            project="test",
            type=MemoryType.EPISODIC,
            content="Fixed the pagination bug",
            title="Pagination fix",
            importance=0.8,
        )
        rec = db.get(id_)
        assert rec.title == "Pagination fix"
        assert rec.importance == 0.8
        assert rec.type == MemoryType.EPISODIC
        db.close()

    def test_insert_default_importance(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(
            project="test", type=MemoryType.SEMANTIC, content="a fact"
        )
        rec = db.get(id_)
        assert rec.importance == 0.5
        db.close()


class TestGet:
    def test_get_existing(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(
            project="test", type=MemoryType.SEMANTIC, content="hello"
        )
        rec = db.get(id_)
        assert rec.id == id_
        assert rec.content == "hello"
        assert rec.project == "test"
        assert rec.type == MemoryType.SEMANTIC
        assert rec.created_at is not None
        assert rec.accessed_at is not None
        assert rec.access_count == 0
        db.close()

    def test_get_nonexistent(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        assert db.get("nonexistent") is None
        db.close()


class TestList:
    def test_list_by_project(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="one")
        db.insert(project="b", type=MemoryType.SEMANTIC, content="two")
        db.insert(project="a", type=MemoryType.EPISODIC, content="three")
        results = db.list(project="a")
        assert len(results) == 2
        db.close()

    def test_list_by_type(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="one")
        db.insert(project="a", type=MemoryType.EPISODIC, content="two")
        results = db.list(project="a", type=MemoryType.SEMANTIC)
        assert len(results) == 1
        assert results[0].type == MemoryType.SEMANTIC
        db.close()

    def test_list_with_limit(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        for i in range(5):
            db.insert(project="a", type=MemoryType.SEMANTIC, content=f"fact {i}")
        results = db.list(project="a", limit=3)
        assert len(results) == 3
        db.close()

    def test_list_ordered_by_created_at_desc(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id1 = db.insert(project="a", type=MemoryType.SEMANTIC, content="first")
        id2 = db.insert(project="a", type=MemoryType.SEMANTIC, content="second")
        results = db.list(project="a")
        assert results[0].id == id2  # most recent first
        db.close()


class TestDelete:
    def test_delete_existing(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(project="a", type=MemoryType.SEMANTIC, content="gone")
        assert db.delete(id_) is True
        assert db.get(id_) is None
        db.close()

    def test_delete_nonexistent(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        assert db.delete("nope") is False
        db.close()


class TestTouch:
    def test_touch_updates_access(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(project="a", type=MemoryType.SEMANTIC, content="x")
        rec_before = db.get(id_)
        db.touch(id_)
        rec_after = db.get(id_)
        assert rec_after.access_count == rec_before.access_count + 1
        assert rec_after.accessed_at >= rec_before.accessed_at
        db.close()


class TestStats:
    def test_stats(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="one")
        db.insert(project="a", type=MemoryType.SEMANTIC, content="two")
        db.insert(project="a", type=MemoryType.EPISODIC, content="three")
        db.insert(project="b", type=MemoryType.PROCEDURAL, content="four")
        stats = db.stats(project="a")
        assert stats["total"] == 3
        assert stats["by_type"]["semantic"] == 2
        assert stats["by_type"]["episodic"] == 1
        assert stats["by_type"].get("procedural", 0) == 0
        db.close()

    def test_stats_empty(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        stats = db.stats(project="empty")
        assert stats["total"] == 0
        db.close()


class TestFTSSearch:
    def test_search_finds_match(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="User prefers dark mode and vim keybindings")
        db.insert(project="a", type=MemoryType.SEMANTIC, content="The API uses REST endpoints")
        results = db.search(query="dark mode", project="a")
        assert len(results) >= 1
        assert any("dark mode" in r.content for r in results)
        db.close()

    def test_search_respects_project(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="dark mode preference")
        db.insert(project="b", type=MemoryType.SEMANTIC, content="dark mode setting")
        results = db.search(query="dark mode", project="a")
        assert len(results) == 1
        db.close()

    def test_search_respects_type_filter(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="dark mode pref")
        db.insert(project="a", type=MemoryType.EPISODIC, content="enabled dark mode yesterday")
        results = db.search(query="dark mode", project="a", types=[MemoryType.SEMANTIC])
        assert len(results) == 1
        assert results[0].type == MemoryType.SEMANTIC
        db.close()

    def test_search_returns_ranked(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="dark mode is preferred by the user")
        db.insert(project="a", type=MemoryType.SEMANTIC, content="mode of transport is walking")
        results = db.search(query="dark mode", project="a")
        # "dark mode" should rank higher than just "mode"
        assert results[0].content.startswith("dark mode")
        db.close()

    def test_search_no_results(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="a", type=MemoryType.SEMANTIC, content="hello world")
        results = db.search(query="quantum physics", project="a")
        assert len(results) == 0
        db.close()

    def test_search_with_limit(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        for i in range(10):
            db.insert(project="a", type=MemoryType.SEMANTIC, content=f"test fact number {i}")
        results = db.search(query="test fact", project="a", limit=3)
        assert len(results) <= 3
        db.close()

    def test_fts_syncs_on_delete(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(project="a", type=MemoryType.SEMANTIC, content="unique searchable term xyzzy")
        assert len(db.search(query="xyzzy", project="a")) == 1
        db.delete(id_)
        assert len(db.search(query="xyzzy", project="a")) == 0
        db.close()
