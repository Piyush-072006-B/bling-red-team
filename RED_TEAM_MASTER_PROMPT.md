# 🔴 BLING Red Team — Master Build Prompt
### For: Google Antigravity (new, non-IDE version)
### Maintainer: BLING Hackathon · Union Bank of India

---

## CRITICAL OPERATING RULES (read before every single action)

1. **Always read `HANDOFF.md` first** at the start of every session. It is your only source of truth for what has been done and what to do next.
2. **Always update `HANDOFF.md` last** before ending any session — even if interrupted mid-task.
3. If the user types **"continue"**, your only action is: read `HANDOFF.md` → resume from `NEXT_TASK` exactly.
4. **Never delete or overwrite `HANDOFF.md`**. Only append/update its fields.
5. **Never create files outside the defined file structure below.** If you need a new file, add it to `HANDOFF.md` under `NEW_FILES_ADDED` and explain why.
6. **Never touch Blue Team code.** Red Team is a fully separate service. Integration is API-only.
7. After completing every task, mark it `[DONE]` in `HANDOFF.md` and write the next task in `NEXT_TASK`.
8. Run `pytest tests/ -v` after every module you build. Record pass/fail count in `HANDOFF.md`.

---

## PROJECT IDENTITY

**What this is:** The Red Team is an adversarial simulation engine that runs externally alongside the Blue Team (BLING forensic fraud detection, Union Bank of India). It receives confirmed fraud signals from Blue Team, mutates them to find detection blind spots, and pushes patch proposals back to Blue Team developers. It never touches production scoring.

**Golden invariant:** Red Team output is developer intelligence, not automated blocking. Every output is a proposal for a human to act on.

---

## FILE STRUCTURE (minimal and clean — do not deviate)

```
red-team/
├── HANDOFF.md                        ← state file, always updated
├── AGENTS.md                         ← Antigravity rules (committed)
├── README.md                         ← auto-generated last, includes draw.io flowchart
├── .env.example                      ← env vars template (no secrets)
├── docker-compose.yml                ← postgres + redis only
├── requirements.txt
├── alembic.ini
│
├── app/
│   ├── main.py                       ← FastAPI app entry
│   ├── config.py                     ← settings via pydantic-settings
│   │
│   ├── api/
│   │   ├── ingest.py                 ← POST /red-team/ingest
│   │   ├── report.py                 ← GET /red-team/report/{id}
│   │   └── evasions.py               ← GET /red-team/evasions
│   │
│   ├── ingest/
│   │   ├── router.py                 ← triage + dedup + priority queue
│   │   └── schemas.py                ← FraudDNA, NoveltyEscalation, GateMissLog pydantic models
│   │
│   ├── engines/
│   │   ├── archetype_extractor.py    ← map 59-feature vector → 16 archetypes or NEW_VARIANT
│   │   ├── mutation_engine.py        ← perturb features to evade Blue Team score
│   │   └── graph_adversary.py        ← synthesise subgraphs that bypass 5 hard gates
│   │
│   ├── sandbox/
│   │   ├── shadow_scorer.py          ← calls Blue Team shadow scorer endpoint (read-only)
│   │   └── evaluators.py             ← gate_probe, feature_sensitivity, context_bypass
│   │
│   ├── knowledge/
│   │   └── kb_store.py               ← append-only evasion knowledge base (postgres)
│   │
│   └── utils/
│       ├── auth.py                   ← X-API-Key middleware
│       └── audit_logger.py           ← structlog, no PII
│
├── ml/
│   └── similarity.py                 ← cosine sim for archetype matching (sklearn only)
│
├── alembic/
│   └── versions/
│       └── 001_initial_schema.py     ← 3 tables: evasion_kb, red_team_reports, ingest_log
│
└── tests/
    ├── test_ingest.py
    ├── test_mutation.py
    ├── test_graph_adversary.py
    └── test_sandbox.py
```

---

## HANDOFF.md SCHEMA (Antigravity must maintain this exact format)

