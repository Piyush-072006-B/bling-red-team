# BLING Red Team API

> **Adversarial simulation engine for BLING forensic fraud detection.**
> Red Team output is **developer intelligence only** — never a blocking signal.

---

## Status / Badges

![Tests](https://img.shields.io/badge/tests-155%2F155-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688)
![Port](https://img.shields.io/badge/port-8002-lightgrey)
![Status](https://img.shields.io/badge/status-Prototype-orange)

| Metric | Value |
|---|---|
| Test suite | ✅ 155 / 155 passing |
| Python version | 3.11 |
| Framework | FastAPI (async) |
| Default port | `8002` |
| Maturity | Prototype / Hackathon |

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Dataset Integration](#dataset-integration)
4. [16 Archetypes](#16-archetypes)
5. [Confirmed Findings](#confirmed-findings)
6. [TGEP Graph Design](#tgep-graph-design)
7. [API Reference](#api-reference)
8. [Quickstart](#quickstart)
9. [Environment Variables](#environment-variables)
10. [Testing](#testing)
11. [Known Limitations](#known-limitations)
12. [Security](#security)

---

## Overview

The **BLING Red Team service** is an adversarial simulation engine that operates alongside the Blue Team forensic fraud-detection pipeline. It ingests confirmed-fraud signals from the Blue Team (FraudDNA, Novelty escalations, Gate misses) and automatically:

- Classifies each signal against **16 BAF-derived fraud archetypes** using cosine similarity.
- Generates **22 targeted mutations** per signal to probe Blue Team detection gaps.
- Runs **5 graph-adversary bypass checks** against Blue Team graph gates.
- Packages each finding into a structured **attack package** (evasion vector + TGEP graph + bypass strategy).
- Maintains a **knowledge-base feedback loop** where historical evasion success rates update future mutation weights.

> [!IMPORTANT]
> Red Team findings are **developer intelligence only**. They inform improvements to the Blue Team and TGEP detectors. They must **never** be wired into automated transaction blocking or customer-facing decisions.

---

## Architecture

### High-Level Pipeline

```
Blue Team Signal
       │
       ▼
POST /red-team/ingest
       │
       ▼
AsyncIO Priority Queue
  CRITICAL > HIGH > MEDIUM > LOW
       │
       ▼
┌──────────────────────┐
│  Pre-flight Tier Check│
│  Tier 1: fast rules  │
│  Tier 2: graph gates │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Archetype Extractor │
│  Cosine similarity   │
│  16 BAF signatures   │
│  → archetype or      │
│    NEW_VARIANT       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│  Mutation Engine  (22 mutations per signal)       │
│                                                  │
│  10 × Single-feature mutations                   │
│     threshold, timing, velocity,                 │
│     context, novelty                             │
│                                                  │
│   6 × Compound mutations                         │
│     daytime_slowdown, structuring_ghost,         │
│     festival_layering, mule_warmup,              │
│     kyc_ghost, senior_festival_night             │
│                                                  │
│   6 × Tier-aware mutations                       │
│     compound_full_bypass, tier1_safe,            │
│     context_stack, gate_defeat_cycle,            │
│     gate_defeat_sink, gate_defeat_bipartite      │
└──────────┬───────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Graph Adversary     │
│  5 gate bypass checks│
│  cycle / sink /      │
│  bipartite /         │
│  cash_mule /         │
│  merchant            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Attack Package      │
│  Builder             │
│  per-evasion TGEP    │
│  graph + bypass      │
│  strategy + JSON     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  KB Feedback Loop    │
│  mutation weights ←  │
│  evasion_success     │
│  history             │
└──────────────────────┘
           │
           ▼
GET /red-team/attack-graph/{id}
  202 → processing (evasions_so_far < 22)
  200 → complete   (all 22 done)
```

### Component Summary

| Component | Responsibility |
|---|---|
| **Ingest endpoint** | Validates and enqueues Blue Team signals with priority |
| **Priority queue worker** | Async background processor, respects CRITICAL > HIGH > MEDIUM > LOW ordering |
| **Pre-flight tier check** | Tier 1 fast-rule gate; Tier 2 graph-gate risk assessment before full mutation |
| **Archetype extractor** | Cosine-similarity classifier against 16 BAF seed vectors (59 features) |
| **Mutation engine** | Generates 22 targeted evasion mutations per signal |
| **Graph adversary** | Tests 5 Blue Team graph gates for structural bypass opportunities |
| **Attack package builder** | Assembles TGEP-compatible graph, bypass strategy, and JSON export per evasion |
| **KB feedback loop** | Updates mutation weights from historical evasion success rates |
| **Self-generation loop** | Injects 3 random archetype signals every 5 minutes (configurable) |

---

## Dataset Integration

### BAF NeurIPS 2022

The archetype seeds are derived from the **BAF (Bank Account Fraud) dataset** — NeurIPS 2022 — using `Base.csv` (1 million real-world fraud transactions).

Each of the 16 archetypes was produced by clustering fraud records along 59 behavioural features and computing centroid vectors. These seed vectors drive cosine-similarity classification at runtime.

### Seed Storage

| File | Purpose |
|---|---|
| `data/computed_archetype_seeds.json` | Raw BAF-derived 59-feature vectors for all 16 archetypes |
| `app/engines/seed_library.py` | Runtime seed access: `get_seed()`, `get_all_seeds()`, `get_seed_with_variation(±10%)` |

### Self-Generation Loop

Every **5 minutes**, the worker automatically selects 3 random archetypes and injects synthetic `FraudDNA` signals derived from their seed vectors. This keeps the knowledge base active even without live Blue Team traffic.

Controlled via `SELF_GENERATION_ENABLED` environment variable (default: `true`).

### Bulk Load

To immediately inject all 16 archetype seeds as synthetic signals:

```bash
python scripts/bulk_load_seeds.py
```

Or enable `BULK_LOAD_ON_STARTUP=true` to run this automatically at service startup.

---

## 16 Archetypes

All archetypes are derived from BAF NeurIPS 2022 and encoded as 59-feature cosine-similarity seed vectors.

| # | Name | TGEP Graph Pattern | Key Features |
|---|---|---|---|
| 1 | `digital_arrest` | 3→1→2 sink | `night_txn_ratio`, `hour_deviation` |
| 2 | `structuring` | 3→1→2 sink | `amount_vs_threshold_50000`, `txn_count_30d` |
| 3 | `rapid_layering` | 3→1→2 sink | `velocity_ratio`, `channel_entropy` |
| 4 | `bipartite_mule` | 3→1→2 sink | `bipartite_score`, `distinct_payees_24h` |
| 5 | `cycle_round_trip` | 3→1→2 sink | `cycle_membership`, `return_ratio` |
| 6 | `cash_in_mule` | 3→1→2 sink | `cash_mule_sink_score`, `fan_out_ratio` |
| 7 | `salary_mule` | 3→1→2 sink | `dormancy_break`, `account_age_days` |
| 8 | `low_slow_mule` | 3→1→2 sink | `temporal_acceleration`, `txn_count_30d` |
| 9 | `romance_scam` | 3→1→2 sink | `counterparty_novelty`, `pagerank_fraud_seeded` |
| 10 | `pig_butchering` | 3→1→2 sink | `community_fraud_ratio`, `burst_score` |
| 11 | `investment_fraud` | 3→1→2 sink | `velocity_ratio`, `amount_zscore` |
| 12 | `account_takeover` | 3→1→2 sink | `channel_switch`, `geography_switch` |
| 13 | `otp_fraud` | 3→1→2 sink | `velocity_ratio`, `burst_score` |
| 14 | `sim_swap` | 3→1→2 sink | `night_txn_ratio`, `is_night` |
| 15 | `ghost_node_cash` | 3→1→2 sink | `sink_score`, `fan_out_ratio` |
| 16 | `merchant_terminal` | 3→1→2 sink | `channel_entropy`, `txn_count_last_1h` |

Signals that do not match any archetype above the cosine threshold are classified as **`NEW_VARIANT`** and forwarded for manual triage.

---

## Confirmed Findings

Three Red Team findings have been confirmed and disclosed to the Blue Team. All are intelligence-grade — no automated action has been taken.

---

### 🔴 Finding 1 — CRITICAL

**Archetype:** `cycle_round_trip`
**Evasion ID:** `graph_bypass_nine_hop_linear`

| Field | Detail |
|---|---|
| Gate bypassed | `cycle` |
| Mechanism | 9-hop linear chain exceeds 8-hop detector range |
| TGEP pattern detected | `circular_laundering` |
| Recommended patch | Extend cycle gate from **8 hops → 10 hops** |

**Description:** The Blue Team cycle gate uses a maximum path length of 8 hops. A 9-hop linear chain that doubles back terminates just outside the detector window, evading the `circular_laundering` TGEP flag entirely. The mutation engine discovered this bound via systematic `gate_defeat_cycle` mutations.

---

### 🟠 Finding 2 — HIGH

**Archetype:** `digital_arrest`
**Evasion ID:** `timing_day`

| Field | Detail |
|---|---|
| Gate bypassed | `context_senior_night` |
| Mechanism | 1.50× night multiplier not applied when transactions are spread across daytime hours |
| TGEP pattern detected | `layering_chain` |
| Recommended patch | Add 7-day rolling `night_txn_ratio` baseline to the context gate |

**Description:** The `context_senior_night` gate applies a 1.50× risk multiplier only to transactions occurring during defined night hours. By shifting transaction timing to daytime while preserving all other digital-arrest behavioural features, the multiplier is never triggered. A rolling 7-day `night_txn_ratio` baseline would close this gap.

---

### 🔴 Finding 3 — CRITICAL

**Archetype:** `ghost_node_cash`
**Evasion ID:** `graph_bypass_sink_with_outflow`

| Field | Detail |
|---|---|
| Gate bypassed | `sink` |
| Mechanism | Inflow accumulation phase not flagged; only active outflows are checked |
| TGEP pattern detected | *(none — no detector exists for accumulation-then-legitimate-spend)* |
| Recommended patch | Add inflow/outflow ratio analysis to both the Blue Team `sink` gate and the TGEP detector suite |

**Description:** The current sink gate monitors for fan-out above a threshold but does not track the ratio of inflow accumulation to eventual legitimate-looking outflows. A ghost node that accumulates funds over several days before dispersing them in transactions that individually appear legitimate evades both the gate and TGEP entirely. This is the most structurally significant finding to date.

---

## TGEP Graph Design

All 17 archetype attack templates use a **confirmed-safe graph structure** validated on **2026-06-05** against the live TGEP detector suite.

### Invariants

| Constraint | Value | Rationale |
|---|---|---|
| Inflow nodes | 3 institutional `CORP` accounts | Mimics realistic corporate payment flow |
| Central node | 1 `ACC` account | Aggregation hub |
| Outflow nodes | Max 2 | Below TGEP Fan-Out Network threshold (>2) |
| Outflow value | ≤ 15% of total inflow | Avoids balance-drain anomaly detectors |
| Max accounts per graph | 5 | Keeps graph within TGEP complexity limits |
| Fan-out cap | 2 | Strictly below TGEP fan-out detector trigger |

### Account Naming Convention

| Role | Format | Example |
|---|---|---|
| Institutional inflow | `CORP{3-digit}` | `CORP042` |
| Central aggregator | `ACC{6-digit}` | `ACC001337` |
| Payroll-style outflow | `PAYROLL_VENDOR_{3-digit}` | `PAYROLL_VENDOR_007` |
| Utility-style outflow | `UTIL_PROVIDER_{3-digit}` | `UTIL_PROVIDER_003` |

### Example Safe Graph

```
CORP001 ──┐
CORP002 ──┼──► ACC001337 ──► PAYROLL_VENDOR_001
CORP003 ──┘               └──► UTIL_PROVIDER_002
```

---

## API Reference

All endpoints (except `/health`) require the header:

```
X-API-Key: {RED_TEAM_API_KEY}
```

---

### `POST /red-team/ingest`

Enqueue a Blue Team confirmed-fraud signal for Red Team analysis.

**Request body** (union type — one of):

| Type | Description |
|---|---|
| `FraudDNA` | Blue Team primary fraud signal |
| `NoveltyEscalation` | Out-of-distribution escalation |
| `GateMissLog` | Missed gate log from Blue Team |
| `DatasetRecord` | Raw BAF-compatible record |

**Responses:**

| Status | Meaning |
|---|---|
| `202` | Accepted — `{ingest_id, priority, queued_for}` |
| `409` | Conflict — duplicate signal already in queue |
| `503` | Service Unavailable — priority queue at capacity |

---

### `GET /red-team/report/{ingest_id}`

Retrieve the full evasion analysis for a processed signal.

**Responses:**

| Status | Meaning |
|---|---|
| `200` | Full evasion analysis report |
| `404` | Ingest ID not found |

---

### `GET /red-team/evasions`

Paginated listing of the evasion knowledge base.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `severity` | `string` | Filter by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) |
| `archetype` | `string` | Filter by archetype name |
| `gate` | `string` | Filter by bypassed gate name |
| `limit` | `integer` | Page size (default: 20) |
| `offset` | `integer` | Page offset (default: 0) |

**Response:** `200` — paginated KB listing.

---

### `GET /red-team/briefing`

Security briefing for developers and Blue Team leads.

**Response:** `200`

```json
{
  "immediate_action_required": [ ... ],
  "structural_findings": [ ... ],
  "mutation_intelligence": { ... }
}
```

---

### `GET /red-team/attack-graph/{ingest_id}`

Retrieve the full attack package (all 22 evasion vectors) for a processed signal.

**Responses:**

| Status | Meaning |
|---|---|
| `200` | Complete — all 22 mutations processed, full packages returned |
| `202` | Processing — `{status: "processing", evasions_so_far: N}` |
| `404` | Ingest ID not found |

---

### `GET /health`

Liveness check — **no authentication required**.

**Response:** `200`

```json
{
  "status": "ok",
  "service": "red-team"
}
```

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum, set RED_TEAM_API_KEY
```

### 3. Start the service

```bash
uvicorn app.main:app --port 8002
```

### 4. Send a test signal

```bash
curl -X POST http://localhost:8002/red-team/ingest \
  -H 'X-API-Key: changeme' \
  -H 'Content-Type: application/json' \
  -d '{
    "source_type": "FRAUD_DNA",
    "account_id": "ACC001337",
    "risk_score": 0.91,
    "triggered_gates": ["cycle", "sink"],
    "features": {}
  }'
```

### 5. Poll for the attack graph

```bash
# Replace {ingest_id} with the ID returned above
curl http://localhost:8002/red-team/attack-graph/{ingest_id} \
  -H 'X-API-Key: changeme'
# Returns 202 until all 22 mutations complete, then 200
```

### 6. (Optional) Bulk-load all 16 archetype seeds

```bash
python scripts/bulk_load_seeds.py
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RED_TEAM_API_KEY` | `changeme` | `X-API-Key` value required on all authenticated endpoints |
| `PII_HASH_SALT` | `red-team-salt-changeme` | Salt for `sha256(SALT+value)[:12]` PII masking before storage |
| `BLUE_TEAM_SHADOW_API_KEY` | *(empty)* | Auth key for Blue Team shadow scorer integration |
| `BLUE_TEAM_SHADOW_URL` | *(empty)* | Base URL of Blue Team shadow scorer (not yet connected) |
| `BLUE_TEAM_INGEST_URL` | `http://localhost:8000/api/v1` | Blue Team ingest URL — reference only, not called at runtime |
| `TGEP_BASE_URL` | *(required for live TGEP)* | Public API URL of the TGEP graph scoring service |
| `TGEP_CLEAR_GRAPH_BETWEEN_ATTACKS` | `true` | Clear TGEP graph state before each attack package run |
| `POSTGRES_URL` | `postgresql://...` | Postgres connection string — deferred post-hackathon |
| `REDIS_URL` | `redis://...` | Redis connection string — deferred post-hackathon |
| `INGEST_RATE_LIMIT` | `500/minute` | slowapi rate limit applied to the ingest endpoint |
| `INGEST_QUEUE_MAX_SIZE` | `1000` | Per-tier queue capacity cap; returns `503` when full |
| `SELF_GENERATION_ENABLED` | `true` | Enable auto self-generation loop (3 archetypes every 5 min) |
| `BULK_LOAD_ON_STARTUP` | `false` | Inject all 16 archetype seeds as signals at service startup |

> [!WARNING]
> Change `RED_TEAM_API_KEY` and `PII_HASH_SALT` before any deployment outside localhost. The defaults are intentionally weak and for local development only.

---

## Testing

Run the full test suite:

```bash
pytest
```

Expected result: **155 / 155 passed**.

### Test File Reference

| File | Tests | Coverage Area |
|---|---|---|
| `tests/test_ingest.py` | 14 | Ingest endpoint validation, priority assignment, deduplication |
| `tests/test_mutation.py` | 15 | All 22 mutation types — single-feature, compound, tier-aware |
| `tests/test_graph_adversary.py` | 15 | 5 gate bypass checks (cycle, sink, bipartite, cash_mule, merchant) |
| `tests/test_sandbox.py` | 12 | Mutation sandbox isolation and rollback |
| `tests/test_worker.py` | 18 | Priority queue ordering, background worker lifecycle |
| `tests/test_briefing.py` | 25 | Briefing endpoint content and severity classification |
| `tests/test_tgep_contracts.py` | 20 | TGEP graph structure invariants and API contracts |
| `tests/test_tier_bypass.py` | 10 | Tier 1 / Tier 2 pre-flight gate logic |
| `tests/test_attack_package.py` | 6 | Attack package builder output structure |
| `tests/test_seed_library.py` | 7 | Seed library access, variation bounds, all 16 archetypes |
| `tests/test_sparse_payload_mutations.py` | 3 | Mutations on minimal/sparse feature payloads |
| `tests/test_security_and_queues.py` | 10 | Auth enforcement, rate limits, queue capacity |
| **Total** | **155** | |

### Running a specific test module

```bash
pytest tests/test_mutation.py -v
```

### Running by marker

```bash
pytest -m critical      # CRITICAL-severity evasion tests only
pytest -m graph         # Graph adversary tests only
```

---

## Known Limitations

> [!NOTE]
> These limitations are intentional scope decisions for the hackathon prototype. Production readiness items are tracked separately.

| Limitation | Impact | Post-Hackathon Plan |
|---|---|---|
| **In-memory stores only** | All signals, KB entries, and evasion packages are lost on restart | Migrate to Postgres (evasion KB) + Redis (queue state) |
| **Blue Team shadow scorer not connected** | Shadow scores always return `null` in evasion packages | Wire up once `BLUE_TEAM_SHADOW_URL` is available |
| **TGEP_BASE_URL required from teammates** | Without it, TGEP graph scoring falls back to mock responses | Coordinate URL with TGEP team at integration milestone |
| **Single-process only** | Cannot horizontally scale; one worker, one queue | Move to distributed queue (Redis Streams or Celery) post-hackathon |

---

## Security

### Authentication

All endpoints (except `/health`) require a **timing-safe** `X-API-Key` comparison using `hmac.compare_digest`. This prevents timing-oracle attacks against the API key.

### PII Masking

Any PII fields (account IDs, counterparty references, etc.) are hashed before storage using:

```
sha256(PII_HASH_SALT + raw_value)[:12]
```

The truncated digest is stored; the original value is never persisted.

### Rate Limiting

The ingest endpoint is rate-limited to **500 requests / minute** via [slowapi](https://github.com/laurentS/slowapi). Requests exceeding this return `429 Too Many Requests`.

### Golden Invariant

> [!CAUTION]
> **Red Team output is developer intelligence only.**
> It must **never** be connected to automated transaction blocking, customer-facing decisions, or any operational risk system. Violations of this invariant are a security incident.

---

*Generated: 2026-06-25 | BLING Hackathon — Red Team Service*
