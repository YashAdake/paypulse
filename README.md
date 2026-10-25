# PayPulse

> When payments start failing, PayPulse finds out why in seconds, remembers past
> fixes, and repairs it with one click of approval.

PayPulse is an AI copilot for payment incidents. It notices when the payment success
rate drops, works out which bank, method or deploy is to blame, recalls how similar
incidents were fixed before, proposes a fix, waits for a human to approve it, applies
it, checks that payments recovered, and saves the incident to memory for next time.

Hackathon project. Project rules for contributors (and AI assistants) are in
[CLAUDE.md](CLAUDE.md).

## How it works

```
traffic generator ──► payment-service ──► Postgres (payments, chaos_rules, deploys)
                           ▲   /chaos lets us break a bank on purpose
                           │
worker: detector polls /stats ──► success rate drops ──► InvestigateIncident (Temporal)
  1. gather evidence    SQL: which bank/method, error codes, p95 latency, recent deploys
  2. recall memory      Supermemory: similar past incidents and what fixed them
  3. root cause         LLM (Jarvislabs Token Factory) reads masked evidence -> JSON RCA + fix
  4. notify             show the proposal to an engineer
  5. wait for approval  Temporal signal: a human clicks Approve
  6. run runbook        e.g. DELETE /chaos/HDFC (idempotent, safe to retry)
  7. verify recovery    Temporal timer, then re-check /stats
  8. save to memory     write the incident and fix back to Supermemory
```

The maths (success rates, p95, top errors) is done in SQL. The LLM only interprets
the evidence; it never computes numbers.

| Component | Tech | Status |
|---|---|---|
| payment-service | Python 3.12, FastAPI, psycopg 3, Postgres 16 | Phase 1 (this branch) |
| worker | Temporal Python SDK | Phase 2+ |
| memory | Supermemory | Phase 4 |
| LLM | Jarvislabs Token Factory (OpenAI-compatible) | Phase 3 |
| UI | Kepler (RubixKube) or a small approval page | Phase 6 |

### Repo layout

```
docker-compose.yml     Postgres + Temporal dev server + services
payment-service/       FastAPI: fake payments, /chaos, /stats, /deploys, traffic generator
  app/main.py          app setup and startup/shutdown
  app/config.py        settings from env vars
  app/db.py            connection pool, startup retry, schema
  app/schema.sql       tables (applied on every startup, idempotent)
  app/domain.py        enums: Bank, Method, ChaosType, ErrorCode
  app/models.py        request/response schemas
  app/routes/          HTTP endpoints (thin)
  app/services/        logic + SQL; simulator.py is pure and unit-tested
worker/                (Phase 2) Temporal worker, detector, agent activities
memory-seed/           (Phase 4) fake past postmortems
ui/                    (Phase 6) approval page fallback
```

## payment-service API

| Endpoint | What it does |
|---|---|
| `POST /pay` | Simulate one payment `{bank, method, amount_paise}`. Banks: HDFC, SBI, ICICI, AXIS. Methods: UPI, CARD. About 98% succeed normally. |
| `POST /chaos` | Break a bank: `{bank, type: "timeout"\|"decline", rate: 0..1}`. Replaces that bank's rule. |
| `GET /chaos` | List active chaos rules. |
| `DELETE /chaos` | Clear all rules. |
| `DELETE /chaos/{bank}` | Clear one bank's rule. Returns 200 even if there was none. |
| `GET /stats?window_seconds=60` | Per bank+method: total, success rate, top error code, p95 latency. |
| `POST /deploys` / `GET /deploys` | Record / list fake deploy events. |
| `GET /healthz` | 200 if the service can reach Postgres, 503 if not. |

Interactive docs: http://localhost:8080/docs

Behaviour worth knowing:

- **Failed payments return 201.** The API call worked; the payment outcome is in `status`.
- **Chaos then baseline.** A payment first rolls against the chaos rate, then against
  the normal 98%. HDFC at 60% timeouts therefore succeeds about 0.4 × 0.98 ≈ 39%.
- **Timeouts look like timeouts.** They fail with `BANK_TIMEOUT` and about 10,000 ms
  latency, so p95 jumps. Declines fail fast with `ISSUER_DECLINED`. Latency is recorded,
  not slept, so the service stays fast.
- **Idempotency.** `POST /pay` and `POST /deploys` accept an optional `Idempotency-Key`
  header. Repeating a key returns the original record with 200; reusing it for a
  different body returns 409. `POST /chaos` and the deletes are idempotent by design.
- **Errors** always look like
  `{"error": {"code", "message", "request_id", "details"?}}`; every response carries
  an `X-Request-ID` header, and every log line is JSON with the same ID.
- **Traffic generator** creates `TRAFFIC_RPS` random payments per second inside the
  service (default 5, `0` turns it off). This is why the service runs a single process.

## Setup for teammates (your laptop)

