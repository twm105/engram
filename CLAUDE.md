# Engram

A lightweight memory system for conversational agents, inspired by the ENGRAM paper (arxiv 2511.12960).

## Core Principles

- **Pure storage-and-retrieval engine** — zero LLM or ML dependency. The calling agent does classification and extraction; engram does the remembering.
- **FTS5 sparse retrieval by default** — zero heavy deps, instant startup. No embedding model required.
- **Forward-compatible** — schema and architecture support future dense retrieval, multi-agent, JSONL backend without breaking changes.
- **Composable CLI** — JSON output to stdout, human text to stderr. Designed to be called by agents as a skill/tool.

## Development Approach

- **Test-driven development (TDD)** — write tests first, then implement until tests pass. Full unit test coverage for all modules.
- **All dependencies must be permissively licensed** (MIT, BSD, Apache 2.0). No copyleft.
- **Minimal dependencies** — only `click` (BSD-3) as a runtime dep. SQLite + FTS5 are stdlib.

## Project Layout

```
src/engram/
  models.py      # dataclasses, MemoryType enum
  db.py          # SQLite + FTS5 schema, CRUD
  retriever.py   # query pipeline, scoring, router
  cli.py         # click CLI, JSON output
tests/
  conftest.py    # shared fixtures
  test_*.py      # one test file per module
docs/            # MUST READ — see Documentation section below
skills/          # agent skill definitions
```

## Environment Variables

- `ENGRAM_PROJECT` — default project namespace (fallback: "default")
- `ENGRAM_DB` — database path (fallback: `~/.local/share/engram/memories.db`)

## Documentation — MANDATORY READING RULES

All detailed documentation lives in `docs/`. These are authoritative references — **you MUST read the relevant doc before making changes in that area**. Do not rely on memory or assumptions.

### `docs/ARCHITECTURE.md` — Read BEFORE any structural change

Contains: module responsibilities, dependency flow between modules, database schema (table definitions, FTS5 triggers, indexes), design rationale for every major decision (why one table not three, why FTS5 not embeddings, why no embedded LLM, why SQLite, why env vars not config files), and forward compatibility design.

**Read this when:** adding a new module, changing module boundaries, modifying the database schema, adding a dependency, or making any architectural decision. Also read before proposing alternatives to existing patterns — the rationale explains why the current approach was chosen.

### `docs/ALGORITHMS.md` — Read BEFORE changing retrieval or scoring

Contains: the four core algorithms with both plain English explanations and mathematical formulas — (1) per-type retrieval, merge, and re-rank pipeline, (2) BM25/FTS5 full-text search and rank normalisation, (3) composite scoring formula with exact weights and decay functions, (4) query routing logic. References the arxiv paper. Also documents the future hybrid RRF algorithm for v2 embeddings.

**Read this when:** modifying `retriever.py`, changing scoring weights, adjusting the ranking algorithm, adding a new retrieval signal, changing the router, or discussing algorithm behaviour. The exact formulas and weight rationale are here — do not guess them.

### `docs/CLI.md` — Read BEFORE changing any CLI command

Contains: complete reference for every command (`add`, `query`, `list`, `get`, `delete`, `stats`) with exact arguments, options, defaults, example invocations, and example JSON output. Also documents importance guidelines and agent integration patterns.

**Read this when:** adding or modifying CLI commands, changing option names or defaults, changing output format, or writing examples. CLI help text (in `cli.py`) and this doc MUST stay consistent — update both together.

### `docs/TESTING.md` — Read BEFORE writing or modifying tests

Contains: TDD methodology, how to run tests (full suite, single module, single test), test file structure, fixture descriptions (`tmp_db_path`, `clean_env`), categorisation of tests (unit vs integration vs e2e), and test isolation guarantees.

**Read this when:** adding new tests, creating new fixtures, debugging test failures, or changing test infrastructure.

### `docs/SPEC.md` — Read BEFORE implementing any new feature

Contains: v2+ feature specifications in structured JSON format with test steps and pass/fail status. Covers: pluggable router protocol, JSONL backend, dense embeddings with RRF, multi-agent namespacing, memory consolidation, MCP server, import/export, memory update, memory pinning.

**Read this when:** planning new features, to check if a feature is already specified, or to understand the intended design for v2 capabilities. New features MUST have a spec entry added here before implementation begins.
