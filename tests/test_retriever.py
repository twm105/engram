"""Tests for engram.retriever — query pipeline, scoring, routing."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from engram.db import EngramDB
from engram.models import MemoryType
from engram.retriever import composite_score, retrieve, route


class TestRoute:
    def test_procedural_keywords(self):
        assert MemoryType.PROCEDURAL in route("how to deploy the app")
        assert MemoryType.PROCEDURAL in route("steps for setting up")
        assert MemoryType.PROCEDURAL in route("workflow for CI")

    def test_episodic_keywords(self):
        assert MemoryType.EPISODIC in route("when did we fix the bug")
        assert MemoryType.EPISODIC in route("last time this happened")
        assert MemoryType.EPISODIC in route("what happened with the deploy")

    def test_semantic_keywords(self):
        assert MemoryType.SEMANTIC in route("what is the API endpoint")
        assert MemoryType.SEMANTIC in route("user prefers dark mode")

    def test_default_returns_all(self):
        result = route("tell me about the project")
        assert set(result) == {MemoryType.EPISODIC, MemoryType.SEMANTIC, MemoryType.PROCEDURAL}

    def test_case_insensitive(self):
        assert MemoryType.PROCEDURAL in route("How To deploy")


class TestCompositeScore:
    def test_basic_scoring(self):
        score = composite_score(
            fts_rank_normalized=1.0,
            hours_since_access=0,
            importance=1.0,
            access_count=10,
        )
        # Maximum possible score: 0.60 + 0.15 + 0.20 + 0.05 = 1.0
        assert 0.95 <= score <= 1.0

    def test_zero_relevance(self):
        score = composite_score(
            fts_rank_normalized=0.0,
            hours_since_access=0,
            importance=0.0,
            access_count=0,
        )
        # Should still have recency contribution (exp(0) = 1.0 * 0.15)
        assert 0.14 <= score <= 0.16

    def test_recency_decay(self):
        recent = composite_score(
            fts_rank_normalized=0.5,
            hours_since_access=1,
            importance=0.5,
            access_count=0,
        )
        old = composite_score(
            fts_rank_normalized=0.5,
            hours_since_access=720 * 3,  # ~90 days
            importance=0.5,
            access_count=0,
        )
        assert recent > old

    def test_importance_effect(self):
        low = composite_score(
            fts_rank_normalized=0.5,
            hours_since_access=100,
            importance=0.1,
            access_count=0,
        )
        high = composite_score(
            fts_rank_normalized=0.5,
            hours_since_access=100,
            importance=0.9,
            access_count=0,
        )
        assert high > low

    def test_access_count_capped(self):
        score10 = composite_score(
            fts_rank_normalized=0.5,
            hours_since_access=100,
            importance=0.5,
            access_count=10,
        )
        score100 = composite_score(
            fts_rank_normalized=0.5,
            hours_since_access=100,
            importance=0.5,
            access_count=100,
        )
        # access boost is capped at 1.0, so these should be equal
        assert score10 == score100


class TestRetrieve:
    def test_retrieve_finds_relevant(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="User prefers dark mode and vim keybindings")
        db.insert(project="p", type=MemoryType.SEMANTIC, content="The API uses GraphQL not REST")
        results = retrieve(db, query="dark mode", project="p")
        assert len(results) >= 1
        assert "dark mode" in results[0].record.content
        db.close()

    def test_retrieve_respects_types(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="dark mode setting")
        db.insert(project="p", type=MemoryType.EPISODIC, content="enabled dark mode yesterday")
        results = retrieve(db, query="dark mode", project="p", types=[MemoryType.EPISODIC])
        assert len(results) == 1
        assert results[0].record.type == MemoryType.EPISODIC
        db.close()

    def test_retrieve_respects_top_k(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        for i in range(10):
            db.insert(project="p", type=MemoryType.SEMANTIC, content=f"fact about testing number {i}")
        results = retrieve(db, query="testing", project="p", top_k=3)
        assert len(results) <= 3
        db.close()

    def test_retrieve_returns_sorted_by_score(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="dark mode is the user preference", importance=0.9)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="mode of transport", importance=0.1)
        results = retrieve(db, query="dark mode", project="p")
        if len(results) >= 2:
            assert results[0].score >= results[1].score
        db.close()

    def test_retrieve_touches_results(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        id_ = db.insert(project="p", type=MemoryType.SEMANTIC, content="dark mode preference")
        retrieve(db, query="dark mode", project="p")
        rec = db.get(id_)
        assert rec.access_count == 1
        db.close()

    def test_retrieve_no_results(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="hello world")
        results = retrieve(db, query="quantum entanglement", project="p")
        assert len(results) == 0
        db.close()

    def test_retrieve_uses_router_when_no_types(self, tmp_db_path):
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.PROCEDURAL, content="how to deploy the application step by step")
        db.insert(project="p", type=MemoryType.SEMANTIC, content="the deploy server is in us-east-1")
        # "how to deploy" should route to procedural
        results = retrieve(db, query="how to deploy", project="p")
        assert len(results) >= 1
        db.close()


class TestPerTypeRetrieval:
    """Tests for per-type top-k retrieval, merge, and re-rank (paper algorithm)."""

    def test_type_balanced_results(self, tmp_db_path):
        """When querying all types, results should include top matches from EACH type,
        not just the globally highest-ranked type."""
        db = EngramDB(tmp_db_path)
        # Add many semantic matches that would dominate a single-query approach
        for i in range(10):
            db.insert(project="p", type=MemoryType.SEMANTIC, content=f"deploy config setting {i}")
        # Add one episodic and one procedural match
        db.insert(project="p", type=MemoryType.EPISODIC, content="deploy failed last Tuesday due to config error")
        db.insert(project="p", type=MemoryType.PROCEDURAL, content="deploy steps: check config then run deploy script")

        results = retrieve(db, query="deploy config", project="p", top_k=5)
        result_types = {r.record.type for r in results}
        # Should include results from multiple types, not just semantic
        assert len(result_types) >= 2
        db.close()

    def test_per_type_top_k_limits(self, tmp_db_path):
        """Each type should contribute at most top_k results to the merge pool."""
        db = EngramDB(tmp_db_path)
        for i in range(20):
            db.insert(project="p", type=MemoryType.SEMANTIC, content=f"semantic fact about testing {i}")
        for i in range(20):
            db.insert(project="p", type=MemoryType.EPISODIC, content=f"episodic event about testing {i}")

        # With top_k=3, we should get at most 3 per type, then re-rank to final 3
        results = retrieve(db, query="testing", project="p", top_k=3)
        assert len(results) <= 3
        db.close()

    def test_deduplication_across_types(self, tmp_db_path):
        """Same memory should not appear twice if it somehow matches in multiple type queries."""
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="the API uses dark mode theming")
        results = retrieve(db, query="dark mode", project="p")
        ids = [r.record.id for r in results]
        assert len(ids) == len(set(ids))  # no duplicates
        db.close()

    def test_single_type_still_works(self, tmp_db_path):
        """When only one type is requested, per-type retrieval should still work correctly."""
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="user prefers dark mode")
        db.insert(project="p", type=MemoryType.EPISODIC, content="switched to dark mode yesterday")
        results = retrieve(db, query="dark mode", project="p", types=[MemoryType.SEMANTIC])
        assert len(results) == 1
        assert results[0].record.type == MemoryType.SEMANTIC
        db.close()

    def test_empty_type_does_not_break(self, tmp_db_path):
        """If one type has no matches, the other types should still return results."""
        db = EngramDB(tmp_db_path)
        db.insert(project="p", type=MemoryType.SEMANTIC, content="dark mode preference")
        # No episodic or procedural memories exist
        results = retrieve(db, query="dark mode", project="p")
        assert len(results) >= 1
        assert results[0].record.type == MemoryType.SEMANTIC
        db.close()
