# Engram Feature Specifications

Future features for v2+. Each spec includes test steps and current implementation status.

## v2 Features

### Router Protocol (Pluggable Router Interface)

```json
{
  "category": "functional",
  "description": "Router as a Protocol interface so keyword heuristic can be swapped for LLM-based or embedding-based routing",
  "steps": [
    "Define a Router Protocol with a route(query: str) -> list[MemoryType] method",
    "Refactor existing keyword router to implement the Protocol",
    "Refactor retrieve() to accept an optional Router parameter",
    "Verify default keyword router behaviour is unchanged",
    "Create an LLM-based router that calls the agent's LLM to classify query types",
    "Verify LLM router returns correct type masks for ambiguous queries",
    "Verify retrieve() works with any Router implementation",
    "Verify backward compatibility: retrieve() without a router uses keyword fallback"
  ],
  "passes": false
}
```

### JSONL Backend

```json
{
  "category": "functional",
  "description": "File-based JSONL storage backend with native BM25 scoring, no SQLite dependency",
  "steps": [
    "Configure engram to use JSONL backend via ENGRAM_BACKEND=jsonl",
    "Store a memory using engram add",
    "Verify memory is written as a JSON line to the JSONL file",
    "Query memories using engram query",
    "Verify BM25 scoring produces ranked results without SQLite",
    "Verify all CLI commands work identically to SQLite backend",
    "Verify switching backends preserves existing data via export/import"
  ],
  "passes": false
}
```

### Dense Embeddings (Hybrid Retrieval)

```json
{
  "category": "functional",
  "description": "Optional sentence-transformers embeddings with hybrid RRF retrieval combining FTS5 and cosine similarity",
  "steps": [
    "Install engram with embeddings extra: pip install engram[embeddings]",
    "Enable embeddings via ENGRAM_EMBEDDINGS=true",
    "Store a memory and verify embedding BLOB is populated in the database",
    "Query memories and verify both FTS5 and cosine similarity are used",
    "Verify results are merged using Reciprocal Rank Fusion (RRF)",
    "Verify semantic queries find conceptually related memories even without keyword overlap",
    "Verify fallback to FTS5-only when embeddings extra is not installed"
  ],
  "passes": false
}
```

### Multi-Agent Namespacing

```json
{
  "category": "functional",
  "description": "Access control with read/write/admin permissions per agent per project",
  "steps": [
    "Register an agent with engram agent register <agent-id>",
    "Grant write permission to agent for a project",
    "Verify agent can store memories in the permitted project",
    "Verify agent cannot store memories in an unpermitted project",
    "Grant read-only permission to a second agent",
    "Verify second agent can query but not write",
    "Grant admin permission and verify agent can manage other agents' access",
    "Verify default behavior (no ACL) allows unrestricted access"
  ],
  "passes": false
}
```

### Memory Consolidation

```json
{
  "category": "functional",
  "description": "Merge near-duplicate memories and apply time-based decay to old ones",
  "steps": [
    "Store several memories with similar content",
    "Run engram consolidate --project test",
    "Verify near-duplicate memories are merged into a single record",
    "Verify merged record preserves the highest importance score",
    "Verify access_count is summed across merged records",
    "Store memories with old timestamps",
    "Run engram consolidate --decay",
    "Verify old, low-importance, rarely-accessed memories are archived or removed",
    "Verify pinned memories are exempt from decay"
  ],
  "passes": false
}
```

### MCP Server

```json
{
  "category": "functional",
  "description": "Model Context Protocol server for direct agent integration via stdio",
  "steps": [
    "Start MCP server with engram mcp",
    "Send an MCP tool call for engram_add via stdin",
    "Verify JSON response on stdout with memory ID",
    "Send an MCP tool call for engram_query",
    "Verify ranked results are returned",
    "Send engram_stats tool call",
    "Verify statistics are returned",
    "Verify MCP server handles malformed requests gracefully",
    "Configure Claude Code to use engram as an MCP server",
    "Verify agent can call engram tools through MCP protocol"
  ],
  "passes": false
}
```

### Import/Export

```json
{
  "category": "functional",
  "description": "Bulk JSONL import and database export for backup and migration",
  "steps": [
    "Store several memories across different projects",
    "Run engram export --output backup.jsonl",
    "Verify exported file contains all memories as JSON lines",
    "Delete the database",
    "Run engram import backup.jsonl",
    "Verify all memories are restored with original IDs and metadata",
    "Verify FTS5 index is rebuilt after import",
    "Verify export with --project flag exports only that project's memories"
  ],
  "passes": false
}
```

### Memory Update

```json
{
  "category": "functional",
  "description": "Update existing memory content while preserving metadata",
  "steps": [
    "Store a memory and note its ID",
    "Run engram update <id> --content 'Updated content'",
    "Verify content is changed",
    "Verify created_at is preserved",
    "Verify accessed_at is updated",
    "Verify FTS5 index reflects the new content",
    "Query for the updated content and verify it is found",
    "Query for the old content and verify it is not found"
  ],
  "passes": false
}
```

### Memory Pinning

```json
{
  "category": "functional",
  "description": "Pin important memories to prevent decay and prioritize retrieval",
  "steps": [
    "Store a memory and pin it with engram pin <id>",
    "Verify pinned flag is set",
    "Run consolidation with decay enabled",
    "Verify pinned memory is not affected by decay",
    "Verify pinned memories receive a retrieval boost in scoring",
    "Unpin the memory with engram unpin <id>",
    "Verify pinned flag is cleared"
  ],
  "passes": false
}
```
