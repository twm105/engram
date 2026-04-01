"""Click CLI for engram — all output is JSON to stdout."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from engram.db import EngramDB
from engram.models import MemoryType
from engram.retriever import retrieve


def _db_path() -> str:
    path = os.environ.get("ENGRAM_DB")
    if path:
        return path
    default = Path.home() / ".local" / "share" / "engram" / "memories.db"
    default.parent.mkdir(parents=True, exist_ok=True)
    return str(default)


def _project() -> str:
    return os.environ.get("ENGRAM_PROJECT", "default")


def _output(data: dict) -> None:
    click.echo(json.dumps(data, indent=2))


MEMORY_TYPES = click.Choice(["episodic", "semantic", "procedural"], case_sensitive=False)


@click.group()
def cli():
    """Engram: lightweight memory system for conversational agents.

    Stores and retrieves typed memories (episodic, semantic, procedural) using
    FTS5 full-text search with composite scoring. All output is JSON.

    \b
    Environment variables:
      ENGRAM_PROJECT  Default project namespace (default: "default")
      ENGRAM_DB       Database path (default: ~/.local/share/engram/memories.db)

    \b
    Examples:
      engram add semantic "User prefers dark mode" --importance 0.8
      engram query "editor preferences" --project myapp
      engram list --type episodic --limit 5
      engram stats --project myapp
    """
    pass


@cli.command()
@click.argument("type", type=MEMORY_TYPES)
@click.argument("content")
@click.option("--title", default=None, help="Short label for the memory (recommended for episodic/procedural).")
@click.option("--project", default=None, help="Project namespace. Overrides ENGRAM_PROJECT env var.")
@click.option("--importance", default=0.5, type=float, help="Importance score 0.0-1.0. Use 0.8+ for critical items.")
def add(type: str, content: str, title: Optional[str], project: Optional[str], importance: float):
    """Store a new memory.

    \b
    Memory types:
      episodic    - Events, incidents, what happened and when
      semantic    - Facts, preferences, knowledge, configurations
      procedural  - Workflows, how-to steps, deployment procedures

    \b
    Examples:
      engram add semantic "User prefers dark mode"
      engram add episodic "Fixed pagination bug" --title "Pagination fix" --importance 0.8
      engram add procedural "Run make deploy, then check /health" --title "Deploy steps"
    """
    proj = project or _project()
    db = EngramDB(_db_path())
    try:
        id_ = db.insert(
            project=proj,
            type=MemoryType(type),
            content=content,
            title=title,
            importance=importance,
        )
        _output({"id": id_, "type": type, "project": proj})
    finally:
        db.close()


@cli.command()
@click.argument("text")
@click.option("--project", default=None, help="Project namespace. Overrides ENGRAM_PROJECT env var.")
@click.option("--types", default=None, help="Comma-separated memory types to query (e.g. 'semantic,episodic').")
@click.option("--top-k", default=10, type=int, help="Max results to return (default: 10).")
def query(text: str, project: Optional[str], types: Optional[str], top_k: int):
    """Query memories by text using full-text search with composite scoring.

    Retrieves top-k candidates from each memory type independently, merges the
    results, and re-ranks by a composite score blending relevance, recency,
    importance, and access frequency.

    If --types is not specified, a keyword-based router selects relevant types
    automatically. Pass --types explicitly for precise control.

    \b
    Examples:
      engram query "dark mode preferences"
      engram query "how to deploy" --types procedural
      engram query "what happened last week" --types episodic --top-k 5
    """
    proj = project or _project()
    type_list = None
    if types:
        type_list = [MemoryType(t.strip()) for t in types.split(",")]

    db = EngramDB(_db_path())
    try:
        results = retrieve(db, query=text, project=proj, types=type_list, top_k=top_k)
        _output({
            "query": text,
            "results": [r.to_dict() for r in results],
        })
    finally:
        db.close()


@cli.command("list")
@click.option("--project", default=None, help="Project namespace. Overrides ENGRAM_PROJECT env var.")
@click.option("--type", "type_", default=None, type=MEMORY_TYPES, help="Filter by memory type.")
@click.option("--limit", default=50, type=int, help="Max results (default: 50).")
def list_cmd(project: Optional[str], type_: Optional[str], limit: int):
    """List stored memories, ordered by most recently created.

    \b
    Examples:
      engram list
      engram list --type semantic --limit 10
      engram list --project myapp
    """
    proj = project or _project()
    mem_type = MemoryType(type_) if type_ else None

    db = EngramDB(_db_path())
    try:
        records = db.list(project=proj, type=mem_type, limit=limit)
        _output({"memories": [r.to_dict() for r in records]})
    finally:
        db.close()


@cli.command()
@click.argument("id")
def get(id: str):
    """Get a specific memory by ID.

    Returns the full memory record as JSON. Exits with code 1 if not found.
    """
    db = EngramDB(_db_path())
    try:
        rec = db.get(id)
        if rec is None:
            click.echo(f"Memory {id} not found", err=True)
            raise SystemExit(1)
        _output(rec.to_dict())
    finally:
        db.close()


@cli.command()
@click.argument("id")
def delete(id: str):
    """Delete a memory by ID.

    Returns {"deleted": true/false, "id": "..."} indicating success.
    """
    db = EngramDB(_db_path())
    try:
        deleted = db.delete(id)
        _output({"deleted": deleted, "id": id})
    finally:
        db.close()


@cli.command()
@click.option("--project", default=None, help="Project namespace. Overrides ENGRAM_PROJECT env var.")
def stats(project: Optional[str]):
    """Show memory statistics for a project.

    Returns total count and breakdown by memory type.
    """
    proj = project or _project()
    db = EngramDB(_db_path())
    try:
        s = db.stats(project=proj)
        _output(s)
    finally:
        db.close()
