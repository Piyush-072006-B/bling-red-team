# HANDOFF.md — Red Team Build State

## STATUS
PHASE: DEPLOYMENT_PENDING
LAST_COMPLETED_TASK: Fixed _apply_delta logic for sparse payloads so missing features injected as 0.0 aren't dropped. Added tests_sparse_payload_mutations.py.
NEXT_TASK: Retest tier-aware mutations against TGEP using real BAF-derived archetype seeds — send digital_arrest ingest, get attack-graph, verify compound_full_bypass graph now uses correct archetype template instead of NEW_VARIANT
BLOCKING_ISSUE: none
TESTS_PASSING: 155/155
DEPLOYMENT_STATUS: PROTOTYPE — single process, in-memory stores, data lost on restart. Persistence deferred post-hackathon.

## COMPLETED_TASKS
### Phase 1 — Setup
- [DONE] Task 1.1 — Initialise HANDOFF.md
- [DONE] Task 1.2 — Scaffold project (full file structure + __init__.py files)
- [DONE] Task 1.3 — Environment files (red-team/.env.example, 6 vars)
- [DONE] Task 1.4 — requirements.txt (18-package pinned list)
- [DONE] Task 1.5 — docker-compose.yml (postgres:15 on 5433, redis:7 on 6380, healthchecks)
- [DONE] Task 1.6 — Database schema (3 tables: ingest_log, evasion_kb, red_team_reports)

### Phase 2 — Implementation
- [DONE] Task 2.1 — Pydantic schemas (FraudDNA + NoveltyEscalation + GateMissLog + discriminated union)
- [DONE] Task 2.2 — Auth (X-API-Key timing-safe) + audit_logger (structlog, hash_id) + config (pydantic-settings)
- [DONE] Task 2.3 — Ingest router (dedup SHA-256, priority, asyncio.Queue)
- [DONE] Task 2.4 — Archetype extractor (cosine sim, 16 signatures, NEW_VARIANT < 0.45) + ml/similarity.py
- [DONE] Task 2.5 — Mutation engine (10 mutations: threshold × 3, timing, velocity × 3, context × 2, novelty_zero)
- [DONE] Task 2.6 — Graph adversary (5 gates: cycle=9-hop, sink=outflow, bipartite=4+3, cash_mule=48h, merchant=2-POS)
- [DONE] Task 2.7 — Shadow scorer client (httpx, 5s timeout, shadow-only, error dict on failure)
- [DONE] Task 2.8 — Evaluators (gate_probe, feature_sensitivity top-5 SHAP, context_bypass Indian multipliers)
- [DONE] Task 2.9 — Knowledge base store (append-only, severity scoring CRITICAL/HIGH/MEDIUM/LOW)
- [DONE] Task 2.10 — API routes (POST /ingest 202/409, GET /report/{id} 200/404, GET /evasions paginated)
- [DONE] Task 2.11 — FastAPI app (routers, CORS, slowapi 500/min, /health, lifespan logging)

### Phase 3 — Integration
- [DONE] Task 3.1 — Blue Team webhook receiver E2E test (scripts/test_blue_team_webhook.py)
- [DONE] Task 3.2 — TGEP outbound webhook (retry-once, HIGH/CRITICAL only, non-blocking)
- [DONE] Task 3.3 — Shadow scorer connectivity test (scripts/test_shadow_connection.py)

### Phase 4 — Tests
- [DONE] Task 4.1 — test_ingest.py (14 tests: dedup, priority all 3 types, schema, auth)
- [DONE] Task 4.2 — test_mutation.py (12 tests: count, strategies, threshold, velocity, timing, novelty, in-place)
- [DONE] Task 4.3 — test_graph_adversary.py (15 tests: all 5 gates, cycle=9 hops, bipartite 4+3, cash_mule 48h, merchant 2-POS)
- [DONE] Task 4.4 — test_sandbox.py (13 tests: mock scorer, score<0.75, gate_probe, feature_sensitivity, context_bypass)

### Phase 5 — Documentation
- [DONE] Task 5.1 — draw.io flowchart (docs/red_team_architecture.drawio + .svg + .spec.yaml)
- [DONE] Task 5.2 — README.md (architecture, quickstart, API reference, security, archetypes, gates, integration contract)

