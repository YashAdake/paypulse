# PayPulse

Hackathon project. AI copilot for payment incidents: detects payment
success-rate drops, investigates by bank/method/deploy, recalls past
incidents, proposes a fix, a human approves, then verifies recovery and
saves the incident to memory.

One-liner: "When payments start failing, PayPulse finds out why in
seconds, remembers past fixes, and repairs it with one click of approval."

## Stack (keep it simple and explainable)
- Python 3.12 everywhere. FastAPI for HTTP APIs.
- Postgres 16. Plain SQL via psycopg 3 (no ORM); SQL is easy to explain.
- Temporal (Python SDK): durable InvestigateIncident workflow,
  approval signal, timers
- Supermemory: past incidents and fixes (recall + write-back)
- LLM via an OpenAI-compatible endpoint: Jarvislabs Token Factory
  (managed open models, pay per token) for dev and demo (payment data
  must not go to public APIs)
- Kepler (RubixKube): engineer-facing surface; integration TBD

## Structure
- payment-service/  FastAPI: fake payments, /chaos, /stats, /deploys,
                    traffic generator
- worker/           Temporal worker + detector + agent activities
- memory-seed/      fake past postmortems for Supermemory
- ui/               simple approval page (fallback if Kepler doesn't fit)
- docker-compose.yml  Postgres + Temporal dev server + services

## Workflow steps
gather evidence -> recall memory -> LLM RCA (JSON) -> notify ->
wait for approval signal -> run runbook -> verify recovery -> save to memory

## Rules
- Do the maths in SQL; the LLM only interprets evidence
- All LLM/DB/HTTP calls in Temporal activities; workflow code stays
  deterministic
- Runbook actions must be idempotent (activities get retried)
- Mask UPI IDs/card numbers before anything reaches the LLM
- Main must always run. Feature branches + PRs.
- Never commit .env or keys (this repo is PUBLIC)
- Scope: ONE scenario (HDFC timeouts) end to end before anything else.
  No UI work until phases 1-5 work.

## Engineering standards
Act as a senior engineer. Production-quality code, hackathon-sized scope.
Code must be easy to read and explain to teammates.

Always:
- Clean structure: small modules with one responsibility
  (app/main.py, app/config.py, app/db.py, app/routes/, app/services/)
- All config via env vars (pydantic-settings) with sensible defaults
- Pydantic models for every request and response
- Structured JSON logging with a request ID middleware
- Never swallow errors; return clear JSON errors with correct HTTP codes
- Validate all inputs (pydantic, enums for bank/method/chaos type)
- /healthz endpoint; clean startup and shutdown (FastAPI lifespan)
- Timeouts on every DB and HTTP call
- Idempotency keys on any action that changes state
- pytest unit tests for core logic (chaos rules, payment simulation);
  no tests for trivial code
- Pinned dependencies in requirements.txt; ruff for lint/format
- Dockerfile: python:3.12-slim, non-root user, small image
- Type hints everywhere. Comments explain WHY, not WHAT.

Never (out of scope; list in README under "Skipped for scope"):
- Auth, multi-tenancy, Kubernetes, CI/CD pipelines, caching layers,
  ORMs, admin panels, extra scenarios beyond HDFC timeouts

When unsure: choose the simpler option and tell me the trade-off.

## Dev setup
Code is written on a low-spec Windows laptop WITHOUT Docker. Never run
docker here. Pure-logic unit tests may run locally with pytest. Everything
else runs on a separate demo PC: git pull -> docker compose up --build -d.
Keep changes small and buildable.

## Phases
0 repo + Docker stack | 1 payment service + chaos | 2 workflow skeleton |
3 evidence + LLM | 4 Supermemory | 5 approve -> fix -> verify | 6 UI/Kepler + demo
