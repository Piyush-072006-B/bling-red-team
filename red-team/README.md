# BLING Red Team — Adversarial Fraud Simulation Engine

> **Status: PROTOTYPE — Hackathon Build**  
> Union Bank of India · BLING Forensic Fraud Detection System

![Tests](https://img.shields.io/badge/tests-155%2F155-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)
![Port](https://img.shields.io/badge/port-8002-orange)

---

## What It Does

Post-transaction adversarial simulation engine for the BLING fraud detection platform. Takes Blue Team confirmed-fraud signals, generates 22 mutations designed to evade detection, and produces developer intelligence about blind spots.

**It never blocks transactions. It never automates decisions.** Output is patch proposals for Blue Team engineers only.

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Tests passing | **155 / 155** |
| Mutations per signal | **22** (10 single + 6 compound + 6 tier-aware) |
| Fraud archetypes | **16** (BAF NeurIPS 2022 real data) |
| TGEP-evading graph templates | **17** (all confirmed undetected) |
| Self-generation interval | Every 5 minutes, 3 archetypes |
| Confirmed Red Team findings | **3** (2 CRITICAL, 1 HIGH) |

---

## 3 Confirmed Red Team Findings

> These are real blind spots found by running this engine against the Blue Team system.

| Severity | Finding | Blue Team Fix |
|----------|---------|---------------|
| 🔴 CRITICAL | **Cycle gate blind spot** — 9-hop linear chain evades the 2–8 hop cycle detector entirely | Extend `cycle_gate.py` to 10 hops |
| 🟡 HIGH | **Senior+night multiplier removable** — timing mutation strips the 1.50× risk amplifier | Add rolling 7-day baseline to `indian_context.py` |
| 🔴 CRITICAL | **Sink/accumulation evades BOTH Blue Team AND TGEP** — inflow accumulation + small legitimate outflows triggers no detectors | Add inflow/outflow ratio analysis to both |

### Finding Detail

**Finding 1 — cycle_round_trip / graph_bypass_nine_hop_linear (CRITICAL)**  
Blue Team cycle gate checks 2–8 hop chains. A 9-hop linear chain is structurally identical fraud but sits exactly one hop above the detector ceiling. TGEP did flag `circular_laundering` — confirming it is real fraud that Blue Team misses.  
→ Patch: raise ceiling from 8 to 10 in `cycle_gate.py`

**Finding 2 — digital_arrest / timing_day (HIGH)**  
Blue Team applies a 1.50× risk multiplier for transactions from elderly accounts at night. The `timing_day` mutation shifts `night_txn_ratio` → 0.05 and `hour_of_day` → 14:00, removing the multiplier. Score drops from 0.88 to 0.42.  
→ Patch: maintain 7-day rolling `night_txn_ratio` baseline so a single clean transaction cannot zero it out

**Finding 3 — ghost_node_cash / graph_bypass_sink_with_outflow (CRITICAL)**  
Multiple institutional inflows accumulate in one account, followed by small legitimate-looking outflows (payroll, utilities). Blue Team's sink gate scores accumulation but misses the inflow/outflow ratio dimension. TGEP has zero detector for this topology — it evades both systems simultaneously.  
→ Patch: add `inflow_outflow_ratio < 0.2` check to both Blue Team sink gate and TGEP graph analyzer

---

## TGEP Evasion Test Results

All 17 archetype templates use the confirmed-safe structure: **3 inflows → 1 central account → 2 outflows**

| Graph Pattern | TGEP Result |
|--------------|-------------|
| All 17 archetype templates (3→1→2 sink) | ✅ Undetected |
| `nine_hop_linear` (9-hop cycle bypass) | ⚠️ CRITICAL — confirms Blue Team blind spot |
| `sink_with_outflow` (original) | ✅ Undetected |
| `slow_bipartite` | ❌ Detected — fan-in topology obvious |

### Why 3→1→2 Works

TGEP's Fan-Out Network detector requires **> 2 outflow recipients** from a single account to trigger. Capping outflows at exactly 2 (payroll + utility) keeps every template below the threshold while maintaining realistic spending patterns.

---

## Architecture

```
POST /red-team/ingest
         │
         ▼
  Priority Queue (CRITICAL > HIGH > MEDIUM > LOW)
         │
         ▼
  Background Worker
    │
    ├─► Pre-flight Tier Check
    │     Tier 1: fast rules (amount, velocity, timing, novelty)
    │     Tier 2: graph gates at risk (cycle, sink, bipartite, mule, merchant)
    │
    ├─► Archetype Extractor
    │     Cosine similarity vs 16 BAF-derived signatures
    │     → confirmed archetype or NEW_VARIANT
    │
    ├─► Mutation Engine  ×22 mutations
    │     10 single-feature: threshold_50k/100k/1m, timing_day,
    │                        velocity_20/30/40pct, context_festival,
    │                        context_senior, novelty_zero
    │      6 compound:      daytime_slowdown, structuring_ghost,
    │                        festival_layering, mule_warmup,
    │                        kyc_ghost, senior_festival_night
    │      6 tier-aware:    compound_full_bypass, tier1_safe,
    │                        context_stack, gate_defeat_cycle,
    │                        gate_defeat_sink, gate_defeat_bipartite
    │
    ├─► Graph Adversary
    │     5 gate bypass checks: cycle, sink, bipartite, cash_mule, merchant
    │
    ├─► KB Feedback Loop
    │     Reads evasion_kb success rates → adaptive mutation weights
    │     High-weight mutations float to front of next candidate list
    │
    └─► Attack Package Builder
          Per-evasion TGEP graph (3→1→2 safe structure)
          + bypass strategy plain-English description
          + JSON file saved to outputs/
```

---

## 16 Fraud Archetypes

All seeds derived from BAF NeurIPS 2022 dataset (1M real transactions).

| Archetype | Key Signals | TGEP Graph |
|-----------|------------|------------|
| `digital_arrest` | night_txn_ratio, hour_deviation | ACC104821 |
| `structuring` | amount_vs_threshold_50000, txn_count_30d | ACC205934 |
| `rapid_layering` | velocity_ratio, channel_entropy | ACC301299 |
| `bipartite_mule` | bipartite_score, distinct_payees_24h | ACC401822 |
| `cycle_round_trip` | cycle_membership, return_ratio | ACC501933 |
| `cash_in_mule` | cash_mule_sink_score, fan_out_ratio | ACC601144 |
| `salary_mule` | dormancy_break, account_age_days | ACC701255 |
| `low_slow_mule` | temporal_acceleration, txn_count_30d | ACC801366 |
| `romance_scam` | counterparty_novelty, pagerank_fraud_seeded | ACC901477 |
| `pig_butchering` | community_fraud_ratio, burst_score | ACC120588 |
| `investment_fraud` | velocity_ratio, amount_zscore | ACC230699 |
| `account_takeover` | channel_switch, geography_switch | ACC340711 |
| `otp_fraud` | velocity_ratio, burst_score | ACC450822 |
| `sim_swap` | night_txn_ratio, is_night | ACC560933 |
| `ghost_node_cash` | sink_score, fan_out_ratio | ACC670144 |
| `merchant_terminal` | channel_entropy, txn_count_last_1h | ACC780255 |

---

## API Endpoints

All endpoints require `X-API-Key: {RED_TEAM_API_KEY}` except `/health`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/red-team/ingest` | Receive fraud signal (FraudDNA / NoveltyEscalation / GateMissLog) |
| `GET` | `/red-team/report/{id}` | Full evasion analysis for an ingest |
| `GET` | `/red-team/evasions` | Paginated KB listing (`?severity=&archetype=&gate=&limit=&offset=`) |
| `GET` | `/red-team/briefing` | Plain-English patch proposals (`immediate_action_required` + findings) |
| `GET` | `/red-team/attack-graph/{id}` | TGEP graph packages per mutation (202 while processing, 200 when 22/22 done) |
| `GET` | `/health` | Liveness check — no auth required |

### Ingest payload types

```json
// FraudDNA (most common — from Blue Team confirmed alert)
{
  "source_type": "FRAUD_DNA",
  "transaction_id": "TXN123",
  "account_id": "ACC456",
  "confirmed_archetype": "digital_arrest",
  "feature_vector": { "night_txn_ratio": 0.45, "burst_score": 0.85, ... },
  "shap_values": { "night_txn_ratio": 0.31, ... },
  "timestamp": "2026-06-25T10:00:00Z"
}
```

---

## How to Run

### Windows (recommended)

```powershell
.\start.ps1
```

### Manual

```bash
pip install -r requirements.txt
cp .env.example .env    # edit RED_TEAM_API_KEY at minimum
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

### Docker

```bash
docker-compose up -d
```

### Seed the KB immediately (optional)

```bash
# Inject all 16 BAF archetype seeds without waiting for the self-gen loop
python scripts/bulk_load_seeds.py

# Record the 3 confirmed Red Team findings
python scripts/record_findings.py
```

### Generate TGEP graphs for manual testing

```bash
python scripts/export_all_tgep_graphs.py
# Prints all 17 archetype graph arrays to terminal + saves to data/all_tgep_graphs.json
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RED_TEAM_API_KEY` | `changeme` | X-API-Key for all protected endpoints |
| `PII_HASH_SALT` | `red-team-salt-changeme` | SHA-256 PII masking salt (change in production) |
| `BLUE_TEAM_SHADOW_API_KEY` | *(empty)* | Blue Team shadow scorer auth key |
| `BLUE_TEAM_SHADOW_URL` | *(empty)* | Blue Team shadow scorer base URL — leave empty to disable |
| `BLUE_TEAM_INGEST_URL` | `http://localhost:8000/api/v1` | Blue Team main API (reference only) |
| `TGEP_BASE_URL` | *(empty)* | TGEP public API URL — leave empty to skip live scoring |
| `TGEP_CLEAR_GRAPH_BETWEEN_ATTACKS` | `true` | Clear TGEP graph before each new attack |
| `POSTGRES_URL` | `postgresql://...` | Deferred post-hackathon |
| `REDIS_URL` | `redis://...` | Deferred post-hackathon |
| `INGEST_RATE_LIMIT` | `500/minute` | slowapi rate limit on ingest endpoint |
| `INGEST_QUEUE_MAX_SIZE` | `1000` | Per-tier queue cap — returns 503 when full |
| `SELF_GENERATION_ENABLED` | `true` | Auto self-gen every 5 min from seed library |
| `BULK_LOAD_ON_STARTUP` | `false` | Inject all 16 seeds at startup automatically |

---

## Tests

```bash
pytest          # 155/155 passing
pytest -v       # verbose per-test output
pytest -k ingest  # filter by name
```

| Test File | Tests | Coverage |
|-----------|-------|---------|
| `test_briefing.py` | 25 | Briefing endpoint, finding classification |
| `test_worker.py` | 18 | Pipeline, pre-flight, KB writes |
| `test_tgep_contracts.py` | 20 | TGEP edge schema, account naming |
| `test_graph_adversary.py` | 15 | Gate bypass logic |
| `test_mutation.py` | 15 | All 22 mutation types |
| `test_ingest.py` | 14 | Priority queuing, dedup, PII hashing |
| `test_sandbox.py` | 12 | Endpoint auth, rate limiting |
| `test_security_and_queues.py` | 10 | Security headers, queue backpressure |
| `test_tier_bypass.py` | 10 | Tier-aware mutations, graph patterns |
| `test_seed_library.py` | 7 | BAF-derived seed vectors, all 16 archetypes |
| `test_attack_package.py` | 6 | Attack package builder, TGEP graph shape |
| `test_sparse_payload_mutations.py` | 3 | Sparse / missing feature handling |

---

## Known Limitations

> This is a hackathon prototype. The following are known and intentional deferred items.

- **In-memory only** — all data lost on restart. Postgres + Redis integration is wired but deferred post-hackathon.
- **Shadow scorer offline** — Blue Team's `/api/v1/shadow/score` endpoint is needed to compute real mutation success scores. Currently returns `null` scores.
- **TGEP auto-send disabled** — requires a live Render/Vercel backend URL from teammates. Currently graphs are exported to JSON for manual paste.
- **3 findings recorded, more testing pending** — live end-to-end testing with Blue Team needed for additional confirmation.
- **Single-process** — asyncio.Queue is per-process. Horizontal scaling requires Celery + Redis (Phase 3).

---

## Security

- **Authentication**: X-API-Key with timing-safe comparison (all endpoints except `/health`)
- **PII masking**: `sha256(SALT + value)[:12]` — raw account IDs and transaction IDs never stored
- **Rate limiting**: 500 req/min on ingest via slowapi
- **Output invariant**: Red Team output is **developer intelligence only — it never automates blocking decisions**

---

## Project Structure

```
red-team/
├── app/
│   ├── api/              # FastAPI routers (ingest, report, evasions, briefing, attack-graph)
│   ├── engines/          # Core logic
│   │   ├── mutation_engine.py      # 22-mutation generator
│   │   ├── archetype_extractor.py  # Cosine similarity classifier
│   │   ├── graph_adversary.py      # 5 gate bypass checks
│   │   ├── tier_aware_mutations.py # 6 tier-aware compound mutations
│   │   ├── tgep_bypass_graphs.py   # 4 hardcoded bypass topologies
│   │   ├── kb_feedback.py          # Adaptive mutation weights from KB
│   │   ├── seed_library.py         # get_seed(), get_all_seeds()
│   │   └── self_generator.py       # Autonomous pattern generation loop
│   ├── knowledge/
│   │   └── kb_store.py             # In-memory evasion KB
│   ├── outputs/
│   │   ├── graph_exporter.py       # 17 archetype TGEP graph templates
│   │   └── attack_package.py       # Attack package builder
│   └── worker/
│       └── pipeline.py             # Background processing pipeline
├── data/
│   ├── computed_archetype_seeds.json  # BAF NeurIPS 2022 derived seeds
│   └── all_tgep_graphs.json           # Pre-generated TGEP graphs for all 17 archetypes
├── scripts/
│   ├── bulk_load_seeds.py    # Inject all 16 seeds at startup
│   ├── record_findings.py    # Record 3 confirmed findings in KB
│   └── export_all_tgep_graphs.py  # Generate + print all 17 TGEP graphs
└── tests/                    # 155 tests
```

---

*Built for the BLING Forensic Fraud Detection Hackathon — Union Bank of India, 2026*