### Phase 6 — Background Worker
- [DONE] Task 6.1 — app/worker/pipeline.py (FRAUD_DNA / NOVELTY / GATE_MISS pipelines, priority queue consumer, asyncio.Task)
- [DONE] Task 6.2 — router.py: added update_ingest_status() (QUEUED → IN_PROGRESS → COMPLETED | FAILED)
- [DONE] Task 6.3 — main.py: worker_loop started in lifespan, gracefully cancelled on shutdown
- [DONE] Task 6.4 — tests/test_worker.py (18 tests: status helper, FRAUD_DNA, NOVELTY, GATE_MISS, loop E2E)

### Phase 7 — Briefing Endpoint
- [DONE] Task 7.1 — app/api/briefing.py (GET /red-team/briefing — severity grouping, plain English fix copy, feature frequency, context multiplier tracking)
- [DONE] Task 7.2 — main.py: briefing router registered
- [DONE] Task 7.3 — tests/test_briefing.py (22 tests: empty KB, mixed severity, item structure, feature ranking, multiplier dedup)

### Phase 8 — Hardening (8-issue pass)
- [DONE] Issue 1 — pipeline.py: _build_report_for_tgep() derives real severity+action from KB rows; TGEP fires only for HIGH/CRITICAL+PATCH
- [DONE] Issue 2 — router.py: _sanitize_payload() hashes account_id/transaction_id/fingerprint_id/alert_id before storing in ingest_log
- [DONE] Issue 3 — app/utils/limiter.py created; @limiter.limit applied to POST /red-team/ingest; circular import eliminated
- [DONE] Issue 4 — WARNING comment added to router.py and kb_store.py; README + HANDOFF updated re: in-memory limitation
- [DONE] Issue 5 — INGEST_QUEUE_MAX_SIZE added to config; bounded queues; QueueFullError raises HTTP 503; log+dedup rolled back on full
- [DONE] Issue 6 — blue_team_shadow_url default = ""; shadow_scorer.py returns null immediately when unconfigured
- [DONE] Issue 7 — tests/test_tgep_contracts.py (20 tests: report shape, severity gating, maybe_fire_tgep, fire_tgep LOW/MEDIUM skip)
- [DONE] Issue 8 — HANDOFF + README updated with PROTOTYPE status, 124/124 test count, in-memory known blocker

### Phase 9 — Local Convenience Scripts
- [DONE] Task 9.1 — start.ps1 (docker-compose up -d, 5s wait, activate venv, uvicorn :8002, open /docs in browser)
- [DONE] Task 9.2 — stop.ps1 (kill port 8002, docker-compose down, print clean stop)

## IN_PROGRESS
(none)

## PENDING_TASKS
(none — all tasks complete)

## KEY_FILES
- red-team/README.md
- red-team/app/main.py
- red-team/app/ingest/schemas.py
- red-team/app/ingest/router.py
- red-team/app/engines/archetype_extractor.py
- red-team/app/engines/mutation_engine.py
- red-team/app/engines/graph_adversary.py
- red-team/app/engines/tier_aware_mutations.py
- red-team/app/engines/fingerprint_vary.py
- red-team/app/engines/tgep_bypass_graphs.py
- red-team/app/outputs/graph_exporter.py
- red-team/app/outputs/tgep_client.py
- red-team/app/outputs/attack_package.py
- red-team/app/sandbox/shadow_scorer.py
- red-team/app/sandbox/evaluators.py
- red-team/app/knowledge/kb_store.py
- red-team/app/api/ingest.py
- red-team/app/api/report.py
- red-team/app/api/evasions.py
- red-team/app/api/briefing.py
- red-team/app/api/attack_graph.py
- red-team/app/utils/limiter.py
- red-team/app/worker/pipeline.py
- red-team/app/worker/pre_flight.py
- red-team/app/engines/seed_data.py
- red-team/app/engines/seed_library.py
- red-team/app/engines/self_generator.py
- red-team/docs/red_team_architecture.drawio
- red-team/docs/red_team_architecture.svg
- red-team/scripts/test_blue_team_webhook.py
- red-team/scripts/test_shadow_connection.py
- red-team/tests/test_ingest.py
- red-team/tests/test_mutation.py
- red-team/tests/test_graph_adversary.py
- red-team/tests/test_sandbox.py
- red-team/tests/test_worker.py
- red-team/tests/test_briefing.py
- red-team/tests/test_security_and_queues.py
- red-team/tests/test_tgep_contracts.py
- red-team/tests/test_tier_bypass.py
- red-team/tests/test_attack_package.py
- red-team/tests/test_seed_library.py
- start.ps1
- stop.ps1

