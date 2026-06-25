<div align="center">

# BLING Red Team
### Adversarial Fraud Simulation Engine — Union Bank of India
**Hackathon: I.D.E.A 2.0 — BYTEJAYS Team**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-155%20passing-brightgreen)
![Status](https://img.shields.io/badge/Status-Hackathon%20Ready-success)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Dataset](https://img.shields.io/badge/Dataset-BAF%20NeurIPS%202022-blue)

</div>

---

## 1. What This Is

Post-transaction adversarial simulation engine built for BLING at Union Bank of India. Sits alongside Blue Team (forensic fraud detection) and TGEP (transaction graph engine) as a third service that finds what the other two miss.

Takes confirmed fraud signals, generates 22 mutations targeting all 3 Blue Team detection tiers, produces developer intelligence — specific patch proposals with exact files to change. Never blocks anything. Never automates decisions. Investigators stay in control.

**Three golden invariants:**
1. Every output is a proposal for a human developer
2. Red Team never writes to Blue Team's database
3. Red Team never makes enforcement decisions

---

## 2. Architecture

Three services:
- **TGEP (port 8000)** — graph intelligence, NetworkX + own XGBoost AUC 0.93, 6 fraud typologies
- **Blue Team (port 8001)** — 3-tier pipeline, 59 features, XGBoost AUC 0.69, 5 hard gates
- **Red Team (port 8002)** — adversarial engine (this repo)

```text
POST /red-team/ingest
        │
        ▼
┌─────────────────────────┐
│     Ingest Router       │  SHA-256 dedup · PII hash · priority queue
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│   Background Worker     │  asyncio.Task · CRITICAL/HIGH/MEDIUM/LOW
└──┬──────────────────────┘
   │
   ▼
Pre-flight tier check → Archetype extractor (16 archetypes, BAF seeds)
   │
   ▼
Mutation engine (22 mutations · KB-weighted · IF fingerprint vary)
   │
   ▼
Shadow scorer (offline → structural analysis only)
   │
   ▼
Graph exporter (3→1→2 sink/accumulation · TGEP-evading)
   │
   ▼
Evasion KB ──► GET /red-team/briefing
              GET /red-team/attack-graph/{id}
              GET /red-team/evasions
              GET /red-team/report/{id}
```

---

## 3. Three Confirmed Red Team Findings

| Priority | Severity | Finding | What Was Proved | Fix |
|---|---|---|---|---|
| 1 | CRITICAL | Cycle gate blind spot | 9-hop chain scores CRITICAL on TGEP (96% circular laundering) but bypasses Blue Team Tier 2 entirely (checks 2-8 hops only) | Extend cycle_gate.py nightly batch to 10 hops |
| 2 | HIGH | Senior+night multiplier removed by timing | timing_day mutation shifts night_txn_ratio 0.95→0.15, removes ×1.50 multiplier — Blue Team has no rolling baseline | Add 7-day rolling night_txn_ratio baseline in indian_context.py |
| 3 | CRITICAL | Sink/accumulation — double blind spot | Large institutional inflows + small legitimate outflows evades Blue Team sink gate AND TGEP internal analyzer — confirmed across 3 separate test sessions | Add inflow/outflow ratio floor to Blue Team sink gate AND TGEP graph analyzer |

Finding 3 is the most significant. A ₹11.3 lakh transaction disguised as legitimate corporate payments — payroll, utilities, insurance — is invisible to both detection systems. Red Team found this pattern by combining the confirmed evasion structure with real BAF NeurIPS 2022 fraud statistics.

---

## 4. TGEP Evasion Test Results

*Date: June 25, 2026*

| Pattern | Structure | TGEP Result | Notes |
|---|---|---|---|
| All 17 archetype templates | 3 inflows → 1 central → 2 outflows | No fraud detected | Confirmed across all 17 archetypes |
| nine_hop_linear | 9-hop linear A→B→...→I | CRITICAL 96% | Confirms Blue Team cycle gate blind spot |
| sink_with_outflow (original) | 3 corp inflows + 3 outflows | No fraud detected | First confirmed evasion June 5 |
| slow_bipartite | 6 senders → 1 collector | Detected | Fan-in obvious regardless of sender count |
| mule_warmup_graph | 30-day warmup + spike | Detected | Week-4 layering chain too obvious |

**Why 3→1→2 structure evades TGEP:**
- No circular paths → cycle detector silent
- Max 2 outflows → below fan-out threshold
- No linear chain → mule chain detector silent
- No split-recombine → layering detector silent
- No repeated amounts → structuring detector silent
- 5-14% outflow/inflow ratio → looks like legitimate business

---

## 5. The 22 Mutations

**Group 1 — 10 single-feature mutations:**

| Mutation | Feature Changed | Blue Team Target |
|---|---|---|
| threshold_amount_50k | amount_series_score ×0.92 | Structuring below ₹50K |
| threshold_amount_100k | amount_vs_threshold_100000 | Structuring below ₹1L |
| threshold_amount_1m | amount_vs_threshold_1000000 | PMLA reporting threshold |
| timing_day | night_txn_ratio 0.95→0.15 | Senior+night ×1.50 multiplier |
| velocity_20pct | burst_score -20%, velocity_ratio -0.76 | Burst gate Tier 1 |
| velocity_30pct | burst_score -28%, velocity_ratio -1.14 | Burst gate Tier 1 |
| velocity_40pct | burst_score -37%, velocity_ratio -1.52 | Burst gate Tier 1 |
| context_festival | is_festival_period=1 | Festival ×0.70 multiplier |
| context_senior | night_txn_ratio→0 | Senior night exemption |
| novelty_zero | counterparty_novelty=0 | Bipartite gate Tier 2 |

**Group 2 — 6 compound mutations (3+ features simultaneously):**

| Mutation | Features Changed | Strategy |
|---|---|---|
| compound_daytime_slowdown | night_txn_ratio, burst_score, velocity_ratio, channel_entropy | Daytime disguise + velocity reduction |
| compound_structuring_ghost | amount_series_score, counterparty_novelty, txn_count_30d | Structuring + ghost payee |
| compound_festival_layering | is_festival_period, velocity_ratio, burst_score, night_txn_ratio | Festival multiplier + slow velocity |
| compound_mule_warmup | dormancy_reactivation_flag, txn_count_30d, avg_txn_amount_30d | Warmup phase mimicry |
| compound_kyc_ghost | kyc_completeness_score, counterparty_novelty, geography_switch | Clean KYC + known payee |
| compound_senior_festival_night | night_txn_ratio, is_festival_period, payee_vpa_age_days | Stack senior + festival multipliers |

**Group 3 — 6 tier-aware compound mutations:**

| Mutation | Tiers Targeted | Combined Multiplier |
|---|---|---|
| compound_full_bypass | Tier 1 + Tier 2 all 5 gates + Tier 3 context | Maximum evasion |
| compound_clean_salary_profile | Tier 2 salary advance legitimacy filter | Salary mule bypass |
| compound_treasury_ghost | Tier 2 internal/treasury filter | Treasury transfer bypass |
| compound_gig_rural_festival | Tier 3 context stack | ×0.70 × ×0.85 × ×0.75 = ×0.446 |
| compound_jandhan_first_timer | Tier 3 Jan Dhan ×0.65 | First-time digital payment |
| compound_low_slow_warmup | Tier 2 dormancy + cash mule | 45-day warmup mimicry |

---

## 6. Blue Team Tier Bypass Strategy

How `compound_full_bypass` defeats each tier:

| Tier | Detection Method | Red Team Bypass |
|---|---|---|
| Tier 1 (5ms) | amount_zscore, night_txn_ratio, burst_score, velocity_ratio, channel_switch, geography_switch | Clamp all to safe ranges: zscore<1.5, night<0.10, burst<0.30, velocity<1.3, switches=0 |
| Tier 2 (15ms) | 5 hard gates: cycle/sink/bipartite/cash_mule_sink/merchant_terminal | cycle_membership=0 + 9-hop chain; sink: fan_out_ratio=2.5; bipartite: max 6 senders; mule: dormancy_break=0; terminal: channel_entropy=0.8 |
| Tier 3 (30ms) | XGBoost 59 features, fraud mean 0.787 | Stack ×0.70 × ×0.85 × ×0.75 = ×0.446 combined multiplier → reduces 0.787 to ~0.35 |
| Isolation Forest | 17 structural features, silent novelty sensor | vary_structural_fingerprint() adds ±0.03-0.07 noise to all 17 features per mutation — no two identical fingerprints |

---

## 7. 16 Fraud Archetypes (BAF NeurIPS 2022)

All archetype seeds derived from 11,029 confirmed fraud rows (KMeans n=16 on BAF NeurIPS 2022 Base.csv, 1M rows total).

| Archetype | Cluster Size | Key Features | Avg Amount |
|---|---|---|---|
| account_takeover | 1,646 | channel_switch, burst_score, dormancy_reactivation | ₹7,50,000 |
| sim_swap | 1,372 | distinct_counterparties_30d, dormancy_break, night | ₹4,50,000 |
| pig_butchering | 891 | account_age_days, temporal_acceleration | ₹1,000 → large exit |
| digital_arrest | 882 | night_txn_ratio 0.95, payee_vpa_age_days 1 day | ₹8,50,000 |
| cash_in_mule | 864 | cash_mule_sink_score 0.9, channel_switch | ₹3,00,000 |
| investment_fraud | 738 | avg_txn_amount, channel_switch | ₹10,000 recurring |
| structuring | 323 | amount_series_score 0.91, amount_vs_threshold 0.95 | ₹47,000 |
| merchant_terminal | 517 | distinct_counterparties, txn_count_90d | ₹80,000 |
| romance_scam | 421 | escalating txn_amount, counterparty_novelty | ₹5K→₹5L |
| otp_fraud | 438 | burst_score, dormancy_reactivation | ₹4,00,000 |
| bipartite_mule | 562 | bipartite_score 0.95, fan_out_ratio 5.0 | ₹1,50,000 |
| salary_mule | 410 | sink_score 0.9, return_ratio 0.01 | ₹40,000 |
| ghost_node_cash | 444 | geography_switch, dormancy_reactivation | ₹3,50,000 |
| cycle_round_trip | 597 | cycle_membership=1, return_ratio 0.95 | ₹85,000 |
| rapid_layering | 586 | fan_out_ratio 3.2, temporal_acceleration 0.47 | ₹1,45,000 |
| low_slow_mule | 338 | txn_count_30d=1, very low everything | ₹25,000 |

---

## 8. API Reference

All routes except `/health` require `X-API-Key` header.
Rate limit: 500/minute on `POST /red-team/ingest`.

| Endpoint | Auth | Returns | Notes |
|---|---|---|---|
| `POST /red-team/ingest` | X-API-Key | 202 ingest_id · priority · queued_for | 503 on queue full · 409 on duplicate |
| `GET /red-team/report/{id}` | X-API-Key | Full evasion analysis for one ingest | 202 if still processing |
| `GET /red-team/evasions` | X-API-Key | Paginated KB, filterable | severity · archetype · gate · limit · offset |
| `GET /red-team/briefing` | X-API-Key | Plain English developer intelligence | Works offline — structural analysis when shadow scorer unavailable |
| `GET /red-team/attack-graph/{id}` | X-API-Key | TGEP-format graphs for all 22 mutations | 202 with evasions_so_far while processing |
| `GET /health` | None | `{"status": "ok"}` | |

**Three input signal types (discriminated union on `source_type`):**
- `FRAUD_DNA` — confirmed fraud from Blue Team investigator feedback
- `NOVELTY` — Isolation Forest escalation (10+ same fingerprint in 7 days)
- `GATE_MISS` — investigator-confirmed false negative
- `DATASET` — bulk load from real fraud datasets (BAF NeurIPS, PaySim)

---

## 9. Briefing Output Format

Briefing works even when Blue Team shadow scorer is offline. `mutation_intelligence` section provides structural analysis using BAF-derived seed data regardless of Blue Team connectivity.

```json
{
  "generated_at": "2026-06-25T14:30:00Z",
  "immediate_action_required": [
    {
      "priority": 1,
      "severity": "CRITICAL",
      "title": "Cycle gate blind spot — 9-hop chain evades detection",
      "what_was_found": "graph_bypass_nine_hop_linear mutation on cycle_round_trip archetype bypasses Tier 2 cycle gate. TGEP scores this pattern CRITICAL (96% circular laundering). Blue Team cycle gate only checks 2-8 hop chains.",
      "what_to_change": "Extend cycle_gate.py nightly batch to check up to 10 hops",
      "file": "app/detection/tier2/cycle_gate.py"
    }
  ],
  "structural_findings": [ ... ],
  "mutation_intelligence": {
    "most_effective_mutations": [ ... ],
    "gate_exposure_summary": { ... }
  }
}
```

---

## 10. Security

| Concern | Implementation |
|---|---|
| Authentication | X-API-Key header, timing-safe comparison on all routes |
| PII in logs | sha256(SALT + identifier)[:12] — no raw account IDs stored anywhere |
| Rate limiting | 500/min on POST /red-team/ingest via slowapi (utils/limiter.py) |
| Queue bounds | INGEST_QUEUE_MAX_SIZE=1000 — HTTP 503 when full |
| Self-calls | BLUE_TEAM_SHADOW_URL defaults empty — Red Team never calls itself |
| IF evasion | vary_structural_fingerprint() — 17 features varied ±0.03-0.07 per mutation |
| Golden invariant | Output is developer intelligence only — zero automated enforcement |

---

## 11. How to Run

**Prerequisites:** Python 3.11, Docker Desktop, Git

**Step 1 — Clone:**
```bash
git clone https://github.com/Piyush-072006-B/bling-red-team
cd bling-red-team/red-team
```

**Step 2 — Setup:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Step 3 — Configure:**
```bash
copy .env.example .env
# Set RED_TEAM_API_KEY to something secure
```

**Step 4 — Start:**
```bash
docker-compose up -d
uvicorn app.main:app --reload --port 8002
```
OR from project root:
```powershell
.\start.ps1
```

**Step 5 — Verify:**
Open http://localhost:8002/health
Open http://localhost:8002/docs

**Step 6 — Seed KB with real data:**
```bash
python scripts/bulk_load_seeds.py
```

**Step 7 — Test:**
```bash
pytest tests/ -v  # 155/155
```

---

## 12. Environment Variables

*Note: `TGEP_BASE_URL` and `BLUE_TEAM_SHADOW_URL` should be left empty until teammates provide their service endpoints.*

| Variable | Default | Required? | Description |
|---|---|---|---|
| `RED_TEAM_API_KEY` | `changeme` | Yes | X-API-Key for all protected endpoints |
| `PII_HASH_SALT` | `red-team-salt-changeme` | Yes | SHA-256 PII masking salt |
| `BLUE_TEAM_SHADOW_API_KEY` | *(empty)* | No | Blue Team shadow scorer auth key |
| `BLUE_TEAM_SHADOW_URL` | *(empty)* | No | Blue Team shadow scorer base URL |
| `BLUE_TEAM_INGEST_URL` | `http://localhost:8000/api/v1` | No | Blue Team main API (reference only) |
| `TGEP_BASE_URL` | *(empty)* | No | TGEP backend URL |
| `TGEP_CLEAR_GRAPH_BETWEEN_ATTACKS` | `true` | No | Clear TGEP graph before each new attack |
| `POSTGRES_URL` | `postgresql://...` | No | Deferred post-hackathon |
| `REDIS_URL` | `redis://...` | No | Deferred post-hackathon |
| `INGEST_RATE_LIMIT` | `500/minute` | No | slowapi rate limit on ingest endpoint |
| `INGEST_QUEUE_MAX_SIZE` | `1000` | No | Per-tier queue cap — HTTP 503 when full |
| `SELF_GENERATION_ENABLED` | `true` | No | Auto self-generate 3 archetypes every 5 min |
| `BULK_LOAD_ON_STARTUP` | `false` | No | Inject all 16 seeds automatically at startup |

---

## 13. File Map

- `app/engines/tier_aware_mutations.py` — 3 utility functions + 6 tier-aware compound mutations targeting all 3 Blue Team tiers simultaneously
- `app/engines/fingerprint_vary.py` — varies 17 Isolation Forest structural features ±0.03-0.07 per mutation to prevent fingerprint repetition
- `app/engines/tgep_bypass_graphs.py` — 4 graph bypass patterns using confirmed TGEP-evading 3→1→2 structure
- `app/engines/pre_flight.py` — estimates Tier 1 risk and Tier 2 gate exposure before mutations run
- `app/engines/kb_feedback.py` — Multi-Armed Bandit weight calculation from historical evasion success rates
- `app/engines/seed_library.py` — 16 archetype seeds derived from BAF NeurIPS 2022 (single source of truth)
- `app/engines/self_generator.py` — autonomous generation loop, 3 archetypes every 5 minutes
- `app/outputs/graph_exporter.py` — 17 archetype TGEP graph templates (3→1→2 sink/accumulation, all confirmed undetected)
- `app/outputs/tgep_client.py` — sends graphs to TGEP backend, non-blocking on failure
- `app/outputs/attack_package.py` — assembles complete attack package per evasion, saves JSON to outputs/
- `app/api/attack_graph.py` — GET /red-team/attack-graph/{id}, returns 202 while processing
- `scripts/load_baf_dataset.py` — one-time BAF NeurIPS 2022 loader (KMeans clustering, feature mapping)
- `scripts/bulk_load_seeds.py` — injects all 16 archetype seeds into pipeline on demand
- `scripts/record_findings.py` — formally records 3 confirmed findings into evasion KB
- `scripts/export_all_tgep_graphs.py` — exports all 17 archetype graphs to data/all_tgep_graphs.json

---

## 14. Database Schema

3 tables (schema ready, runtime in-memory for hackathon):
- `ingest_log`
- `evasion_kb`
- `red_team_reports`

**Port assignments (no conflicts):**
- Red Team API: `8002` | Blue Team: `8001` | TGEP backend: `8000` | TGEP frontend: `3000`
- Red Team PostgreSQL: `5433` | Blue Team PostgreSQL: `5432`
- Red Team Redis: `6380` | Blue Team Redis: `6379`

---

## 15. Known Limitations

**WARNING: PROTOTYPE STATUS**
- In-memory only: data lost on server restart
- Shadow scorer offline: all severities show LOW, scores show 0
- TGEP auto-send broken: Vercel URL dead (410 Gone), Render URL needed from teammate
- Postgres schema exists (alembic migrations run) but runtime doesn't persist to DB
- Single process only: not safe for multi-worker deployment

**What works without any teammate connection:**
- Self-generation loop (3 archetypes every 5 minutes)
- All 22 mutations on manual payloads
- Briefing endpoint (structural analysis)
- TGEP-format graph generation (manual paste to TGEP frontend)
- All 155 tests

---

## 16. Integration Guide (for teammates)

**Blue Team needs to add (3 changes):**

1. Call Red Team from `feedback.py` after blockchain seal
```python
import httpx
import os

async def _notify_red_team(confirmed_fraud: dict) -> None:
    url = os.getenv("RED_TEAM_URL", "")
    key = os.getenv("RED_TEAM_API_KEY", "")
    if not url: return
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{url}/red-team/ingest",
                json=confirmed_fraud,
                headers={"X-API-Key": key},
            )
    except Exception:
        pass  # Red Team failure must never affect Blue Team
```
2. Add `POST /api/v1/shadow/score` — read-only, no DB writes, no alerts
3. Add env vars: `RED_TEAM_URL`, `RED_TEAM_API_KEY`

**TGEP needs to add (2 changes):**

1. Provide Render backend URL for `TGEP_BASE_URL`
2. Add `POST /api/red-team/evaluate` endpoint
```json
// Request schema:
{
  "edges": [...],
  "expected_typologies": [...]
}

// Response schema:
{
  "detected": [...],
  "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "confidence": 0.95
}
```

---

## 17. Tech Stack

| Component | Technology |
|---|---|
| Web Framework | FastAPI 0.111 |
| Machine Learning | XGBoost (Blue Team data via BAF), scikit-learn (cosine similarity + KMeans clustering) |
| Utilities | httpx, structlog, slowapi |
| Data | PostgreSQL 15, Redis 7 |
| Environment | Docker + Docker Compose |
| Testing | pytest 155/155 |

---

<div align="center">
BLING Hackathon · BYTEJAYS Team · Red Team · Union Bank of India<br>
Post-transaction adversarial fraud simulation<br>
Developer intelligence only · Never automated blocking<br>
<a href="https://github.com/Piyush-072006-B/bling-red-team">github.com/Piyush-072006-B/bling-red-team</a>
</div>