```markdown
# HANDOFF.md — Red Team Build State

## STATUS
PHASE: [SETUP | BUILD | INTEGRATION | TESTING | DONE]
LAST_COMPLETED_TASK: [description]
NEXT_TASK: [exact next action]
BLOCKING_ISSUE: [none | description of blocker]
TESTS_PASSING: [X/Y]

## COMPLETED_TASKS
- [DONE] ...

## IN_PROGRESS
- [ ] ...

## PENDING_TASKS
- [ ] ...

## NEW_FILES_ADDED
(files not in original spec, with reason)

## INTEGRATION_STATUS
BLUE_TEAM_SHADOW_SCORER_URL: [configured | not yet]
BLUE_TEAM_INGEST_CONNECTED: [yes | no]
TGEP_WEBHOOK_CONNECTED: [yes | no]

## NOTES
(anything a fresh model needs to know to continue)
```

---

## BUILD PHASES (execute in order, never skip)

### PHASE 1 — SETUP

**Task 1.1 — Initialise HANDOFF.md**
Create `HANDOFF.md` with STATUS=SETUP, NEXT_TASK="Task 1.2 scaffold project".

**Task 1.2 — Scaffold project**
Create the exact file structure above. Every file gets a stub (docstring + TODO). Do not write logic yet.

**Task 1.3 — Environment files**
Create `.env.example`:
```
RED_TEAM_API_KEY=changeme
BLUE_TEAM_SHADOW_URL=http://localhost:8002          # Blue Team shadow scorer
BLUE_TEAM_INGEST_URL=http://localhost:8000/api/v1   # Blue Team main API
TGEP_WEBHOOK_URL=http://localhost:9000/webhook
POSTGRES_URL=postgresql://redteam:redteam@localhost:5433/redteam
REDIS_URL=redis://localhost:6380
```