You write code and run unit tests locally. Docker is **not** needed on the laptop.

```powershell
git clone https://github.com/YashAdake/paypulse.git
cd paypulse
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

ruff check .               # lint
ruff format .              # format
cd payment-service; pytest; cd ..   # pure-logic unit tests (no DB needed)
```

Workflow: `main` must always run. Branch from `main`, open a PR, merge when it works
on the demo PC. Never commit `.env` or keys: **this repo is public**.

## Run on the demo PC

Needs Docker Desktop and Git.

```powershell
git clone https://github.com/YashAdake/paypulse.git   # first time only
cd paypulse
git pull
# Optional: Copy-Item .env.example .env, then edit. Defaults work without it.
docker compose up --build -d
docker compose ps          # all services should become "healthy"
```

| What | URL |
|---|---|
| payment-service | http://localhost:8080/docs |
| Temporal Web UI | http://localhost:8233 |
| Postgres | `localhost:5432`, user/password/db `paypulse` |

Useful commands:

```powershell
docker compose logs -f payment-service    # JSON logs; a traffic summary every 30s
docker compose restart payment-service
docker compose down                       # stop, keep data
docker compose down -v                    # stop and wipe the database (fresh start)
```

### Check it works (PowerShell)

Run these on the demo PC after `docker compose up`. Give the traffic generator about
a minute to fill the first stats window.

```powershell
$api = "http://localhost:8080"

# 0. Health
Invoke-RestMethod "$api/healthz"

# 1. Baseline: every bank and method around 0.98 success, p95 well under 1000 ms
(Invoke-RestMethod "$api/stats?window_seconds=60").groups | Format-Table

# 2. Break HDFC: 60% of HDFC payments time out
$body = @{ bank = "HDFC"; type = "timeout"; rate = 0.6 } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/chaos" -ContentType "application/json" -Body $body
(Invoke-RestMethod "$api/chaos").rules | Format-Table

# 3. Let the 60-second window fill with chaos traffic
Start-Sleep -Seconds 60

# 4. Only HDFC drops: around 0.39 success, top error BANK_TIMEOUT, p95 around 10000 ms.
#    SBI, ICICI and AXIS stay around 0.98.
(Invoke-RestMethod "$api/stats?window_seconds=60").groups | Format-Table

# 5. Clear chaos (run it twice: the second call returns removed = [] and still succeeds)
Invoke-RestMethod -Method Delete "$api/chaos"
Invoke-RestMethod -Method Delete "$api/chaos"
```

With about 37 payments per bank+method per minute, numbers wobble by a few percent;
the HDFC drop is far bigger than the noise.

More checks:

```powershell
# One payment by hand, with an idempotency key. Run it twice: same id, 201 then 200.
$pay = @{ bank = "SBI"; method = "UPI"; amount_paise = 49900 } | ConvertTo-Json
Invoke-WebRequest -Method Post "$api/pay" -ContentType "application/json" -Body $pay `
  -Headers @{ "Idempotency-Key" = "demo-1" } -UseBasicParsing |
  Select-Object StatusCode, Content

# Record and list a deploy
$deploy = @{ service = "hdfc-connector"; version = "v2.4.1"; description = "Tune bank timeout" } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/deploys" -ContentType "application/json" -Body $deploy
(Invoke-RestMethod "$api/deploys?since_seconds=3600").deploys | Format-Table

# Bad input gets a clear 422 that names the field
try {
  Invoke-RestMethod -Method Post "$api/chaos" -ContentType "application/json" `
    -Body '{"bank":"HDFC","type":"timeout","rate":1.5}'
} catch { $_.ErrorDetails.Message }
```

## Configuration

All settings are env vars with defaults; see [.env.example](.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `TRAFFIC_RPS` | `5` | Fake payments per second; `0` turns the generator off |
| `LOG_LEVEL` | `INFO` | `DEBUG` also logs `/healthz` polls |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `paypulse` | Database credentials |
| `PAYMENT_SERVICE_PORT` / `POSTGRES_PORT` | `8080` / `5432` | Host ports |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | Jarvislabs Token Factory | Used from Phase 3; key only in `.env` |

Database timeouts and pool sizes (`DB_*`) are in
[payment-service/app/config.py](payment-service/app/config.py).

## Skipped for scope

Deliberately left out to keep the hackathon build small and explainable:

- Auth and multi-tenancy
- Kubernetes, CI/CD pipelines
- Caching layers (the chaos rule is read from Postgres on every payment; fine at 5 rps)
- ORMs (plain SQL via psycopg 3) and a migrations tool (`schema.sql` is re-applied on
  startup; reset with `docker compose down -v` after a schema change)
- Admin panels
- Scenarios beyond HDFC timeouts
- Durable Temporal storage (the dev server keeps history in memory)
- Storing payer identifiers (UPI IDs, card numbers): evidence is aggregates only
