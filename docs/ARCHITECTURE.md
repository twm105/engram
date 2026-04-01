# Architecture

## Overview

Engram is a lightweight memory system for conversational AI agents. It stores typed memories (episodic, semantic, procedural) and retrieves them using full-text search with composite scoring. The system is designed as a pure storage-and-retrieval engine with no LLM or ML dependency — the calling agent handles classification and extraction.

## Design Rationale

### Why typed memory?

The ENGRAM paper (Patel & Patel, 2025; [arxiv:2511.12960](https://arxiv.org/abs/2511.12960)) demonstrates that organising memories into cognitive types and retrieving per-type before merging outperforms both naive full-context approaches and complex architectures like knowledge graphs or multi-stage pipelines. The three types map to well-established categories from cognitive psychology:

- **Episodic**: "what happened" — time-bound events and incidents
- **Semantic**: "what is true" — facts, preferences, configurations
- **Procedural**: "how to do it" — workflows, recipes, deployment steps

### Why no embedded LLM?

Most memory systems embed an LLM client for extraction, classification, or summarisation. Engram deliberately avoids this:

- **Zero API keys required** — runs fully offline
- **No cost per operation** — no token usage for memory management
- **No latency** — no network round-trips for store/retrieve
- **Composable** — any agent (Claude Code, Cursor, custom scripts) can call the CLI
- **The agent already has an LLM** — it can classify memory types and assign importance before calling `engram add`

### Why FTS5 over embeddings?

Embeddings (dense retrieval) are the paper's recommended approach, but for v1 we chose FTS5 (sparse retrieval) as the default:

- **Zero heavy dependencies** — no torch, no sentence-transformers (~2GB), no numpy
- **Instant startup** — no model loading time
- **BM25 is strong** — for keyword-rich agent memories, BM25 often matches or exceeds embedding quality
- **Forward-compatible** — the schema includes a nullable `embedding BLOB` column for v2 hybrid retrieval

### Why SQLite?

- Part of Python's standard library — no database server to install or manage
- FTS5 is built into SQLite — full-text search with no external dependency
- WAL mode for concurrent reads
- ACID compliance — no data corruption from crashes
- Single file — easy to backup, move, or delete

## Module Structure

```
src/engram/
├── __init__.py      # Package version
├── models.py        # Data types (MemoryType, MemoryRecord, QueryResult)
├── db.py            # Storage layer (SQLite + FTS5)
├── retriever.py     # Query pipeline (per-type retrieval, scoring, routing)
└── cli.py           # CLI interface (click, JSON output)
```

### Dependency flow

```
cli.py ──> retriever.py ──> db.py ──> models.py
```

Each layer depends only on the layer below it. No circular dependencies.

### `models.py`

Pure data definitions. No I/O, no side effects.

- `MemoryType` enum: `EPISODIC`, `SEMANTIC`, `PROCEDURAL`
- `MemoryRecord` dataclass: the complete memory record with all fields
- `QueryResult` dataclass: a record paired with its retrieval score
- Both have `.to_dict()` methods for JSON serialisation (embeddings excluded)

### `db.py`

All SQLite interaction is isolated here. The `EngramDB` class manages:

- **Schema initialisation**: creates tables, FTS5 virtual table, and sync triggers on first use (idempotent)
- **CRUD**: `insert()`, `get()`, `list()`, `delete()`
- **Search**: `search()` runs FTS5 MATCH queries with project and type filtering
- **Access tracking**: `touch()` updates `accessed_at` and increments `access_count`
- **Statistics**: `stats()` returns counts grouped by memory type

The FTS5 index is kept in sync via SQLite triggers (INSERT, UPDATE, DELETE), so it never drifts from the base table.

### `retriever.py`

Implements the paper's retrieval algorithm:

1. **Router**: determines which memory types to query (keyword heuristic or explicit `--types`)
2. **Per-type retrieval**: queries each type independently via `db.search()`
3. **Scoring**: applies composite scoring to each result (relevance + recency + importance + access frequency)
4. **Merge**: unions all per-type results, deduplicating by ID
5. **Re-rank**: sorts by composite score, returns top-k
6. **Touch**: updates access metadata for returned results

### `cli.py`

Thin layer that wires click commands to `db` and `retriever`. All output is JSON to stdout. Errors and human-readable messages go to stderr.

## Database Schema

Single table with an FTS5 external content table:

```
memories (base table)
├── id: TEXT PRIMARY KEY (uuid4 hex)
├── project: TEXT (namespace)
├── type: TEXT (episodic|semantic|procedural)
├── title: TEXT (optional)
├── content: TEXT (memory body)
├── importance: REAL (0.0-1.0)
├── embedding: BLOB (nullable, reserved for v2)
├── created_at: TEXT (ISO 8601)
├── accessed_at: TEXT (ISO 8601, updated on retrieval)
└── access_count: INTEGER (incremented on retrieval)

memories_fts (FTS5 virtual table, auto-synced via triggers)
├── title
├── content
├── type
└── project
```

### Why one table, not three?

The paper implies separate stores per type, but a single table with a `type` column is simpler:

- One schema to manage, one migration path
- Cross-type deduplication is trivial
- The `type` column + composite index gives per-type query performance at no cost
- SQLite handles hundreds of thousands of rows without difficulty

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|---|---|---|
| `ENGRAM_PROJECT` | `"default"` | Default project namespace |
| `ENGRAM_DB` | `~/.local/share/engram/memories.db` | Database file path |

No config files, no YAML, no TOML. Environment variables are the simplest interface for both human users and agent integrations.

## Forward Compatibility

The v1 architecture is designed to accommodate v2 features without breaking changes:

- **JSONL backend**: the `EngramDB` interface can be implemented by a JSONL-backed class
- **Embeddings**: the `embedding` column exists; the retriever can blend FTS5 + cosine similarity via Reciprocal Rank Fusion
- **Router protocol**: `route()` can be replaced by a Protocol-based interface accepting pluggable implementations
- **Multi-agent**: the `project` namespace already isolates memories; ACL is an additive layer
- **MCP server**: the CLI commands map 1:1 to MCP tool definitions

See [SPEC.md](SPEC.md) for detailed v2 feature specifications.
