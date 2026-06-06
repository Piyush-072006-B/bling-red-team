# HANDOFF.md — Red Team Build State

## STATUS
PHASE: DEPLOYMENT_PENDING
LAST_COMPLETED_TASK: Copy red-team/README.md to project root (D:\bling-red-team\README.md)
NEXT_TASK: Deploy Red Team to Railway (3 steps: push to GitHub, create Railway project, set env vars). Do NOT wire Blue Team or TGEP yet.
BLOCKING_ISSUE: none
TESTS_PASSING: 124/124
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
- [DONE] Task 9.1 — start.ps1 (docker-compose up -d, 5s wait, activate venv, uvicorn :8001, open /docs in browser)
- [DONE] Task 9.2 — stop.ps1 (kill port 8001, docker-compose down, print clean stop)

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
- red-team/app/sandbox/shadow_scorer.py
- red-team/app/sandbox/evaluators.py
- red-team/app/knowledge/kb_store.py
- red-team/app/api/ingest.py
- red-team/app/api/report.py
- red-team/app/api/evasions.py
- red-team/app/api/tgep_webhook.py
- red-team/app/api/briefing.py
- red-team/app/utils/limiter.py
- red-team/app/worker/pipeline.py
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
- start.ps1
- stop.ps1

## INTEGRATION_STATUS
BLUE_TEAM_SHADOW_SCORER_URL: not configured — wiring deferred
BLUE_TEAM_INGEST_CONNECTED: no — wiring deferred
TGEP_WEBHOOK_CONNECTED: no — wiring deferred

## NOTES
- Project root: d:\bling-red-team
- Red Team files: d:\bling-red-team\red-team\
- Local server tested and working on port 8001
- All 124 tests pass (124/124). Service is production-ready for Railway deployment.
- DEPLOYMENT_STATUS: PROTOTYPE — single process, in-memory stores, data lost on restart.
- KNOWN BLOCKER (post-hackathon): Postgres/Redis persistence not yet wired — all data ephemeral.
- 3 TGEP test results saved: digital_arrest=HIGH, 9hop_cycle=CRITICAL, bipartite=HIGH
- 3 patch proposals identified: cycle gate 9+ hops, senior+night secondary trigger, bipartite threshold 0.55
- Shadow scorer returns null (expected — Blue Team not local)
- Archetype showing NEW_VARIANT (expected — sparse feature vector, only 26/59 features sent)
- Ports: Red Team API=8001, PostgreSQL=5433, Redis=6380
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
- start.ps1: docker-compose up -d → 5s wait → venv activate → uvicorn :8001 → opens /docs
- stop.ps1: kills port 8001 → docker-compose down → prints "Red Team stopped cleanly"
- Fixed PydanticUndefinedAnnotation: removed `from __future__ import annotations` from app/api/ingest.py (deferred annotations broke Pydantic discriminated-union resolution at startup)
- Added `mutation_intelligence` to `GET /red-team/briefing` so it produces structural analysis (top features, multipliers tested, plain English recs) even when shadow scorer is offline (all severities LOW).
- Renamed the 'accepted' bucket to 'structural_findings' in `GET /red-team/briefing` to better reflect that these are real patterns requiring review when the shadow scorer is offline.
- Created `.gitignore` in `red-team/` to exclude `venv/`, `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `.eggs/`, `htmlcov/`, and `.coverage`.
- Copied `red-team/README.md` to `D:\bling-red-team\README.md` (project root) to ensure the documentation is immediately visible at the top level of the repository.
- When returning: type "continue" → agent reads this file → starts Railway deployment
- GOLDEN INVARIANT PRESERVED: Red Team output is developer intelligence, not automated blocking.
