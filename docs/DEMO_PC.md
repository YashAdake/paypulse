# Demo PC: bring-up and debugging

Everything was written on a laptop without Docker. Python unit tests, lint and static
checks passed there; **nothing has run in Docker yet**. This page gets the stack running
on the demo PC and gives Claude Code the context to debug it.

## 1. Prepare (once)

```powershell
git clone https://github.com/YashAdake/paypulse.git
cd paypulse
git switch feature/phase-2
Copy-Item .env.example .env
notepad .env    # set LLM_API_KEY (Jarvislabs) and, if you have one, SUPERMEMORY_API_KEY
```

## 2. Start Claude Code in the repo and paste this prompt

```text
You are on the PayPulse demo PC (Windows, Docker Desktop available). Read CLAUDE.md,
README.md and docs/DEMO_PC.md first. We are on branch feature/phase-2, which contains
Phases 0-5 plus the Command Center UI. All of it was written on a laptop without Docker:
Python unit tests (48), ruff and static checks passed there, but nothing has been built
or run in Docker yet. Your job is to get the full demo working end to end, fast.

Do this in order, fixing problems as you find them (small, focused fixes; commit each
fix with a clear message; push to feature/phase-2 only when I say "push"):

1. Check .env exists and LLM_API_KEY is set (never print its value, never commit .env).
2. docker compose up --build -d, then docker compose ps. Fix any build failure
   (the ui build runs `tsc --noEmit` first, so TypeScript errors show up there).
3. Verify each service: payment-service /healthz (8080), api /api/status (8000),
   Command Center (3000), Temporal UI (8233). Read `docker compose logs <service>`
   for anything unhealthy. Known risk areas, none run before:
   - payment-service SQL in app/services/stats.py (/stats/timeseries, /stats/breakdown)
   - worker: Temporal sandbox imports, @workflow.init, dataclass conversion
   - api: list_workflows / query / signal against the Temporal dev server
   - ui: nginx proxy to api, TypeScript build, recharts/lucide imports
4. If SUPERMEMORY_API_KEY is set: docker compose run --rm memory-seed
5. Run the demo flow from README "Demo script": inject HDFC timeouts 60% (via the UI
   or POST /chaos), confirm an incident opens within ~15 s (docker compose logs -f worker),
   steps progress, the AI root cause appears, approve via the UI or
   POST http://localhost:8000/api/incidents/incident-HDFC/decision {"approved": true},
   recovery verifies, incident ends "resolved".
6. Report what you fixed and what still needs attention. Keep scope tight: no new
   features, no refactors, just make the demo work.
```

## 3. Useful commands

```powershell
docker compose ps
docker compose logs -f worker
docker compose logs --tail 100 api ui payment-service
docker compose up --build -d worker      # rebuild one service after a fix
docker compose down -v                   # full reset (wipes the database)
```

## Expected behaviour

| Step | What you should see |
|---|---|
| Startup | All services up; Command Center shows 4 banks green, ~98% |
| Inject HDFC 60% timeouts | HDFC tiles turn red, ~39%, top error BANK_TIMEOUT, p95 ~10 s |
| ~10-15 s later | Worker log `incident opened`; incident appears in the UI |
| Investigation | Evidence → memory → AI root cause (a few seconds) → waiting for approval |
| Approve | Runbook clears the fault, recovery checks turn green within ~30 s, "Resolved in N s" |

Without SUPERMEMORY_API_KEY the memory steps say "not configured" and the rest still works.