**Task 1.4 — requirements.txt**
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
pydantic-settings==2.2.1
sqlalchemy==2.0.30
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9
redis==5.0.4
celery==5.4.0
scikit-learn==1.4.2
numpy==1.26.4
httpx==0.27.0
structlog==24.1.0
pytest==8.2.0
pytest-asyncio==0.23.6
python-dotenv==1.0.1
slowapi==0.1.9
```

**Task 1.5 — docker-compose.yml**
Two services only: postgres (port 5433, db=redteam) and redis (port 6380). Use different ports from Blue Team to allow both to run simultaneously on the same machine.

**Task 1.6 — Database schema**
Write `alembic/versions/001_initial_schema.py` with exactly 3 tables:

`ingest_log` — every incoming signal (id, source_type [FRAUD_DNA|NOVELTY|GATE_MISS], raw_payload jsonb, received_at, status)

`evasion_kb` — append-only knowledge base (id, archetype, evasion_vector jsonb, gate_bypassed text[], feature_deltas jsonb, context_multiplier_abused text, severity [LOW|MEDIUM|HIGH|CRITICAL], created_at)

`red_team_reports` — one report per evasion batch (id, report_type [GATE_PATCH|NEW_ARCHETYPE|CONTEXT_ABUSE], payload jsonb, recommended_action [PATCH|MONITOR|ACCEPT], created_at)

---

### PHASE 2 — BUILD (module by module, test after each)

**Task 2.1 — Pydantic schemas** (`app/ingest/schemas.py`)

Write three models:
- `FraudDNA`: transaction_id, account_id, confirmed_archetype (one of 16 or "NEW_VARIANT"), feature_vector (dict of 59 features), shap_values (dict), timestamp
- `NoveltyEscalation`: fingerprint_id, structural_features (dict of 17), occurrence_count, escalated_at
- `GateMissLog`: transaction_id, gate_name (one of: cycle, sink, bipartite, cash_mule_sink, merchant_terminal), alert_id, missed_at, investigator_note

**Task 2.2 — Auth middleware** (`app/utils/auth.py`)
X-API-Key header check. Key read from env. Return 403 on mismatch. Apply to all routes.

**Task 2.3 — Ingest router** (`app/ingest/router.py`)
- Dedup by transaction_id (check ingest_log first)
- Assign priority: FRAUD_DNA=HIGH, NOVELTY with occurrence_count>=15=CRITICAL, GATE_MISS=MEDIUM
- Write to ingest_log
- Push to appropriate analysis queue (use asyncio.Queue for now, Celery in Phase 3)
- Return: `{"ingest_id": uuid, "priority": str, "queued_for": str}`

**Task 2.4 — Archetype extractor** (`app/engines/archetype_extractor.py`)
Known archetypes and their dominant features (from Blue Team README):
```python
ARCHETYPE_SIGNATURES = {
    "structuring": ["amount_series_score", "txn_count_30d", "amount_vs_threshold_50000"],
    "romance_scam": ["counterparty_novelty", "return_ratio", "payee_vpa_age_days"],
    "pig_butchering": ["velocity_ratio", "burst_score", "counterparty_novelty"],
    "merchant_terminal": ["channel_switch", "return_ratio"],
    "cash_in_mule": ["cash_mule_sink_score", "dormancy_break"],
    "otp_fraud": ["burst_score", "channel_switch", "velocity_ratio"],
    "digital_arrest": ["night_txn_ratio", "payee_vpa_age_days", "amount_zscore"],
    "investment_fraud": ["channel_entropy", "counterparty_novelty", "burst_score"],
    "account_takeover": ["geography_switch", "channel_switch", "velocity_ratio"],
    "low_slow_mule": ["dormancy_reactivation_flag", "burst_score", "night_txn_ratio"],
    "cycle_round_trip": ["cycle_membership", "return_ratio", "fan_out_ratio"],
    "salary_mule": ["return_ratio", "velocity_ratio", "txn_count_30d"],
    "rapid_layering": ["temporal_acceleration", "fan_out_ratio", "velocity_ratio"],
    "sim_swap": ["geography_switch", "channel_switch", "burst_score"],
    "ghost_node_cash": ["cash_mule_sink_score", "geography_switch", "dormancy_break"],
    "bipartite_mule": ["bipartite_score", "fan_out_ratio", "distinct_counterparties_30d"],
}
```
Logic: cosine similarity between incoming feature_vector (normalised) and each archetype signature centroid. If max similarity < 0.45, label as NEW_VARIANT.

**Task 2.5 — Mutation engine** (`app/engines/mutation_engine.py`)
For a given feature_vector and confirmed_archetype, generate N=10 mutations:
- **Threshold mutations**: for `amount_series_score`, `amount_vs_threshold_50000/100000/1000000` — shift amount to 0.92× below threshold (evade structuring detection)
- **Timing mutations**: `night_txn_ratio` → push to 0.15 (daytime); `hour_deviation` → reduce to 0
- **Velocity mutations**: `burst_score` / `velocity_ratio` → reduce by 20–40% stepwise
- **Context abuse mutations**: if `is_festival_period`=0, flip to 1 (test if ×0.70 multiplier saves score); if account_age suggests senior (>60), remove night flag
- **Novelty mutations**: set `counterparty_novelty`=0 (pretend payee is known)

Each mutation returns: `{mutation_id, mutation_type, delta_features: dict, original_vector: dict, mutated_vector: dict}`

**Task 2.6 — Graph adversary** (`app/engines/graph_adversary.py`)
Generate synthetic transaction subgraphs designed to bypass each of Blue Team's 5 gates. Each gate has a bypass strategy:
- **Cycle gate bypass**: insert 2 intermediary nodes between A and C so path length = 9 hops (Blue Team checks 2–8 hops only)
- **Sink gate bypass**: add small outflow transactions to reduce `sink_score` = retention × inflow_concentration below threshold
- **Bipartite gate bypass**: split 7 senders into 2 batches of 4 and 3 (density drops below 0.7 trigger)
- **Cash mule sink bypass**: insert 48h digital activity between receive and ATM withdrawal (breaks dormancy pattern)
- **Merchant terminal bypass**: route through 2 POS terminals instead of round-trip through 1

Returns: `{gate_name, bypass_strategy, synthetic_subgraph: dict, expected_to_trigger: bool}`

**Task 2.7 — Shadow scorer client** (`app/sandbox/shadow_scorer.py`)
HTTP client using httpx that POSTs mutated transactions to `BLUE_TEAM_SHADOW_URL/api/v1/score`. Parse response: extract `score`, `action`, `gate_fired`. Timeout=5s. On failure: log and return `{"score": null, "error": "shadow_scorer_unavailable"}`. **Never call production Blue Team URL.**

**Task 2.8 — Evaluators** (`app/sandbox/evaluators.py`)
Three evaluators, each takes (original_result, mutated_result, mutation):

`gate_probe(original, mutated, mutation)` → returns which gate was bypassed, by how much (score delta), and the minimum delta required to trigger it (near-miss distance).

`feature_sensitivity(original, mutated, mutation)` → using SHAP values diff, identify which features contributed most to score reduction. Returns top-5 most exploitable features with their delta impact.

`context_bypass(original, mutated, mutation)` → check if any Indian context multiplier was responsible for score drop. Returns which multiplier was abused and the score delta it caused.

**Task 2.9 — Knowledge base store** (`app/knowledge/kb_store.py`)
Append-only writes to `evasion_kb`. Never update or delete rows. On insert: generate a severity score:
- CRITICAL: evasion_success=True AND gate bypassed AND context_multiplier_abused
- HIGH: evasion_success=True AND gate bypassed
- MEDIUM: score reduced below REVIEW threshold (0.50) from HIGH_RISK (≥0.75)
- LOW: score reduced but still above 0.50

**Task 2.10 — API routes**

`POST /red-team/ingest` — accepts FraudDNA | NoveltyEscalation | GateMissLog (discriminated union on `source_type` field). Calls ingest router. Returns ingest_id + priority.

`GET /red-team/report/{ingest_id}` — returns full evasion analysis for an ingest: mutations tried, evasions found, gate vulnerabilities, recommended action.

`GET /red-team/evasions` — paginated list of evasion_kb entries. Query params: `severity`, `archetype`, `gate`, `limit` (default 20), `offset`.

**Task 2.11 — FastAPI app** (`app/main.py`)
Wire all routers. Add auth middleware. Add `/health` returning `{"status":"ok","service":"red-team"}`. Add rate limiting: 500/min on ingest.

---

### PHASE 3 — INTEGRATION

**Task 3.1 — Blue Team webhook receiver**
Blue Team calls Red Team on confirmed fraud via `POST /red-team/ingest` with `source_type: "FRAUD_DNA"`. Verify this works end-to-end using a mock Blue Team payload.

**Task 3.2 — TGEP outbound webhook**
After a RED_TEAM_REPORT is generated with `recommended_action: "PATCH"`, fire a webhook to `TGEP_WEBHOOK_URL` with payload: `{report_id, archetype, gate_vulnerability, proposed_patch_summary, severity}`. Use httpx async POST. Retry once on failure.

**Task 3.3 — Shadow scorer connectivity test**
Write a one-shot test script `scripts/test_shadow_connection.py` that sends a known structuring transaction to the shadow scorer and asserts score > 0.5. Document the Blue Team setup needed (see Integration section below).

---

### PHASE 4 — TESTING

**Task 4.1 — test_ingest.py**
- Test dedup (same transaction_id twice → second gets 409)
- Test priority assignment for all three source types
- Test schema validation (missing fields → 422)

**Task 4.2 — test_mutation.py**
- For structuring archetype: assert all 10 mutations generated
- Assert threshold mutations produce amounts < 50000
- Assert mutated_vector differs from original_vector

**Task 4.3 — test_graph_adversary.py**
- For each of 5 gates: assert bypass strategy is generated
- Assert cycle bypass uses 9-hop path (outside 2–8 range)
- Assert bipartite bypass splits senders to density < 0.7

**Task 4.4 — test_sandbox.py**
- Mock shadow scorer returning score=0.9 (HIGH_RISK)
- Run mutation engine on digital_arrest archetype
- Assert at least one mutation produces score < 0.75 in mock
- Assert gate_probe returns gate_name and near_miss_delta

---

### PHASE 5 — README + DRAW.IO FLOWCHART

**Task 5.1 — Generate draw.io flowchart**
Use the draw.io skill to generate a flowchart XML showing:
1. Three inputs (Fraud DNA / Novelty Escalation / Gate Miss Log) → Ingest Router
2. Ingest Router → three engines (Archetype Extractor / Mutation Engine / Graph Adversary)
3. All three → Sandbox (Shadow Scorer + Evaluators)
4. Sandbox → Knowledge Base
5. Knowledge Base → three outputs (Gate Patch Proposal / New Archetype Spec / Red Team Report)
6. Red Team Report → TGEP webhook (dashed line)
7. Gate Patch / New Archetype → Blue Team (dashed line, labelled "developer action")

Save as `docs/red_team_architecture.drawio` and export PNG to `docs/red_team_architecture.png`.

**Task 5.2 — Write README.md**
Sections: What This Is · Architecture (embed PNG) · API Reference · How to Run · Integration with Blue Team · File Map · Tech Stack. Mirror Blue Team README style.

---

## INTEGRATION: HOW RED TEAM CONNECTS TO BLUE TEAM + TGEP

### Blue Team → Red Team (confirmed fraud signal)

Blue Team already calls `POST /feedback` when an investigator confirms fraud. In Blue Team's `app/api/feedback.py`, after the blockchain seal and River FTRL update, add one call:

```python
# In Blue Team feedback.py — add after existing blockchain + river calls
import httpx

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
```
RED_TEAM_URL=http://red-team:8002
RED_TEAM_API_KEY=changeme
```

