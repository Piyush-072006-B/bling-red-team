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
| Red Team API         | 8002 |
| Red Team PostgreSQL  | 5433 |
| Red Team Redis       | 6380 |
| Blue Team API        | 8000 |
| Blue Team PostgreSQL | 5432 |
| Blue Team Redis      | 6379 |

## CONTEXT MANAGEMENT RULES
1. Before writing any new code, read the existing file first
2. Before adding any import, check if it already exists in the file
3. Before creating any new function, search for similar functions in the codebase
4. Maximum function length: 40 lines. If longer, split it
5. Maximum file length: 400 lines for engine files (mutation_engine.py, graph_adversary.py, pipeline.py). 200 lines for all other files. If any engine file exceeds 400 lines, split by grouping related functions into a helper module (e.g. mutation_helpers.py) — never truncate logic.
6. After every task, summarize what changed and why in HANDOFF.md
7. Never duplicate logic that exists elsewhere — find and import it instead

## MUTATION STRENGTH RULES
8. Single-feature mutations are weak. Every archetype must have at least 
   2 compound mutations changing 3+ features simultaneously
9. Compound mutations must be realistic — features a real attacker would 
   change together, not random combinations
10. Compound mutation naming: prefix with compound_ 

## SKILL ACTIVATION HINTS
- For any mutation or ML work: use machine-learning-ops-ml-pipeline 
  and data-scientist skills
- For any cleanup or refactor: use code-refactoring-refactor-clean 
  and clean-code skills
- For context restore at session start: use code-refactoring-context-restore
