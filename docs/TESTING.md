# Testing Strategy

## Approach

Engram uses **test-driven development (TDD)**. For every module, tests are written first, then the implementation is built until all tests pass. This ensures full coverage and that the public API is designed from the consumer's perspective.

## Running Tests

```bash
# Full suite
uv run pytest tests/ -v

# Single module
uv run pytest tests/test_db.py -v

# Single test class
uv run pytest tests/test_retriever.py::TestPerTypeRetrieval -v

# Single test
uv run pytest tests/test_cli.py::TestQuery::test_query_finds_match -v
```

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_models.py       # Data model tests
├── test_db.py           # Storage layer tests
├── test_retriever.py    # Retrieval algorithm tests
└── test_cli.py          # CLI integration tests
```

### `conftest.py` — Shared Fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `tmp_db_path` | function | Provides a fresh temporary database path per test |
| `clean_env` | function (autouse) | Clears `ENGRAM_DB` and `ENGRAM_PROJECT` env vars between tests |

All tests use isolated temporary databases. No test depends on or modifies shared state.

### `test_models.py` — Unit Tests

Tests for pure data types with no I/O:

- `MemoryType` enum values and string construction
- `MemoryRecord` creation with defaults and explicit values
- `to_dict()` serialisation (JSON-compatible, excludes embeddings)
- `QueryResult` score pairing

### `test_db.py` — Storage Layer Tests

Tests for SQLite + FTS5 operations against a real database:

- **Schema**: table creation, idempotent re-initialisation
- **Insert**: returns uuid, stores all fields, default importance
- **Get**: existing record, nonexistent returns None
- **List**: project filtering, type filtering, limit, ordering (newest first)
- **Delete**: existing (returns True), nonexistent (returns False)
- **Touch**: increments access_count, updates accessed_at
- **Stats**: counts by type, empty project
- **FTS Search**: keyword matching, project isolation, type filtering, ranking, limit, FTS sync on delete

### `test_retriever.py` — Algorithm Tests

Tests for the retrieval pipeline:

- **Router**: keyword detection for each type, case insensitivity, default-to-all fallback
- **Composite score**: weight verification, recency decay, importance effect, access count cap
- **Retrieve (basic)**: finds relevant results, respects type filter, respects top-k, sorted by score, touches results, empty results
- **Per-type retrieval**: type-balanced results (the key paper algorithm), per-type limits, deduplication across types, single-type correctness, graceful handling of empty types

### `test_cli.py` — Integration Tests

End-to-end tests via Click's `CliRunner`:

- **Add**: all three types, with title, with importance, project override, invalid type rejection
- **Query**: finds matches, no results, type filtering, top-k limit
- **List**: all memories, type filter, limit, empty project
- **Get**: existing (full JSON), nonexistent (exit code 1)
- **Delete**: existing (deleted: true), nonexistent (deleted: false)
- **Stats**: populated project, empty project

All CLI tests verify JSON output is parseable and contains expected fields.

## Test Categories

### Unit Tests

- `test_models.py` — pure logic, no I/O
- `TestCompositeScore` in `test_retriever.py` — pure math
- `TestRoute` in `test_retriever.py` — pure string matching

### Integration Tests

- `test_db.py` — tests against real SQLite databases
- `TestRetrieve` and `TestPerTypeRetrieval` in `test_retriever.py` — db + retriever together
- `test_cli.py` — full CLI stack via CliRunner

### End-to-End Tests (Manual)

Run against the installed CLI:

```bash
# Store
ENGRAM_DB=/tmp/test.db engram add semantic "User prefers dark mode" --importance 0.8

# Retrieve
ENGRAM_DB=/tmp/test.db engram query "dark mode"

# List
ENGRAM_DB=/tmp/test.db engram list

# Stats
ENGRAM_DB=/tmp/test.db engram stats

# Cleanup
rm /tmp/test.db
```

## Test Isolation

Every test gets its own temporary database via the `tmp_db_path` fixture. The `clean_env` autouse fixture ensures no environment variables leak between tests. Tests do not depend on execution order.

## Dependencies

Testing requires only `pytest>=7.0` (MIT license), installed via `uv sync --extra dev`. Click's built-in `CliRunner` is used for CLI tests — no additional test dependencies.
