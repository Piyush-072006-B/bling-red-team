# AGENTS.md — Red Team Service
# Antigravity Operating Rules (committed)

## Identity
This is the Red Team adversarial simulation engine for BLING / Union Bank of India.
It runs alongside the Blue Team (BLING forensic fraud detection) as a fully separate service.
Integration is API-only. Red Team never touches Blue Team code or database directly.

## Golden Invariant
Red Team output is **developer intelligence**, not automated blocking.
Every output is a proposal for a human to act on.

## Session Protocol
1. Always read `HANDOFF.md` first at the start of every session.
2. Always update `HANDOFF.md` last before ending any session.
3. On "continue": read HANDOFF.md → resume from NEXT_TASK exactly.
4. Never delete or overwrite HANDOFF.md. Only append/update fields.
5. Never create files outside the defined file structure (add to NEW_FILES_ADDED if needed).
6. Never touch Blue Team code.
7. Mark every completed task [DONE] in HANDOFF.md, set NEXT_TASK.
8. Run `pytest tests/ -v` after every module built. Record pass/fail in HANDOFF.md.

## What Red Team Must Never Do
- Never call `POST /api/v1/score` (production Blue Team scorer)
- Never write to Blue Team's database
- Never block or delay Blue Team's feedback pipeline
- Never auto-apply patches — only propose them
- Never store raw account IDs or VPAs — hash: `sha256(SALT + account_id)[:12]`

## Ports
| Service              | Port |
|----------------------|------|
| Red Team API         | 8001 |
| Red Team PostgreSQL  | 5433 |
| Red Team Redis       | 6380 |
| Blue Team API        | 8000 |
| Blue Team PostgreSQL | 5432 |
| Blue Team Redis      | 6379 |