Add `red-team` service to Blue Team's `docker-compose.yml` networks so both containers can reach each other.

### Blue Team → Red Team (novelty escalations)

In Blue Team's `app/detection/novelty/` wherever novelty escalations are sent to Red Team (on 10+ fingerprint), change the call to:

```python
await client.post(
    f"{settings.RED_TEAM_URL}/red-team/ingest",
    json={
        "source_type": "NOVELTY",
        "fingerprint_id": fingerprint_id,
        "structural_features": structural_features,
        "occurrence_count": count,
        "escalated_at": datetime.utcnow().isoformat()
    },
    headers={"X-API-Key": settings.RED_TEAM_API_KEY},
    timeout=3.0
)
```

### Red Team → Blue Team (shadow scorer)

Red Team needs a read-only copy of Blue Team's scorer to simulate against. Blue Team must expose one additional endpoint — **not in production flow, developer use only**:

```python
# Add to Blue Team app/api/ as shadow_score.py
# Route: POST /api/v1/shadow/score
# Auth: INTERNAL_API_KEY only
# Behaviour: identical to /api/v1/score but writes nothing to DB, fires no alerts
# Returns: same response schema as /api/v1/score
```

Red Team's `BLUE_TEAM_SHADOW_URL` points to this endpoint.

### Red Team → TGEP (patch proposals)

