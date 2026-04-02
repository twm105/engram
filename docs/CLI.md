# CLI Reference

Engram provides a command-line interface for storing and retrieving typed memories. All commands output JSON to stdout, making it easy for agents and scripts to parse results.

## Installation

```bash
uv sync        # install dependencies
uv run engram  # run via uv
```

Or install globally:

```bash
uv tool install .
engram --help
```

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `ENGRAM_PROJECT` | `"default"` | Default project namespace for all commands |
| `ENGRAM_DB` | `~/.local/share/engram/memories.db` | Path to the SQLite database file |

All commands accept `--project` to override `ENGRAM_PROJECT` for that invocation.

## Commands

### `engram add`

Store a new memory.

```
engram add <type> <content> [OPTIONS]
```

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `type` | yes | Memory type: `episodic`, `semantic`, or `procedural` |
| `content` | yes | The memory content (quote if it contains spaces) |

**Options:**

| Option | Default | Description |
|---|---|---|
| `--title TEXT` | none | Short label (recommended for episodic and procedural) |
| `--project TEXT` | `$ENGRAM_PROJECT` | Project namespace |
| `--importance FLOAT` | `0.5` | Importance score, 0.0-1.0. Use 0.8+ for critical items |

**Memory types:**

- `episodic` — Events, incidents, what happened and when
- `semantic` — Facts, preferences, knowledge, configurations
- `procedural` — Workflows, how-to steps, deployment procedures

**Examples:**

```bash
# Store a user preference
engram add semantic "User prefers dark mode and vim keybindings" --importance 0.8

# Record an incident
engram add episodic "Fixed pagination bug in API layer" --title "Pagination fix" --importance 0.7

# Save a workflow
engram add procedural "Run make deploy, wait for health check, verify in staging" --title "Deploy steps"

# Store in a specific project
engram add semantic "API uses GraphQL" --project myapp
```

**Output:**

```json
{
  "id": "a1b2c3d4e5f6...",
  "type": "semantic",
  "project": "default"
}
```

### `engram query`

Query memories by text using full-text search with composite scoring.

```
engram query <text> [OPTIONS]
```

Retrieves top-k candidates from each memory type independently, merges the results, and re-ranks by a composite score blending relevance, recency, importance, and access frequency.

**Arguments:**

| Argument | Required | Description |
|---|---|---|
| `text` | yes | The search query (quote if it contains spaces) |

**Options:**

| Option | Default | Description |
|---|---|---|
| `--project TEXT` | `$ENGRAM_PROJECT` | Project namespace |
| `--types TEXT` | auto-routed | Comma-separated memory types (e.g. `semantic,episodic`) |
| `--top-k INTEGER` | `10` | Maximum number of results to return |

If `--types` is not specified, a keyword-based router selects relevant types automatically. Pass `--types` explicitly for precise control.

**Examples:**

```bash
# General query (auto-routes to all types)
engram query "dark mode preferences"

# Query specific type
engram query "how to deploy" --types procedural

# Multiple types, limited results
engram query "deployment" --types episodic,procedural --top-k 5

# Scoped to a project
engram query "API configuration" --project myapp
```

**Output:**

```json
{
  "query": "dark mode preferences",
  "results": [
    {
      "id": "a1b2c3d4...",
      "project": "default",
      "type": "semantic",
      "title": null,
      "content": "User prefers dark mode and vim keybindings",
      "importance": 0.8,
      "created_at": "2026-04-01T12:00:00+00:00",
      "accessed_at": "2026-04-01T14:30:00+00:00",
      "access_count": 3,
      "score": 0.91
    }
  ]
}
```

### `engram list`

List stored memories, ordered by most recently created.

```
engram list [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--project TEXT` | `$ENGRAM_PROJECT` | Project namespace |
| `--type TYPE` | all | Filter: `episodic`, `semantic`, or `procedural` |
| `--limit INTEGER` | `50` | Maximum number of results |

**Examples:**

```bash
engram list
engram list --type semantic --limit 10
engram list --project myapp
```

**Output:**

```json
{
  "memories": [
    {
      "id": "a1b2c3d4...",
      "project": "default",
      "type": "semantic",
      "title": null,
      "content": "User prefers dark mode",
      "importance": 0.8,
      "created_at": "2026-04-01T12:00:00+00:00",
      "accessed_at": "2026-04-01T12:00:00+00:00",
      "access_count": 0
    }
  ]
}
```

### `engram get`

Get a specific memory by ID.

```
engram get <id>
```

Returns the full memory record as JSON. Exits with code 1 if the memory is not found.

**Example:**

```bash
engram get a1b2c3d4e5f6...
```

**Output:**

```json
{
  "id": "a1b2c3d4e5f6...",
  "project": "default",
  "type": "semantic",
  "title": null,
  "content": "User prefers dark mode",
  "importance": 0.8,
  "created_at": "2026-04-01T12:00:00+00:00",
  "accessed_at": "2026-04-01T12:00:00+00:00",
  "access_count": 0
}
```

### `engram delete`

Delete a memory by ID.

```
engram delete <id>
```

**Example:**

```bash
engram delete a1b2c3d4e5f6...
```

**Output:**

```json
{
  "deleted": true,
  "id": "a1b2c3d4e5f6..."
}
```

Returns `"deleted": false` if the ID was not found.

### `engram stats`

Show memory statistics for a project.

```
engram stats [OPTIONS]
```

**Options:**

| Option | Default | Description |
|---|---|---|
| `--project TEXT` | `$ENGRAM_PROJECT` | Project namespace |

**Example:**

```bash
engram stats --project myapp
```

**Output:**

```json
{
  "total": 42,
  "by_type": {
    "semantic": 25,
    "episodic": 12,
    "procedural": 5
  }
}
```

## Importance Guidelines

When storing memories, the `--importance` flag tells engram how critical this memory is. It affects retrieval ranking:

| Range | Use for | Examples |
|---|---|---|
| `0.8 - 1.0` | Critical preferences, blocking bugs, architecture decisions | "Never use ORM for bulk inserts" |
| `0.5 - 0.7` | Useful context, patterns, conventions | "Team uses conventional commits" |
| `0.2 - 0.4` | Minor details, one-off observations | "Considered using Redis but decided against it" |

## Agent Integration

Engram is designed to be called by AI agents as a tool. The JSON output is machine-parseable, and the CLI can be invoked from any agent that can run shell commands.

**Typical agent workflow:**

```bash
# Before starting a task, retrieve context
engram query "relevant topic" --project $PROJECT --top-k 5

# After learning something, store it
engram add semantic "discovered fact" --project $PROJECT --importance 0.7

# After completing a task, record it
engram add episodic "completed the migration" --title "DB migration" --project $PROJECT
```

See `skills/memory/SKILL.md` for a ready-made Claude Code skill definition.
