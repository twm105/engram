# Algorithms

This document explains the retrieval algorithms used in engram, how they work, and why. The design is based on the ENGRAM paper by Patel & Patel (2025): [arxiv:2511.12960](https://arxiv.org/abs/2511.12960).

## The Core Idea

The ENGRAM paper's central finding is that **typed memory + simple retrieval beats complex architectures**. Instead of building elaborate knowledge graphs, multi-stage pipelines, or OS-style memory schedulers, you get better results by:

1. Organising memories into cognitive types (episodic, semantic, procedural)
2. Retrieving the best matches from each type independently
3. Merging and re-ranking the results

This approach achieved +15 points over full-context baselines on the LongMemEval benchmark while using only ~1% of the tokens. The key insight: structured organisation of memories matters more than sophisticated retrieval mechanisms.

## Memory Types

The three types come from cognitive psychology:

| Type | What it stores | Real-world analogy |
|---|---|---|
| **Episodic** | Events — what happened, when, in what context | "I remember the deploy failing last Tuesday" |
| **Semantic** | Facts — knowledge, preferences, configurations | "The API uses port 8080" |
| **Procedural** | How-to — workflows, steps, recipes | "To deploy: run make deploy, then check /health" |

The distinction matters for retrieval: when someone asks "how do I deploy?", procedural memories should surface even if episodic memories about past deploys score higher on raw keyword matching.

## Algorithm 1: Per-Type Retrieval, Merge, and Re-Rank

This is the paper's core retrieval algorithm. In plain English:

1. Figure out which memory types are relevant to the query
2. Search each type separately and get the best matches from each
3. Combine all the results into one pool, removing duplicates
4. Score each result and sort by score
5. Return the top results

### Why per-type instead of a single query?

Consider the query "deploy config" against a database with 10 semantic memories about config settings, 1 episodic memory about a deploy failure, and 1 procedural memory about deploy steps. A single FTS5 query across all types returns results ranked purely by text relevance — the 10 semantic memories dominate because they all contain "config", pushing the episodic and procedural memories out of the top-k.

Per-type retrieval gets the best results **from each type first**, then merges. This guarantees type diversity in the final results, which is exactly what the paper shows leads to better downstream performance.

### Formal description

Given:
- Query text `q`
- Set of memory types `T = {t₁, t₂, ..., tₙ}` (determined by the router)
- Per-type result limit `k`

```
For each type tᵢ ∈ T:
    Rᵢ = FTS5_SEARCH(q, type=tᵢ, limit=k)        # top-k from this type
    Sᵢ = {SCORE(r) for r in Rᵢ}                    # score each result

Merged = ⋃ᵢ Sᵢ                                     # union, deduplicate by ID
Ranked = SORT(Merged, by=score, descending)          # re-rank merged pool
Result = Ranked[:k]                                  # final top-k
```

### Implementation

```python
for mem_type in types:
    type_records = db.search(query, project, types=[mem_type], limit=top_k)
    type_scored = score_records(type_records)
    for result in type_scored:
        merged[result.id] = max(merged.get(result.id), result, key=score)

results = sorted(merged.values(), by=score, reverse=True)[:top_k]
```

See `src/engram/retriever.py:retrieve()`.

## Algorithm 2: BM25 Full-Text Search (FTS5)

Engram v1 uses SQLite's FTS5 engine for text matching. FTS5 implements the BM25 ranking function, which is the standard algorithm for information retrieval.

### Plain English

BM25 answers the question: "how relevant is this document to this query?" It considers:

- **Term frequency**: how many times the query words appear in the document (more = more relevant, but with diminishing returns)
- **Inverse document frequency**: how rare the query words are across all documents (rarer words are more informative — "pagination" is more useful than "the")
- **Document length**: longer documents get a slight penalty (a word appearing in a 10-word memory is more significant than in a 500-word one)

### Mathematical formulation

For a query `Q` with terms `q₁, q₂, ..., qₙ` and a document `D`:

```
BM25(D, Q) = Σᵢ IDF(qᵢ) × (f(qᵢ, D) × (k₁ + 1)) / (f(qᵢ, D) + k₁ × (1 - b + b × |D| / avgdl))
```

Where:
- `f(qᵢ, D)` = frequency of term `qᵢ` in document `D`
- `|D|` = length of document `D` (in tokens)
- `avgdl` = average document length across all documents
- `k₁ = 1.2` = term frequency saturation parameter (controls diminishing returns)
- `b = 0.75` = length normalisation parameter
- `IDF(qᵢ) = log((N - n(qᵢ) + 0.5) / (n(qᵢ) + 0.5) + 1)` where `N` is total documents and `n(qᵢ)` is documents containing `qᵢ`

FTS5 handles all of this internally. Engram calls it via:

```sql
SELECT m.*, fts.rank
FROM memories_fts fts
JOIN memories m ON m.rowid = fts.rowid
WHERE memories_fts MATCH ?
ORDER BY fts.rank
LIMIT ?
```

FTS5 returns `rank` as a negative number (more negative = better match). Engram normalises these to 0-1 for composite scoring.

### FTS5 rank normalisation

Since FTS5 returns results already sorted by relevance, we use positional normalisation:

```
normalised_rank(i) = 1 - (i / n)    where n = total results, i = 0-indexed position
```

The best match gets 1.0, the worst gets 0.0 (or close to it). This is a simple linear interpolation that preserves the relative ordering from BM25 while mapping to a consistent scale for composite scoring.

## Algorithm 3: Composite Scoring

After FTS5 provides relevance ranking, engram applies a composite score that blends multiple signals. This is where engram goes beyond the paper's pure cosine similarity approach — since we don't have a downstream LLM re-ranker, the composite score acts as a lightweight re-ranking layer.

### Plain English

The composite score answers: "given that this memory is somewhat relevant to the query, how useful is it likely to be right now?" It considers four things:

1. **Relevance** (60%): How well does the text match the query? This is the FTS5/BM25 signal.
2. **Importance** (20%): How important did the caller say this memory is? Critical facts score higher.
3. **Recency** (15%): How recently was this memory accessed? Recently-useful memories are likely still useful.
4. **Frequency** (5%): How often has this memory been retrieved? Frequently-retrieved memories are probably valuable.

### Mathematical formulation

```
score = 0.60 × relevance + 0.15 × recency + 0.20 × importance + 0.05 × frequency
```

Where:

- `relevance` = normalised FTS5 rank ∈ [0, 1]
- `recency = e^(-h / 720)` where `h` = hours since last access
  - This is an exponential decay with a half-life of ~30 days
  - A memory accessed 1 hour ago: recency ≈ 1.0
  - A memory accessed 30 days ago: recency ≈ 0.37
  - A memory accessed 90 days ago: recency ≈ 0.05
- `importance` = caller-assigned value ∈ [0, 1]
- `frequency = min(access_count / 10, 1.0)` — capped at 1.0 to prevent runaway scores

### Why these weights?

The weights are chosen so that **relevance always dominates**. A memory that perfectly matches the query text (relevance = 1.0) contributes 0.60 to the score. All other signals combined can contribute at most 0.40. This means:

- A highly relevant but old, low-importance memory still scores well
- A barely relevant but recent, high-importance memory won't outrank a good text match
- The non-relevance signals act as **tiebreakers** when multiple memories have similar text relevance

This aligns with the paper's finding that retrieval quality is the primary driver of performance.

### Recency decay explained

The recency signal uses exponential decay:

```
recency(h) = e^(-h / 720)
```

Why 720 hours (~30 days)?

- Agent memories tend to be useful for weeks, not minutes
- A 30-day half-life means memories are still useful a month later but naturally fade
- This matches the paper's observation that "recently accessed" is a better signal than "recently created" — which is why engram tracks `accessed_at` rather than using `created_at` for recency

The `accessed_at` timestamp updates every time a memory is returned as a query result. This means frequently-retrieved memories stay "fresh" — a form of reinforcement learning through use.

## Algorithm 4: Query Routing

The router determines which memory types to query for a given input. The paper uses an LLM-based router that produces a 3-bit type mask. Engram v1 uses a keyword heuristic as a lightweight fallback.

### Plain English

The router looks at the query text and guesses which types of memory would be useful:

- "How to deploy" → procedural (it's asking for steps)
- "When did we fix the bug" → episodic (it's asking about a past event)
- "What is the API endpoint" → semantic (it's asking for a fact)
- "Tell me about the project" → all types (ambiguous)

### Implementation

```python
def route(query):
    if contains_any(query, ["how to", "steps", "workflow", "procedure"]):
        return [PROCEDURAL]
    if contains_any(query, ["when did", "last time", "what happened"]):
        return [EPISODIC]
    if contains_any(query, ["what is", "who is", "preference", "prefers"]):
        return [SEMANTIC]
    return [EPISODIC, SEMANTIC, PROCEDURAL]  # default: query all
```

### Why this is intentionally naive

The keyword router is a convenience fallback. The primary usage path is agents passing `--types` explicitly:

```bash
engram query "deploy procedure" --types procedural
```

The calling agent has its own LLM and can classify queries more accurately than keyword matching. In v2, the router will be a pluggable Protocol interface, allowing LLM-based routing as an upgrade path (see [SPEC.md](SPEC.md)).

## Future: Hybrid Retrieval with Reciprocal Rank Fusion

The paper's recommended approach uses dense embeddings (cosine similarity) rather than sparse retrieval (BM25). In v2, engram will support both, merged via Reciprocal Rank Fusion (RRF).

### Plain English

Run two searches in parallel — one keyword-based (FTS5), one meaning-based (embeddings). Combine the results by giving each document a score based on its rank in each list, not its raw score. This way, a document that ranks #1 in keyword search and #5 in semantic search gets a high combined score even though its raw scores are on different scales.

### Mathematical formulation

```
RRF(d) = Σᵢ 1 / (k + rankᵢ(d))
```

Where:
- `d` = a document (memory)
- `rankᵢ(d)` = rank of `d` in the i-th retrieval method (FTS5 or embeddings)
- `k = 60` = smoothing constant (standard value from the RRF paper)

If a memory doesn't appear in one of the rankings, it simply doesn't contribute a term for that ranker. This naturally handles the case where keyword search finds matches that semantic search misses, and vice versa.

This is not yet implemented — see [SPEC.md](SPEC.md) for the specification.