## INTEGRATION_STATUS
BLUE_TEAM_SHADOW_SCORER_URL: not configured — wiring deferred
BLUE_TEAM_INGEST_CONNECTED: no — wiring deferred
TGEP_WEBHOOK_CONNECTED: no — wiring deferred

## NOTES
- Project root: d:\bling-red-team
- Red Team files: d:\bling-red-team\red-team\
- Local server tested and working on port 8002
- All 129 tests pass (129/129). Service is production-ready for Railway deployment.
- DEPLOYMENT_STATUS: PROTOTYPE — single process, in-memory stores, data lost on restart.
- KNOWN BLOCKER (post-hackathon): Postgres/Redis persistence not yet wired — all data ephemeral.
- 3 TGEP test results saved: digital_arrest=HIGH, 9hop_cycle=CRITICAL, bipartite=HIGH
- 3 patch proposals identified: cycle gate 9+ hops, senior+night secondary trigger, bipartite threshold 0.55
- Shadow scorer returns null (expected — Blue Team not local)
- Archetype showing NEW_VARIANT (expected — sparse feature vector, only 26/59 features sent)
- Ports: Red Team API=8002, PostgreSQL=5433, Redis=6380
- DB in v1 uses in-memory stores. Postgres wiring is the next natural step (Phase 3 extension).
- slowapi rate limit: 500/min on POST /red-team/ingest
- Do not run docker-compose down — containers can stay running
- Never call production Blue Team scorer — shadow endpoint only
- Never store raw account IDs — hash with sha256(SALT+account_id)[:12]
- draw.io CLI requires js-yaml — installed in .agents/skills/drawio/scripts/node_modules/
- Fixed structlog PrintLogger incompatibility by switching to structlog.stdlib.LoggerFactory().
- Cleaned up .env by removing inline comments.
- Performed project cleanup (removed __pycache__, .pytest_cache, and .arch.json).
- Implemented background worker pipeline (app/worker/pipeline.py) — 72/72 tests passing.
- Worker uses asyncio.Task (no Celery). Failed items marked FAILED in ingest_log, no retries.
- Implemented GET /red-team/briefing (app/api/briefing.py) — 94/94 tests passing.
- Issue 1: pipeline.py TGEP webhook now derives severity from real KB rows.
- Issue 2: PII sanitization — raw IDs hashed before ingest_log storage.
- Issue 3: Rate limiter moved to app/utils/limiter.py; applied to POST /ingest.
- Issue 4: WARNING comments added to router.py + kb_store.py re in-memory limitation.
- Issue 5: Bounded queues (INGEST_QUEUE_MAX_SIZE); QueueFullError → HTTP 503.
- Issue 6: blue_team_shadow_url default=""; shadow_scorer.py short-circuits if unconfigured.
- Issue 7: Contract tests for TGEP webhook (20 tests in test_tgep_contracts.py).
- Issue 8: HANDOFF + README updated with PROTOTYPE status, 124/124 count.
- start.ps1: docker-compose up -d → 5s wait → venv activate → uvicorn :8002 → opens /docs
- stop.ps1: kills port 8002 → docker-compose down → prints "Red Team stopped cleanly"
- Fixed PydanticUndefinedAnnotation: removed `from __future__ import annotations` from app/api/ingest.py (deferred annotations broke Pydantic discriminated-union resolution at startup)
- Added `mutation_intelligence` to `GET /red-team/briefing` so it produces structural analysis (top features, multipliers tested, plain English recs) even when shadow scorer is offline (all severities LOW).
- Renamed the 'accepted' bucket to 'structural_findings' in `GET /red-team/briefing` to better reflect that these are real patterns requiring review when the shadow scorer is offline.
- Created `.gitignore` in `red-team/` to exclude `venv/`, `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `.eggs/`, `htmlcov/`, and `.coverage`.
- Copied `red-team/README.md` to `D:\bling-red-team\README.md` (project root) to ensure the documentation is immediately visible at the top level of the repository.
- When returning: type "continue" → agent reads this file → starts Railway deployment
- GOLDEN INVARIANT PRESERVED: Red Team output is developer intelligence, not automated blocking.
- Added context management, mutation strength, and skill activation rules to red-team/AGENTS.md
- Applied updated architecture proposal: port changed to 8002, BLUE_TEAM_SHADOW_API_KEY added, TGEP bidirectional webhook integrated with KB fields.
- Added 6 compound mutations to simulate sophisticated attackers (daytime_slowdown, structuring_ghost, festival_layering, mule_warmup, kyc_ghost, senior_festival_night).
- Updated file length rule in `AGENTS.md` to allow 400 lines for engine files (`mutation_engine.py`, `graph_adversary.py`, `pipeline.py`).
- Implemented 3-tier bypass + Isolation Forest evasion. Added `tier_aware_mutations.py` and `tgep_bypass_graphs.py`.
- `mutation_engine.py` now runs 22 mutations (10 single, 6 old compound, 6 tier-aware) per signal, applying `vary_structural_fingerprint` to all.
- Pipeline now runs a pre-flight tier check (logged via structlog) before mutations.
- TGEP bypass graphs are now stored in `evasion_kb` with `mutation_type="graph_bypass_{evasion_type}"`.
- All 139 tests passing (`test_tier_bypass.py` added).
- Replaced output architecture: pipeline now builds attack packages (graph_exporter → tgep_client) per evasion.
- NEW: `app/outputs/graph_exporter.py` — 17 archetype-specific TGEP graph templates.
- NEW: `app/outputs/tgep_client.py` — async TGEP client (send_to_tgep, request_evidence, get_tgep_verdict, clear_tgep_graph).
- NEW: `app/outputs/attack_package.py` — assembles per-evasion attack package and writes JSON file to outputs/.
- NEW: `app/api/attack_graph.py` — GET /red-team/attack-graph/{ingest_id} endpoint.
- UPDATED: `config.py` — TGEP_BASE_URL + TGEP_CLEAR_GRAPH_BETWEEN_ATTACKS replace old webhook URL.
- UPDATED: `.env.example` — new TGEP settings documented.
- UPDATED: `.gitignore` — outputs/ directory excluded.
- UPDATED: `kb_store.py` — added tgep_graph + tgep_response fields to evasion rows.
- UPDATED: `pipeline.py` — per-evasion attack package build + TGEP send (non-blocking) replaces fire-and-forget webhook.
- All 145 tests passing (`test_attack_package.py` added with 5 tests).
- SELF_GENERATION: enabled, 5-minute intervals, 3 archetypes per cycle.
- Seed library provides 16 realistic feature vectors (59 features each) from BAF NeurIPS 2022 + PaySim statistics.
- NEW: `app/engines/seed_data.py` — 16 archetype seed vectors, each with all 59 Blue Team features.
- NEW: `app/engines/seed_library.py` — get_seed, get_all_seeds, get_seed_with_variation (±noise on numeric features, binary flags preserved).
- NEW: `app/engines/self_generator.py` — run_self_generation_cycle + start_self_generation_loop (asyncio task, backpressure at 50 pending).
- NEW: `app/ingest/schemas.py` — DatasetRecord (source_type="DATASET") added to discriminated union, routes through FRAUD_DNA pipeline.
- UPDATED: `config.py` — SELF_GENERATION_ENABLED, SELF_GENERATION_INTERVAL_SECONDS, SELF_GENERATION_ARCHETYPES_PER_CYCLE.
- UPDATED: `main.py` — self_gen_task started in lifespan alongside worker_task, cancelled on shutdown.
- UPDATED: `pipeline.py` — DATASET source_type routes to _pipeline_fraud_dna.
- UPDATED: `router.py` — DATASET gets HIGH priority, dataset_name+original_record_id dedup.
- All 151 tests passing (`test_seed_library.py` added with 6 tests).
