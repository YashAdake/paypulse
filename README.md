# PayPulse

> When payments start failing, PayPulse finds out why in seconds, remembers past
> fixes, and repairs it with one click of approval.

PayPulse is an AI copilot for payment incidents. It notices when the payment success
rate drops, works out which bank, method or deploy is to blame, recalls how similar
incidents were fixed before, proposes a fix, waits for a human to approve it, applies
it, checks that payments recovered, and saves the incident to memory for next time.

Hackathon project. Rules for contributors (and AI assistants): [CLAUDE.md](CLAUDE.md).
Running it on the demo PC: [docs/DEMO_PC.md](docs/DEMO_PC.md).

## How it works

```
traffic generator ──► payment-service ──► Postgres (payments, chaos_rules, deploys)
                           ▲   /chaos lets us break a bank on purpose
                           │
worker: detector polls /stats ──► success rate < 90% ──► InvestigateIncident (Temporal)
  1. gather evidence    SQL: per-method now vs before, error mix, other banks, deploys
  2. recall memory      Supermemory: similar past incidents and what fixed them
  3. root cause         Jarvislabs LLM reads masked evidence -> JSON RCA + runbook
  4. notify             proposal appears in the Command Center
  5. wait for approval  Temporal signal: a human clicks Approve (durable wait, 15 min)
  6. run runbook        restart_bank_connector (idempotent, safe to retry)
  7. verify recovery    Temporal timers: re-check the bank every 10 s
  8. save to memory     postmortem written back to Supermemory

ui (Command Center, :3000) ──► api (:8000) ──► payment-service + Temporal
```

The maths (success rates, p95, error shares) is done in SQL. The LLM only interprets
the evidence and picks a runbook from an allow-list; it never writes commands.

| Component | What | Tech |
|---|---|---|
| `payment-service/` | System under watch: fake payments, chaos, stats | FastAPI, psycopg 3, Postgres 16 |
| `worker/` | Detector + InvestigateIncident workflow + activities | Temporal Python SDK, httpx |
| `api/` | Backend for the UI: live data, incident progress, approvals | FastAPI, Temporal client |
| `ui/` | Command Center | React, Vite, TypeScript, Tailwind, Recharts, nginx |
| `memory-seed/` | Fake past postmortems loaded into Supermemory | Markdown |

Partners: **Temporal** (durable workflow, approval signal, timers), **Jarvislabs**
(Token Factory LLM, `deepseek-v4.1-flash-1017`), **Supermemory** (incident memory),
**Kepler by RubixKube** (engineer surface, integration pending).

### Design choices worth knowing

- **One incident per bank.** Workflow ID `incident-HDFC`: Temporal refuses a second
  running workflow with the same ID, so duplicates are impossible.
- **Detector asks Temporal**, not local memory, whether an incident is running or closed
  recently (120 s cooldown), so restarts are safe.
- **Progress is a Temporal query.** The UI shows exactly what the workflow knows.
- **First approval wins.** Double clicks or retries can't flip a decision.
- **Runbooks are idempotent.** `restart_bank_connector` maps to `DELETE /chaos/{bank}` in
  the simulator; repeating it is harmless.
- **Masking.** UPI IDs and card numbers are masked before anything reaches the LLM.
- **Graceful without keys.** No Supermemory key: investigations run without memory.
  No LLM key: the root-cause step fails clearly (shown in the UI).

## payment-service API

| Endpoint | What it does |
|---|---|
| `POST /pay` | Simulate one payment `{bank, method, amount_paise}` (~98% succeed) |
| `POST /chaos` · `GET /chaos` · `DELETE /chaos` · `DELETE /chaos/{bank}` | Break / list / heal banks |
| `GET /stats?window_seconds=60` | Per bank+method: total, success rate, top error, p95 |
| `GET /stats/timeseries` | Success rate per bank in 10 s buckets (UI chart) |
| `GET /stats/breakdown?bank=HDFC` | Evidence: per-method now vs baseline, error mix, all banks |
| `POST /deploys` · `GET /deploys` | Record / list fake deploy events |
| `GET /healthz` | 200 if Postgres is reachable, else 503 |

Failed payments return 201 (the call worked; the outcome is in `status`). `POST /pay` and
`POST /deploys` accept an `Idempotency-Key` header. Errors always look like
`{"error": {"code", "message", "request_id"}}`.

## Setup for teammates (laptop)

Write code and run unit tests locally; Docker is not needed on the laptop.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ruff check .; ruff format .
cd payment-service; pytest; cd ..\worker; pytest; cd ..
```

Branch from `main`, open a PR, merge once it works on the demo PC. Never commit `.env`
or keys: **this repo is public**.

## Run on the demo PC

```powershell
git clone https://github.com/YashAdake/paypulse.git; cd paypulse
Copy-Item .env.example .env      # then set LLM_API_KEY (and SUPERMEMORY_API_KEY)
docker compose up --build -d
docker compose ps                 # wait for "healthy"
docker compose run --rm memory-seed   # once, if SUPERMEMORY_API_KEY is set
```

| What | URL |
|---|---|
| **Command Center** | http://localhost:3000 |
| Temporal UI | http://localhost:8233 |
| api docs | http://localhost:8000/docs |
| payment-service docs | http://localhost:8080/docs |

```powershell
docker compose logs -f worker            # incidents, steps, errors (JSON)
docker compose logs -f api payment-service
docker compose down                      # stop, keep data
docker compose down -v                   # stop and wipe the database
```

### Demo script (2 minutes)

1. Open the Command Center: all banks green, partners live in the top strip.
2. Demo controls: **HDFC · timeouts · 60% → Inject fault**. HDFC turns red within seconds.
3. ~10 s later an incident opens; the timeline ticks through evidence (SQL), memory
   (Supermemory finds the Aug 12 HDFC incident) and AI root cause (Jarvislabs).
4. The workflow waits. Show **Open in Temporal UI**: it is paused durably on a signal.
5. Click **Approve fix**. The runbook runs, recovery checks turn green,
   "Resolved in N s" appears, and the postmortem is saved to memory.

### Quick checks without the UI (PowerShell)

```powershell
$api = "http://localhost:8080"
(Invoke-RestMethod "$api/stats?window_seconds=60").groups | Format-Table
$body = @{ bank = "HDFC"; type = "timeout"; rate = 0.6 } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/chaos" -ContentType "application/json" -Body $body
Start-Sleep -Seconds 60
(Invoke-RestMethod "$api/stats?window_seconds=60").groups | Format-Table   # only HDFC drops (~0.39)
(Invoke-RestMethod "http://localhost:8000/api/incidents").incidents | Format-Table
Invoke-RestMethod -Method Delete "$api/chaos"
```

## Configuration

All settings are env vars with defaults; see [.env.example](.env.example). Detector and
workflow tuning (`DETECTOR_*`, `APPROVAL_TIMEOUT_S`, …) is in
[worker/app/config.py](worker/app/config.py).

## Skipped for scope

- Auth and multi-tenancy
- Kubernetes, CI/CD pipelines
- Caching layers
- ORMs and a migrations tool (`schema.sql` re-applied on startup; `docker compose down -v`
  after a schema change)
- Admin panels
- Scenarios beyond HDFC timeouts (other banks/declines work, but only HDFC is rehearsed)
- Durable Temporal storage (the dev server keeps history in memory)
- Storing payer identifiers: evidence is aggregates only
- A UI lockfile (`package-lock.json` is generated by the first Docker build)
- Workflow integration tests (verified end to end on the demo PC instead)
