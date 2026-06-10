# BLING Red Team
**Adversarial Fraud Simulation Engine — Union Bank of India**

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)
![FastAPI 0.111](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square)
![Tests: 127 passing](https://img.shields.io/badge/Tests-127_passing-success?style=flat-square)
![Status: Prototype](https://img.shields.io/badge/Status-Prototype-orange?style=flat-square)
![PostgreSQL 15](https://img.shields.io/badge/PostgreSQL-15-blue?style=flat-square)
![Redis 7](https://img.shields.io/badge/Redis-7-red?style=flat-square)

---

## What This Is

Red Team is a post-transaction adversarial simulation engine built for the BLING Hackathon at Union Bank of India. It runs alongside Blue Team (forensic fraud detection) and TGEP (transaction graph engine).

It does NOT score live transactions and does NOT block anything. Its sole purpose: take confirmed fraud signals, mutate them 10 ways to find what Blue Team would miss, and produce developer intelligence — specific, actionable patch proposals.

Golden invariant: Every output is a proposal for a human developer. Nothing is automated. Investigators stay in control.

The system is composed of three services:
- **Blue Team**: ML fraud detection, 3-tier pipeline, 59 features, 5 hard gates
- **Red Team**: adversarial engine (this repo)
- **TGEP**: graph pattern analysis deployed on Vercel

---

## Architecture

```text
POST /red-team/ingest
        │
        ▼
┌─────────────────────┐
│   Ingest Router     │  dedup · priority · sanitize PII
│  (asyncio.Queue)    │  CRITICAL / HIGH / MEDIUM / LOW
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Worker Pipeline   │  background asyncio.Task
│   pipeline.py       │
└──┬──────┬───────────┘
   │      │
   ▼      ▼
FRAUD_DNA          NOVELTY / GATE_MISS
   │                    │
   ▼                    ▼
archetype_extractor  graph_adversary
mutation_engine      (5 gate bypasses)
shadow_scorer
evaluators
   │                    │
   └──────────┬─────────┘
              ▼
      ┌───────────────┐
      │   kb_store    │  append-only evasion KB
      └───────┬───────┘
              │
      ┌───────┴────────────────────────────┐
      │                                    │
      ▼                                    ▼
GET /red-team/briefing          TGEP webhook (HIGH/CRITICAL only)
GET /red-team/report/{id}       fires to TGEP_WEBHOOK_URL
GET /red-team/evasions
```

The draw.io architecture diagram is at `docs/red_team_architecture.drawio` and the SVG is at `docs/red_team_architecture.svg`.

---

## The 3 Input Signal Types

| Signal Type | Source | Priority | What Red Team does with it |
|---|---|---|---|
| **FRAUD_DNA** | Blue Team POST /feedback confirmed fraud | HIGH | Extracts archetype → generates 10 mutations → scores each via shadow scorer → evaluates gate probes + SHAP sensitivity + context bypass → writes to KB |
| **NOVELTY** | Blue Team IF queue escalation (10+ same fingerprint) | CRITICAL | Extracts archetype → runs all 5 gate adversary bypasses → writes 5 evasions to KB |
| **GATE_MISS** | Investigator-confirmed false negative | MEDIUM | Runs graph adversary for that specific gate → writes 1 evasion to KB |

---

## The 10 Mutation Types

| Mutation | Feature Changed | What It Tests |
|---|---|---|
| threshold_amount_50k | amount_series_score, amount_vs_threshold_50000 | Structuring below ₹50K |
| threshold_amount_100k | amount_vs_threshold_100000 | Structuring below ₹1L |
| threshold_amount_1m | amount_vs_threshold_1000000 | Structuring below ₹10L PMLA threshold |
| timing_day | night_txn_ratio 0.95→0.15 | Daytime disguise of night fraud |
| velocity_20pct | burst_score -20%, velocity_ratio -2.8 | Slow velocity to evade burst gate |
| velocity_30pct | burst_score -30%, velocity_ratio -2.8 | Slower velocity evasion |
| velocity_40pct | burst_score -40%, velocity_ratio -2.8 | Maximum velocity reduction |
| context_festival | is_festival_period=1 | Abuse ×0.70 festival multiplier |
| context_senior | night_txn_ratio→0 | Remove senior+night ×1.50 trigger |
| novelty_zero | counterparty_novelty=0 | Pretend payee is a known contact |

---

## The 5 Gate Bypass Strategies

| Gate | Blue Team Detection | Red Team Bypass Strategy |
|---|---|---|
| Cycle | Circular paths 2-8 hops | Synthesise 9-hop path — outside detection range |
| Sink | High retention + inflow concentration | Add small outflow transactions to reduce sink_score |
| Bipartite | 7+ senders → 1 collector density >0.7 | Split senders into 4+3 batches, density drops below 0.7 |
| Cash Mule Sink | Receive → ATM → digital silence | Insert 48h of small activity between receive and ATM |
| Merchant Terminal | Round-trip through same POS | Route through 2 different POS terminals |

---

## API Reference

All routes require `X-API-Key` header except `/health`.
Rate limit: `500/minute` on `POST /red-team/ingest`.

**POST /red-team/ingest**
- **Auth**: X-API-Key
- **Rate limit**: 500/min
- **Input**: FraudDNA | NoveltyEscalation | GateMissLog (discriminated on source_type)
- **Returns 202**: `{ingest_id, priority, queued_for}`
- **Returns 503**: `{"detail": "queue_full"}` when all 4 queues at max capacity
- **Returns 409**: duplicate transaction_id

*FraudDNA schema:*
```json
{
  "source_type": "FRAUD_DNA",
  "transaction_id": "TXN_001",
  "account_id": "ACC_123",
  "confirmed_archetype": "digital_arrest",
  "feature_vector": { ...up to 59 features... },
  "shap_values": { ...top features... },
  "timestamp": "2026-06-06T02:14:00Z"
}
```

*NoveltyEscalation schema:*
```json
{
  "source_type": "NOVELTY",
  "fingerprint_id": "fp_abc123",
  "structural_features": { ...17 features... },
  "occurrence_count": 15,
  "escalated_at": "2026-06-06T..."
}
```

*GateMissLog schema:*
```json
{
  "source_type": "GATE_MISS",
  "transaction_id": "TXN_002",
  "gate_name": "cycle",
  "alert_id": "alert_xyz",
  "missed_at": "2026-06-06T...",
  "investigator_note": "circular pattern missed"
}
```

**GET /red-team/report/{ingest_id}**
- **Auth**: X-API-Key
- **Returns**: full evasion analysis — all mutations tried, gate vulnerabilities, SHAP deltas, recommended action, tgep_webhook_status
- **Returns 202** if still processing
- **Returns 404** if not found

**GET /red-team/evasions**
- **Auth**: X-API-Key
- **Query params**: severity (LOW|MEDIUM|HIGH|CRITICAL), archetype, gate, limit (default 20), offset
- **Returns**: paginated list of evasion KB entries with full mutation vectors

**GET /red-team/briefing**
- **Auth**: X-API-Key
- **Returns** human-readable developer intelligence:
```json
{
  "threat_summary": "X evasion patterns. Y CRITICAL, Z HIGH.",
  "immediate_action_required": [
    {
      "priority": 1,
      "severity": "CRITICAL",
      "title": "plain English title",
      "what_was_found": "plain English explanation",
      "what_to_change": "exact fix instruction",
      "file": "blue_team file to change",
      "evasion_ids": ["uuid"]
    }
  ],
  "monitor": ["...HIGH severity..."],
  "structural_findings": ["...LOW/MEDIUM — real findings, shadow scorer offline..."],
  "top_exploitable_features": ["velocity_ratio", "burst_score", "night_txn_ratio"],
  "context_multipliers_at_risk": ["festival_0.70x"],
  "mutation_intelligence": {
    "summary": "Shadow scorer offline — showing structural analysis only",
    "top_exploitable_features": ["...with plain_english + recommendation..."],
    "context_multipliers_tested": ["..."],
    "archetype_confirmed": "...",
    "tgep_payload_hint": "..."
  }
}
```
*Note: briefing works even when shadow scorer is offline — mutation_intelligence section provides structural analysis regardless of Blue Team connectivity.*

**GET /health**
- **No auth required**
- **Returns**: `{"status": "ok", "service": "red-team"}`

Interactive docs: http://localhost:8002/docs

---

## Three Output Layers

**Layer 1 — GET /red-team/evasions**
- **Audience**: data engineers, automated pipelines
- **Content**: raw KB entries, filterable, all 40+ fields per evasion
- **Use case**: bulk analysis, integration with other tools

**Layer 2 — GET /red-team/report/{id}**
- **Audience**: security engineers
- **Content**: full analysis for one ingest — all 10 mutations, gate probes, SHAP deltas, recommended action
- **Use case**: deep investigation of a specific confirmed fraud case

**Layer 3 — GET /red-team/briefing**
- **Audience**: Blue Team developers, product managers
- **Content**: plain English — what to fix, which file, why it matters
- **Use case**: daily briefing, what to patch this sprint
- **Works offline**: mutation_intelligence section runs without Blue Team connected

---

## Validated TGEP Test Results

Date: June 5, 2026

| Pattern | Mutations Applied | TGEP Result | Threat Level | Key Finding |
|---|---|---|---|---|
| digital_arrest | timing_day — shifted night_txn_ratio 0.95→0.15 | Hybrid Laundering 69%, Smurfing 48% | HIGH | Blue Team senior+night ×1.50 multiplier bypassed by timing shift. Graph still detectable. |
| 9-hop cycle | graph_adversary cycle bypass — 9 hops vs Blue Team's 2-8 range | Circular Laundering 96%, Cross-Rail 67% | CRITICAL | Cycle gate has hard upper bound of 8 hops. 9-hop path completely bypasses Tier-2. |
| 7-sender bipartite | graph_adversary bipartite split 4+3 | Fan-In Aggregation 59%, Hybrid Laundering 84% | HIGH | Density threshold at 0.7 bypassable by splitting sender batches. |

---

## Three Confirmed Patch Proposals for Blue Team

**PATCH 1 — Cycle Gate Upper Bound (CRITICAL)**
- **Current**: cycle gate detects paths 2-8 hops
- **Gap**: 9-hop circular path scored CRITICAL on TGEP, bypassed Blue Team entirely
- **Fix**: extend cycle_membership nightly batch to check up to 10 hops
- **File**: app/detection/tier2/cycle_gate.py

**PATCH 2 — Senior+Night Multiplier Secondary Trigger (HIGH)**
- **Current**: senior + night_txn_ratio > 0.5 triggers ×1.50 multiplier
- **Gap**: shifting night_txn_ratio to 0.15 removes the multiplier entirely
- **Fix**: add dormancy_reactivation_flag=1 as independent trigger regardless of night_txn_ratio
- **File**: app/detection/context/indian_context.py

**PATCH 3 — Bipartite Gate Density Threshold (HIGH)**
- **Current**: bipartite gate fires at density > 0.7 with 7+ senders
- **Gap**: splitting 7 senders into 4+3 batches reduces density below threshold
- **Fix**: lower density threshold to 0.55 or add time-window aggregation across batches
- **File**: app/detection/tier2/bipartite_gate.py

---

## Security

| Concern | Implementation |
|---|---|
| Auth | X-API-Key header on all routes, checked via timing-safe comparison |
| PII in logs | sha256(SALT + identifier)[:12] — account_id, transaction_id, fingerprint_id, alert_id never stored raw |
| Rate limiting | 500/min on POST /red-team/ingest via slowapi (utils/limiter.py) |
| Queue bounds | INGEST_QUEUE_MAX_SIZE=1000 — returns HTTP 503 when full |
| SQL injection | Parameterized queries only |
| Shadow scorer | BLUE_TEAM_SHADOW_URL defaults to empty — will not call itself |
| Secrets | .env only, never committed |
| Golden invariant | Red Team output is developer intelligence only — never automated blocking |

---

## How to Run Locally

Prerequisites: Python 3.11, Docker Desktop, Git

**Step 1 — Clone and setup:**
```bash
git clone <repo>
cd bling-red-team/red-team
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

**Step 2 — Configure:**
```bash
copy .env.example .env
# Edit .env — set RED_TEAM_API_KEY to something secure
```

**Step 3 — Start infrastructure:**
```bash
docker-compose up -d
```

**Step 4 — Run migrations:**
```bash
alembic upgrade head
```

**Step 5 — Start server:**
```bash
uvicorn app.main:app --reload --port 8002
```

*OR use the convenience scripts from project root:*
```bash
Double-click start.ps1   # starts everything + opens browser
Double-click stop.ps1    # stops everything cleanly
```

**Step 6 — Verify:**
- Open http://localhost:8002/health
- Open http://localhost:8002/docs  ← interactive API explorer

**Step 7 — Run tests:**
```bash
pytest tests/ -v   # 127/127 passing
```

---

## Environment Variables

| Variable | Description | Default / Example |
|---|---|---|
| RED_TEAM_API_KEY | X-API-Key for all inbound requests | Required |
| BLUE_TEAM_SHADOW_URL | Blue Team shadow scorer URL | Leave empty until Blue Team wired |
| BLUE_TEAM_INGEST_URL | Blue Team main API base URL | Reference only |
| TGEP_WEBHOOK_URL | TGEP webhook endpoint | Leave empty until TGEP wired |
| POSTGRES_URL | Sync PostgreSQL URL for Alembic | postgresql://redteam:redteam@localhost:5433/redteam |
| POSTGRES_ASYNC_URL | Async PostgreSQL URL for SQLAlchemy | postgresql+asyncpg://... |
| REDIS_URL | Redis URL | redis://localhost:6380 |
| APP_ENV | development / staging / production | development |
| LOG_LEVEL | DEBUG / INFO / WARNING / ERROR | INFO |
| INGEST_RATE_LIMIT | slowapi rate limit string | 500/minute |
| INGEST_QUEUE_MAX_SIZE | max items across all 4 priority queues | 1000 |
| PII_HASH_SALT | Salt for sha256 PII masking | Change in production |

---

## File Map

```text
app/main.py — FastAPI app, lifespan, worker startup, CORS, rate limit handler
app/config.py — pydantic-settings, all env vars, cached singleton
app/api/ingest.py — POST /red-team/ingest, rate limit decorator
app/api/report.py — GET /red-team/report/{id}
app/api/evasions.py — GET /red-team/evasions, paginated KB query
app/api/briefing.py — GET /red-team/briefing, human-readable intelligence
app/api/tgep_webhook.py — outbound webhook to TGEP (no inbound routes)
app/ingest/router.py — dedup, PII sanitization, priority queue assignment
app/ingest/schemas.py — FraudDNA, NoveltyEscalation, GateMissLog pydantic models
app/engines/archetype_extractor.py — cosine similarity → 16 archetypes or NEW_VARIANT
app/engines/mutation_engine.py — generates 10 mutations per fraud signal
app/engines/graph_adversary.py — 5 gate bypass strategies
app/sandbox/shadow_scorer.py — httpx client to Blue Team shadow endpoint
app/sandbox/evaluators.py — gate_probe, feature_sensitivity, context_bypass
app/knowledge/kb_store.py — append-only evasion knowledge base (WARNING: in-memory)
app/worker/pipeline.py — background asyncio.Task, consumes queue, runs full pipeline
app/utils/auth.py — timing-safe X-API-Key check
app/utils/audit_logger.py — structlog, hash_id() for PII masking
app/utils/limiter.py — shared slowapi Limiter singleton
ml/similarity.py — cosine similarity for archetype matching
alembic/versions/001_initial_schema.py — 3 tables: ingest_log, evasion_kb, red_team_reports
docs/red_team_architecture.drawio — draw.io architecture diagram
docs/red_team_architecture.svg — SVG export for README embedding
```

---

## Database Schema

Three tables:

- **ingest_log** — every incoming signal
  `id, source_type (FRAUD_DNA|NOVELTY|GATE_MISS), raw_payload (sanitized jsonb), received_at, status (QUEUED|IN_PROGRESS|COMPLETED|FAILED), transaction_id_hash (SHA-256 dedup key, no raw IDs stored)`

- **evasion_kb** — append-only, never updated or deleted
  `id, archetype, evasion_vector jsonb, gate_bypassed text[], feature_deltas jsonb, context_multiplier_abused, severity, evasion_success, score_original, score_mutated, mutation_type, gate_probe_result jsonb, feature_sensitivity_result jsonb, context_bypass_result jsonb, ingest_log_id (FK), created_at`

- **red_team_reports** — one per evasion batch
  `id, report_type (GATE_PATCH|NEW_ARCHETYPE|CONTEXT_ABUSE), payload jsonb, recommended_action (PATCH|MONITOR|ACCEPT), tgep_webhook_sent bool, created_at`

**Ports (no conflicts with Blue Team):**
- Red Team API: 8002 | Blue Team API: 8000
- Red Team PostgreSQL: 5433 | Blue Team PostgreSQL: 5432
- Red Team Redis: 6380 | Blue Team Redis: 6379

---

## Tech Stack

- **FastAPI 0.111** | API framework
- **PostgreSQL 15** | Primary database (schema ready, persistence deferred)
- **Redis 7** | Queue/cache (configured, persistence deferred)
- **scikit-learn** | Cosine similarity for archetype matching only
- **httpx** | Shadow scorer client + TGEP outbound webhook
- **structlog** | Structured logging with PII masking
- **slowapi** | Rate limiting
- **Docker + Docker Compose** | Infrastructure
- **pytest** | 127/127 tests passing

---

## Integration with Blue Team and TGEP (deferred)

### A. Blue Team → Red Team (confirmed fraud)
Add one httpx call in Blue Team `feedback.py` after blockchain seal.

```python
async def notify_red_team(fraud_dna: dict):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.RED_TEAM_URL}/red-team/ingest",
                json={
                    "source_type": "FRAUD_DNA",
                    "transaction_id": fraud_dna["transaction_id"],
                    "account_id": fraud_dna["account_id"],
                    "confirmed_archetype": fraud_dna["archetype"],
                    "feature_vector": fraud_dna["feature_vector"],
                    "shap_values": fraud_dna["shap_values"],
                    "timestamp": fraud_dna["timestamp"]
                },
                headers={"X-API-Key": settings.RED_TEAM_API_KEY},
                timeout=3.0
            )
        except Exception:
            pass  # Red Team is non-critical — never block Blue Team on failure
```

Add to Blue Team `.env`:
```env
RED_TEAM_URL=http://red-team:8002
RED_TEAM_API_KEY=changeme
```

### B. Blue Team shadow scorer
Blue Team must expose one new read-only endpoint:
**POST /api/v1/shadow/score**
- Auth: INTERNAL_API_KEY only
- Behaviour: identical to `/api/v1/score` but writes nothing to DB, fires no alerts
- Point Red Team `BLUE_TEAM_SHADOW_URL` at this endpoint.

### C. Red Team → TGEP webhook
- Find the exact webhook path on `transaction-graph-engine.vercel.app`
- Set in Red Team `.env`: `TGEP_WEBHOOK_URL=https://transaction-graph-engine.vercel.app/[path]`
- Red Team fires automatically for HIGH/CRITICAL severity evasions.

Webhook payload format:
```json
{
  "source": "red_team",
  "report_id": "uuid",
  "event_type": "EVASION_CONFIRMED",
  "archetype": "digital_arrest",
  "gate_vulnerability": "cycle",
  "proposed_patch_summary": "...",
  "severity": "HIGH",
  "recommended_action": "PATCH",
  "created_at": "..."
}
```

---

## Known Limitations

**WARNING: PROTOTYPE STATUS**
- **In-memory only**: `_queues`, `_seen_hashes`, `_ingest_log` (router.py) and `_evasion_kb` (kb_store.py) are in-memory. Data is lost on server restart.
- **Single process only**: not safe for multi-worker deployment
- Postgres schema exists and migrations run, but runtime does not persist to DB yet
- Redis is configured but not used for queue durability yet
- Persistence to Postgres/Redis is deferred post-hackathon

**Shadow scorer offline**:
- When `BLUE_TEAM_SHADOW_URL` is empty, `score_original=0` and `score_mutated=null`
- All severities show as LOW in this state
- `mutation_intelligence` section of `/briefing` still provides full structural analysis regardless of shadow scorer status

---

## What Red Team Does NOT Do

- Does not score live transactions
- Does not block or delay any transaction
- Does not write to Blue Team's database
- Does not auto-apply any patch proposal
- Does not store raw account IDs, transaction IDs, or VPAs anywhere
- Does not call production Blue Team scorer (shadow only)
- Does not make irreversible decisions of any kind

---

*BLING Hackathon · Red Team · Union Bank of India*  
*Adversarial fraud simulation with graph intelligence*  
*Post-transaction · Developer intelligence only · Never automated blocking*
