# Engram

A lightweight memory system for AI agents. Store what matters, retrieve what's relevant, build knowledge and taste over time.

Engram gives any conversational agent — Claude Code, Cursor, custom scripts — persistent typed memory backed by full-text search. No API keys, no embedding models, no heavyweight dependencies. Just `pip install` and go.

Based on the ENGRAM paper by Patel & Patel (2025): [arxiv:2511.12960](https://arxiv.org/abs/2511.12960).

## Why agents need memory

Without memory, every conversation starts from zero. Agents re-discover the same facts, repeat the same mistakes, and can't build on prior work. Engram fixes this by giving agents a structured way to accumulate knowledge across sessions:

- **Preferences stick** — "user prefers dark mode" is remembered, not re-asked
- **Incidents leave traces** — "the deploy broke last Tuesday because of X" is retrievable next time deploys come up
- **Procedures are learned** — "to deploy: run make deploy, check /health, verify staging" doesn't need to be re-explained

Over time, an agent with memory develops something like taste — it knows what worked, what didn't, and what matters to you.

## How it works

Engram organises memories into three cognitive types from the paper:

| Type | Stores | Example |
|---|---|---|
| **Episodic** | Events — what happened | "Deploy failed due to missing env var" |
| **Semantic** | Facts — what is true | "API uses port 8080, prefers snake_case" |
| **Procedural** | How-to — workflows and steps | "To deploy: make deploy, then check /health" |

When queried, engram retrieves the best matches from each type independently, then merges and re-ranks using a composite score that blends:

- **Relevance** (60%) — BM25 full-text match via SQLite FTS5
- **Importance** (20%) — caller-assigned priority
- **Recency** (15%) — exponential decay from last access
- **Frequency** (5%) — how often a memory has been retrieved

This per-type-then-merge approach is the paper's key finding: it outperformed full-context baselines by +15 points on the LongMemEval benchmark while using ~1% of the tokens. Structured organisation beats sophisticated retrieval mechanisms.

## Quick start

```bash
pip install engram
# or
uv tool install engram
```

Store some memories:

```bash
engram add semantic "User prefers dark mode and vim keybindings" --importance 0.8
engram add episodic "Fixed pagination bug in API layer" --title "Pagination fix"
engram add procedural "Run make deploy, wait for health check, verify staging" --title "Deploy steps"
```

Query them:

```bash
engram query "dark mode preferences"
engram query "how to deploy" --types procedural
engram query "what went wrong with pagination" --types episodic --top-k 5
```

All output is JSON to stdout, designed for machine consumption. Human messages go to stderr.

## Agent integration

Engram is designed to be called by agents as a CLI tool. The typical workflow:

```bash
# Before starting a task — retrieve context
engram query "relevant topic" --project myapp --top-k 5

# After learning something — store it
engram add semantic "discovered fact" --project myapp --importance 0.7

# After completing a task — record it
engram add episodic "completed the migration" --title "DB migration" --project myapp
```

A ready-made Claude Code skill definition is included in [`skills/memory/SKILL.md`](skills/memory/SKILL.md). Set `ENGRAM_PROJECT` to scope memories to a specific project.

## Design principles

- **Pure storage-and-retrieval** — zero LLM or ML dependency. The calling agent does classification and extraction; engram does the remembering.
- **Minimal footprint** — only runtime dependency is `click`. SQLite and FTS5 are stdlib.
- **Composable CLI** — JSON output, environment variable config, no interactive prompts. Works with any agent that can shell out.
- **All deps permissively licensed** — MIT, BSD, Apache 2.0 only.

## Roadmap

Engram v1 is a deliberate starting point — FTS5 sparse retrieval with no heavy dependencies. The architecture is designed for these extensions, each specified in detail in [`docs/SPEC.md`](docs/SPEC.md):

- **Dense embeddings with hybrid retrieval** — optional sentence-transformers integration (`pip install engram[embeddings]`). Combines FTS5 keyword search with cosine similarity via Reciprocal Rank Fusion, catching conceptual matches that keyword search misses.
- **JSONL backend** — a lightweight file-based alternative to SQLite (`ENGRAM_BACKEND=jsonl`). Plain text storage means better version control diffs, simpler backup, and zero binary dependencies.
- **Full skill implementation** — MCP server for direct agent integration via stdio, plus import/export, memory update, pinning, and consolidation. Moving from "CLI tool agents can call" to "native capability agents can use."

## Documentation

| Doc | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Module structure, schema design, design rationale |
| [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) | Retrieval pipeline, BM25, composite scoring, query routing |
| [`docs/CLI.md`](docs/CLI.md) | Complete command reference with examples |
| [`docs/SPEC.md`](docs/SPEC.md) | v2+ feature specifications |
| [`docs/TESTING.md`](docs/TESTING.md) | TDD methodology, running tests, fixtures |

## License

MIT
