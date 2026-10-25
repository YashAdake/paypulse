# PayPulse handoff: full context for the debugging session

Read this before touching anything. It is everything the build session knew: what
PayPulse is, how the pieces fit, what has been verified, what has never run, and where
bugs are most likely. Also read [CLAUDE.md](../CLAUDE.md) (project rules) and
[DEMO_GUIDE.md](DEMO_GUIDE.md) (the owner's step-by-step).

---

## 1. Goal right now

Get the **full demo working end to end on the demo Mac**, then rehearse it.

Demo story: inject HDFC timeouts → PayPulse detects the drop → investigates (SQL evidence,
Supermemory recall, Jarvislabs LLM root cause) → waits for a human → human clicks
Approve in the Command Center → runbook fixes it → recovery verified → postmortem saved
to memory. Every partner (Temporal, Supermemory, Jarvislabs, Kepler) must be visibly
credited in the UI where it does its job.

Scope: **make it work, don't extend it.** Small, focused fixes only.

## 2. Working rules (from the owner)

- Demo machine: **macOS, zsh, Docker Desktop**. Give commands for zsh, never PowerShell.
- **Commit each fix** with a clear message (end messages with the Co-Authored-By line the
  harness gives you). **Push only when the owner says "push"**. Branch: `feature/phase-2`.
  Merge to `main` only after the demo works.
- **Never print or commit API keys.** `.env` is gitignored; the repo is **public**.
- Report facts vs guesses. If something is unverified, say so.
- Keep code style: small modules, type hints, comments explain *why*, pydantic models,
  JSON logs, maths in SQL, all I/O in Temporal activities, idempotent actions.
- Owner is short on time: prefer the smallest fix that makes the demo work.

## 3. State of the code

Branch `feature/phase-2` contains Phases 0-5 plus the Command Center UI. It was written
on a Windows laptop **without Docker** (and without Node).

| Verified | How |
|---|---|
| payment-service core (/pay, /chaos, /stats, /deploys, traffic, idempotency, errors) | Ran against a real Postgres 16 locally: HDFC dropped to 0.29-0.45 with BANK_TIMEOUT, p95 ~10.2 s, other banks 0.94-1.0; idempotency 201/200/409; 20 rps pacing exact |
| Python unit tests: 48 pass | `payment-service/tests` (14), `worker/tests` (34); ruff clean |
| Temporal SDK usage | Every call checked against temporalio 1.34.0 source; `_Definition.from_class(InvestigateIncident)` validates; IncidentInput / Progress / ApprovalDecision round-trip through the default data converter |
| api + payment-service app construction | Both build OpenAPI with all routes |
| Jarvislabs LLM | Real call: valid JSON, correct diagnosis, ~1.2 s, model spends hidden reasoning tokens |
| Supermemory | Real calls with the owner's key: 3 seed docs loaded (container tag `paypulse-incidents`); the worker's actual `recall_memory` code returns the Aug-12 HDFC incident first (similarity 0.763) |
| Docker images / wheels | All have linux/arm64 builds (Apple Silicon OK) |

| **Never run** | Risk |
|---|---|
| Any Docker build or `docker compose up` | Build errors, healthchecks |
| UI TypeScript build (`tsc --noEmit && vite build`) | **Highest risk.** Never compiled. No package-lock.json (generated on first build) |
| `/stats/timeseries`, `/stats/breakdown` SQL | Written, not executed |
| worker ↔ Temporal dev server (start, activities, query, signal, timers) | Sandbox / serialization surprises |
| api ↔ Temporal (`list_workflows`, query, signal) | Visibility query on dev server |
| nginx proxy `/api` → api | Docker DNS resolver config |

## 4. Architecture

```
traffic generator ─► payment-service (FastAPI, :8080) ─► Postgres 16 (:5432)
                          ▲  /chaos breaks a bank on purpose
                          │
worker (python -m app.main)
  ├─ detector: polls /stats every 5 s; bank+method < 90% with ≥20 payments in 60 s
  │            → start workflow id "incident-<BANK>" (one running per bank)
  └─ Temporal worker, task queue "paypulse": InvestigateIncident + 7 activities
                          │
Temporal dev server (:7233 gRPC, :8233 UI), in-memory
                          │
api (FastAPI, :8000) ─ list/query/signal workflows; relays stats + chaos ─┐
ui (React build served by nginx, host :3000 → container :8080) ─ /api/* ──┘
memory-seed (compose profile "tools"): loads memory-seed/*.md into Supermemory
```

Workflow steps (worker/app/workflows.py), each recorded in `Progress`:

| # | Step key | Activity / mechanism | Tech badge |
|---|---|---|---|
| 1 | gather_evidence | `GET /stats/breakdown?bank=` + `GET /deploys` | Postgres SQL |
| 2 | recall_memory | Supermemory `POST /v4/search` (non-critical) | Supermemory |
| 3 | analyze_root_cause | LLM `POST /chat/completions`, JSON mode, validated | Jarvislabs |
| 4 | notify | log + mark posted | Command Center |
| 5 | await_approval | `wait_condition` on signal `submit_decision`, 900 s timeout | Temporal signal |
| 6 | run_runbook | `DELETE /chaos/{bank}` (= "restart_bank_connector") | Temporal activity |
| 7 | verify_recovery | `check_bank_health` every 10 s, ≤12 checks, ≥93% and ≥10 payments in 20 s | Temporal timers |
| 8 | save_memory | Supermemory `POST /v3/documents`, customId `paypulse-<run_id>` (non-critical) | Supermemory |

Outcomes (`IncidentStatus`): resolved, unresolved, rejected, expired, escalated (LLM chose
`escalate`), failed (a critical step failed → workflow raises ApplicationError).

## 5. Repo map

```
CLAUDE.md                 project rules
docker-compose.yml        postgres, temporal, payment-service, worker, api, ui, memory-seed
.env.example              all env vars; real keys only in .env
payment-service/app/
  main.py                 lifespan: wait for DB → pool → schema.sql → traffic task
  db.py, schema.sql       psycopg 3 async pool, timeouts, idempotent schema
  domain.py               stdlib enums (Bank, Method, ChaosType, ErrorCode)
  models.py               pydantic schemas (incl. Timeseries*, Breakdown*)
  services/simulator.py   PURE outcome logic (chaos first, then 98% baseline)
  services/stats.py       ALL stats SQL: /stats, /stats/timeseries, /stats/breakdown
  services/{payments,chaos,deploys,traffic}.py
  routes/*.py             thin HTTP layer
  log.py, middleware.py, errors.py   JSON logs, X-Request-ID, uniform JSON errors
worker/app/
  contracts.py            dataclasses passed through Temporal + shared name constants
  progress.py             PURE Progress/Step state the UI reads via query
  detection.py            PURE find_triggers / may_open_incident
  rca.py, masking.py, runbooks.py, notes.py   PURE prompt+parse, masking, allow-list, texts
  activities.py           all HTTP side effects (payment-service, LLM, Supermemory)
  workflows.py            InvestigateIncident (deterministic)
  detector.py             polling loop; asks Temporal (describe) for running/cooldown
  main.py                 connects Temporal (retry), runs Worker + detector, SIGTERM
  seed_memory.py          one-off Supermemory loader
api/app/
  routes/live.py          GET /api/live (stats+timeseries+chaos), POST/DELETE /api/chaos
  routes/incidents.py     GET /api/incidents, GET /api/incidents/{id}?run_id=, POST .../decision
  routes/health.py        GET /api/healthz (liveness), GET /api/status (partner strip)
  payment_service.py, temporal.py, errors.py, models.py, main.py
ui/
  Dockerfile              node:24 build (npm install, tsc, vite) → nginx-unprivileged
  nginx.conf              resolver 127.0.0.11; /api/ → http://api:8000; SPA fallback
  src/api.ts              TS types mirroring api + Progress; fetch helpers
  src/usePoll.ts          poll-after-response hook
  src/App.tsx             layout; follows newest incident
  src/panels/             PoweredBy, LivePayments, DemoControls, IncidentList, IncidentDetail
memory-seed/*.md          3 fake postmortems (HDFC Aug-12 is the one recall should find)
```

**Name contract:** `WORKFLOW_TYPE="InvestigateIncident"`, query `"get_progress"`, signal
`"submit_decision"` are defined in `worker/app/contracts.py` and duplicated as strings in
`api/app/routes/incidents.py`. Change both together. UI types in `ui/src/api.ts` mirror
`worker/app/progress.py` and `contracts.py`.

## 6. Configuration

Compose passes these to worker and api (anchor `&paypulse-env`): `TEMPORAL_ADDRESS=temporal:7233`,
`PAYMENT_SERVICE_URL=http://payment-service:8080`, `LLM_BASE_URL`, `LLM_MODEL`,
`LLM_API_KEY`, `SUPERMEMORY_API_KEY`, `LOG_LEVEL`.

- LLM: Jarvislabs Token Factory, `https://models.jarvislabs.net/v1`, model
  `deepseek-v4.1-flash-1017`, `max_tokens` 1500 (reasoning tokens count against it).
- Supermemory: `https://api.supermemory.ai`, container tag `paypulse-incidents`,
  search threshold 0.3, `searchMode: "hybrid"`, `include.documents: true`.
  v3/v4 endpoints are deprecated but live until 2026-12-31.
- Tunables in `worker/app/config.py` (`DETECTOR_*`, `APPROVAL_TIMEOUT_S`, ...) and
  `WorkflowSettings` in `contracts.py` (evidence/verify windows).

## 7. Where bugs are most likely, and what to check

**UI build (check first).** `docker compose build ui` and read the `tsc` errors.
- No lockfile: `npm install` resolves fresh. Direct deps pinned: react 19.3.1, recharts
  3.10.1, lucide-react 1.61.0, vite 7.3.7, @vitejs/plugin-react 5.2.0, tailwindcss +
  @tailwindcss/vite 4.3.3, typescript 5.9.3.
- Likely spots: recharts prop types in `LivePayments.tsx` (`ReferenceLine label`,
  `YAxis tickFormatter`, `Line unit`), `aria-hidden` / JSX typing in `IncidentDetail.tsx`.
  All lucide icon names were checked to exist in 1.61.0.
- Fastest fix for a stubborn type error: fix the type properly; if blocked, a narrow
  cast is acceptable. Don't drop `tsc` from the build.

**nginx.** If `/api` returns 502 from the UI: check `docker compose logs ui`. The config
resolves `api` via Docker DNS `127.0.0.11` per request (`set $api_upstream`), so ui starts
even if api isn't up yet.

**payment-service SQL** (`services/stats.py`). Test directly:
`curl -s "localhost:8080/stats/timeseries" | python3 -m json.tool` and
`curl -s "localhost:8080/stats/breakdown?bank=HDFC" | python3 -m json.tool`.
Things to suspect: `date_bin(make_interval(secs => $1), ...)` param typing,
`percentile_cont ... FILTER`, int2 params (psycopg sends small ints as int2; the window
+ baseline sum is already cast to `::int`).

**worker / Temporal.**
- Workflow sandbox: all app imports are inside `workflow.unsafe.imports_passed_through()`.
  If you see sandbox restriction errors, that's the place.
- `@workflow.init __init__` builds `Progress` using `workflow.info()` and `workflow.now()`.
- Activities are bound methods on `Activities`; the workflow calls
  `workflow.execute_activity_method(Activities.<name>, arg, ...)`.
- A critical step failure raises `ApplicationError` → Temporal shows the run Failed; the UI
  still shows progress via query (replay).
- Detector uses `handle.describe()`; NOT_FOUND → no previous incident. Cooldown 120 s after
  a run closes before reopening the same bank.
- Inspect workflows: `docker compose exec temporal temporal workflow list` (and the UI at :8233).

**api.** `list_workflows("WorkflowType = 'InvestigateIncident'")` on the dev server; query
`get_progress` needs the worker running (Temporal replays to answer). Errors map to JSON:
Temporal NOT_FOUND → 404, other RPC errors → 503, payment-service down → 502.

**LLM step.** If it fails: `docker compose logs worker | grep -i analyze`. Bad/missing
key → non-retryable error shown on the timeline. A malformed answer raises `RcaParseError`
and Temporal retries (3 attempts). If `content` comes back empty, raise `LLM_MAX_TOKENS`.

**Temporal healthcheck** in compose (`temporal operator cluster health`) may not work in that
image; it is cosmetic: worker and api depend on `service_started` and retry the connection.

## 8. Expected demo behaviour and timings

| Moment | Expected |
|---|---|
| Startup | ~60 s before the chart is meaningful; 4 banks ~98% |
| Inject HDFC timeout 60% | HDFC tiles red within ~10 s (60 s window mixes in) |
| Detection | `incident opened` in worker logs ~8-15 s after injecting |
| Steps 1-4 | seconds; LLM ~1-5 s |
| Await approval | UI shows Approve / Reject; Temporal UI shows run waiting |
| After Approve | runbook clears fault; verify turns healthy in ~20-30 s |
| End | status `resolved`, "Resolved in N s", postmortem saved to Supermemory |

Each rehearsal saves another postmortem to Supermemory, so recall results grow.

## 9. Debug commands (zsh)

```bash
docker compose ps
docker compose logs --tail 100 worker
docker compose logs --tail 100 api ui payment-service
docker compose up --build -d <service>          # rebuild after a fix
docker compose down -v && docker compose up --build -d   # full reset
docker compose exec postgres psql -U paypulse -d paypulse -c "select bank, status, count(*) from payments where created_at > now() - interval '1 minute' group by 1,2;"
docker compose exec temporal temporal workflow list
curl -s localhost:8000/api/status | python3 -m json.tool
curl -s localhost:8000/api/incidents/incident-HDFC | python3 -m json.tool
```

Unit tests on the Mac (pure logic, no Docker needed):

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
(cd payment-service && pytest -q) && (cd worker && pytest -q) && ruff check .
```

## 10. Not done / out of scope

- **Kepler (RubixKube)**: no integration; UI shows "integration in progress".
- No UI lockfile yet (commit the generated `ui/package-lock.json` once the build works:
  `docker compose cp` is not available for build stages, so generate it with
  `cd ui && npm install --package-lock-only` if Node is on the Mac, otherwise skip).
- No workflow integration tests; no auth, CI/CD, migrations, extra scenarios.