TGEP receives a webhook from Red Team when severity=CRITICAL or HIGH:

```json
POST TGEP_WEBHOOK_URL
{
  "source": "red_team",
  "report_id": "uuid",
  "event_type": "EVASION_CONFIRMED",
  "archetype": "structuring",
  "gate_vulnerability": "sink",
  "proposed_patch_summary": "Increase sink_score threshold from 0.6 to 0.72 based on 7 confirmed evasions",
  "severity": "HIGH",
  "recommended_action": "PATCH",
  "created_at": "2026-06-03T..."
}
```

TGEP should create a ticket or alert from this. If TGEP has a webhook receiver endpoint, point `TGEP_WEBHOOK_URL` to it. If not, Red Team stores the payload in `red_team_reports` and TGEP polls `GET /red-team/evasions?severity=HIGH`.

---

## PORTS REFERENCE (no conflicts with Blue Team)

| Service | Port |
|---------|------|
| Red Team API | 8002 |
| Red Team PostgreSQL | 5433 |
| Red Team Redis | 6380 |
| Blue Team API | 8000 |
| Blue Team PostgreSQL | 5432 |
| Blue Team Redis | 6379 |

---

## TECH STACK

FastAPI 0.111 · PostgreSQL 15 · Redis 7 · scikit-learn (similarity only) · httpx (shadow scorer + TGEP webhook) · structlog · Docker + Docker Compose

No XGBoost, no Neo4j, no Celery in v1. Keep it lean.

---

## WHAT RED TEAM MUST NEVER DO

- Never call `POST /api/v1/score` (production Blue Team scorer)
- Never write to Blue Team's database
- Never block or delay Blue Team's feedback pipeline
- Never auto-apply patches — only propose them
- Never store raw account IDs or VPAs in logs — hash them: `sha256(SALT + account_id)[:12]`

---

*End of master prompt. Antigravity: read HANDOFF.md first, then execute the current NEXT_TASK.*
