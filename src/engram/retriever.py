"""Query pipeline, scoring, and routing for engram."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from engram.db import EngramDB
from engram.models import MemoryType, QueryResult


def route(query: str) -> list[MemoryType]:
    """Route a query to relevant memory types based on keywords.

    This is a convenience fallback — agents should pass --types explicitly.
    """
    q = query.lower()

    if any(w in q for w in ("how to", "steps", "workflow", "procedure", "instructions")):
        return [MemoryType.PROCEDURAL]
    if any(w in q for w in ("when did", "last time", "what happened", "remember when", "history")):
        return [MemoryType.EPISODIC]
    if any(w in q for w in ("what is", "who is", "preference", "prefers", "likes")):
        return [MemoryType.SEMANTIC]

    return list(MemoryType)


def composite_score(
    fts_rank_normalized: float,
    hours_since_access: float,
    importance: float,
    access_count: int,
) -> float:
    """Compute composite retrieval score.

    Weights: relevance 0.60, recency 0.15, importance 0.20, access 0.05.
    """
    recency = math.exp(-hours_since_access / 720)  # ~30-day half-life
    access_boost = min(access_count / 10, 1.0)

    return (
        0.60 * fts_rank_normalized
        + 0.15 * recency
        + 0.20 * importance
        + 0.05 * access_boost
    )


def _score_records(records: list, now: datetime) -> list[QueryResult]:
    """Score a list of FTS5-ranked records with composite scoring."""
    if not records:
        return []

    scored: list[QueryResult] = []
    for i, rec in enumerate(records):
        # Normalize FTS rank: first result is best (rank 1.0), linearly decreasing
        fts_normalized = 1.0 - (i / len(records)) if len(records) > 1 else 1.0

        accessed = datetime.fromisoformat(rec.accessed_at)
        hours = max((now - accessed).total_seconds() / 3600, 0)

        score = composite_score(
            fts_rank_normalized=fts_normalized,
            hours_since_access=hours,
            importance=rec.importance,
            access_count=rec.access_count,
        )
        scored.append(QueryResult(record=rec, score=round(score, 4)))

    return scored


def retrieve(
    db: EngramDB,
    query: str,
    project: str,
    types: Optional[list[MemoryType]] = None,
    top_k: int = 10,
) -> list[QueryResult]:
    """Retrieve and rank memories using per-type top-k retrieval, merge, and re-rank.

    Algorithm (from the ENGRAM paper):
    1. For each memory type, retrieve top-k candidates separately
    2. Merge (union) all per-type results, deduplicating by ID
    3. Re-rank the merged pool with composite scoring
    4. Return the final top-k
    """
    if types is None:
        types = route(query)

    now = datetime.now(timezone.utc)

    # Per-type retrieval: get top-k candidates from each type independently
    merged: dict[str, QueryResult] = {}  # id -> best QueryResult (dedup)

    for mem_type in types:
        type_records = db.search(
            query=query, project=project, types=[mem_type], limit=top_k,
        )
        type_scored = _score_records(type_records, now)

        for qr in type_scored:
            existing = merged.get(qr.record.id)
            if existing is None or qr.score > existing.score:
                merged[qr.record.id] = qr

    if not merged:
        return []

    # Re-rank the merged pool and take final top-k
    results = sorted(merged.values(), key=lambda qr: qr.score, reverse=True)[:top_k]

    # Touch retrieved memories
    for qr in results:
        db.touch(qr.record.id)

    return results
