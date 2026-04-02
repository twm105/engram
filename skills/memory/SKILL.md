---
name: memory
description: Store and retrieve memories using engram. Use when you learn something worth remembering across sessions, or before starting a task to check for relevant context.
argument-hint: query or memory content
---

Use the `engram` CLI to store and retrieve memories for this project.

## When to Store Memories

Store memories when you learn something that would be useful in future conversations:

- **semantic** — Facts, preferences, knowledge ("User prefers dark mode", "API uses GraphQL")
- **episodic** — Events, incidents, what happened ("Fixed pagination bug on 2026-04-01")
- **procedural** — How-to knowledge, workflows ("Deploy: run make deploy, then check /health")

## Storing

```bash
engram add <type> "<content>" [--title "<label>"] [--project <name>] [--importance <0.0-1.0>]
```

Importance guidelines:

- `0.8-1.0` — Critical preferences, blocking bugs, architecture decisions
- `0.5-0.7` — Useful context, patterns, conventions
- `0.2-0.4` — Minor details, one-off observations

## Retrieving

Before starting a task, check for relevant context:

```bash
engram query "<question>" [--project <name>] [--types <type,type>] [--top-k <n>]
```

Use `--types` to narrow: `--types semantic` for facts, `--types episodic` for history, `--types procedural` for how-tos.

## Browsing and Managing

```bash
engram list [--project <name>] [--type <type>] [--limit <n>]
engram get <id>
engram delete <id>
engram stats [--project <name>]
```

## Environment

- Set `ENGRAM_PROJECT` to scope memories to the current project
- Set `ENGRAM_DB` to customize database location (default: `~/.local/share/engram/memories.db`)

## Output

All commands output JSON to stdout. Parse the results and incorporate relevant memories into your reasoning.
