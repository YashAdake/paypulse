# PayPulse demo guide (macOS)

Step-by-step bring-up on the demo Mac. Every command is copy-paste ready for the
**Terminal** app (zsh). Works on Apple Silicon and Intel Macs.

> Status: Phases 0-5 and the Command Center are written. Python tests, lint and static
> checks pass, Jarvislabs and Supermemory were tested live, and the past incidents are
> already loaded into Supermemory. **The full stack has not run in Docker yet**, so
> step 5 (Claude Code) is where any remaining bugs get fixed.

---

## Step 1: Check the tools (5 min)

Open **Terminal** and run:

```bash
docker --version && git --version && claude --version
```

If something is missing:

| Missing | Fix |
|---|---|
| `docker` | Install **Docker Desktop for Mac** from docker.com, open it, wait for "Engine running" |
| `git` | `xcode-select --install` |
| `claude` | `curl -fsSL https://claude.ai/install.sh \| bash`, then open a new Terminal and run `claude` once to log in |

Docker Desktop must be **running** (whale icon in the menu bar). In Docker Desktop
→ Settings → Resources, give it at least **4 GB memory**.

Check that the ports we need are free (no output means all free):

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(3000|8000|8080|8233|7233|5432) '
```

If something shows up on 5432 (a local Postgres), stop it, or set `POSTGRES_PORT=5433`
in `.env` in step 3.

✅ All three versions print, Docker Desktop shows "Engine running".

---

## Step 2: Get the code (2 min)

```bash
cd ~/Desktop
git clone https://github.com/YashAdake/paypulse.git
cd paypulse
git switch feature/phase-2
git branch --show-current
```

✅ The last command prints `feature/phase-2`.

---

## Step 3: Add your keys to `.env` (2 min)

Create the file:

```bash
cp .env.example .env
```

Then run this. It asks for each key without showing it on screen; paste the key
and press Enter:

```bash
read -s "LLM?Jarvislabs API key: " && echo && read -s "SM?Supermemory API key: " && echo
sed -i '' "s|^LLM_API_KEY=.*|LLM_API_KEY=$LLM|; s|^SUPERMEMORY_API_KEY=.*|SUPERMEMORY_API_KEY=$SM|" .env
unset LLM SM
grep -E '^(LLM|SUPERMEMORY)_API_KEY=' .env | sed -E 's/=(.{6}).*/=\1…(set)/'
```

✅ Both lines print with the first 6 characters and `…(set)`. Then confirm git ignores the file:

```bash
git status --short .env
```

✅ No output (`.env` is never committed; this repo is public).

---

## Step 4: First build and start (5-10 min the first time)

```bash
docker compose up --build -d
```

Then watch until everything is up (press `Ctrl+C` to stop watching):

```bash
while true; do clear; docker compose ps; sleep 3; done
```

✅ `postgres`, `payment-service` and `api` show **healthy**; `temporal`, `worker` and `ui`
show **running**.

**If the build or a service fails, don't debug by hand: go to step 5.**

---

## Step 5: Start Claude Code to verify and fix (main step)

```bash
claude
```

Paste this prompt into Claude:

```text
You are on the PayPulse demo Mac (macOS, zsh, Docker Desktop). Read docs/HANDOFF.md
(full project context from the build session), CLAUDE.md and docs/DEMO_GUIDE.md first. We are on branch feature/phase-2, which
contains Phases 0-5 plus the Command Center UI. It was written on a Windows laptop
without Docker: Python unit tests (48), ruff and static checks passed, Jarvislabs and
Supermemory were tested live, and the seed incidents are already in Supermemory. But
nothing has been built or run in Docker before. Your job: get the full demo working
end to end, fast.

Work in order, fixing problems as you find them (small, focused fixes; commit each fix
with a clear message; push to feature/phase-2 only when I say "push"):

1. Confirm .env exists and LLM_API_KEY and SUPERMEMORY_API_KEY are set. Never print
   key values and never commit .env.
2. docker compose up --build -d, then docker compose ps. Fix any build failure (the ui
   build runs `tsc --noEmit` first, so TypeScript errors show up there).
3. Verify: payment-service /healthz (8080), api /api/status (8000), Command Center
   (3000), Temporal UI (8233). Read `docker compose logs <service>` for anything
   unhealthy. Never run before, so these are the risk areas:
   - payment-service SQL in app/services/stats.py (/stats/timeseries, /stats/breakdown)
   - worker: Temporal sandbox imports, @workflow.init, dataclass conversion
   - api: list_workflows / query / signal against the Temporal dev server
   - ui: nginx proxy to api, TypeScript build, recharts/lucide imports
4. Run the demo flow (docs/DEMO_GUIDE.md step 7 has curl commands): inject HDFC
   timeouts at 60%, confirm an incident opens within ~15 s (docker compose logs -f
   worker), steps progress, the AI root cause appears, approve, recovery verifies,
   the incident ends "resolved".
5. Report what you fixed and anything still open. Keep scope tight: no new features,
   no refactors, just make the demo work.
```

Approve its commands when asked. Let it fix issues one at a time.

✅ Claude reports all services healthy and one incident that reached **resolved**.

---

## Step 6: See it in the browser (5 min)

```bash
open http://localhost:3000
open http://localhost:8233
```

| Tab | You should see |
|---|---|
| Command Center (3000) | 4 banks green at ~98%; partner strip shows Temporal **Live**, Jarvislabs and Supermemory **Ready** |
| Temporal UI (8233) | Workflows list (incident runs appear here as `incident-HDFC`) |

Wait about 60 seconds after startup so the chart has data, then run the demo in the
Command Center:

1. **Demo controls** → HDFC · timeouts · 60% → **Inject fault**
2. HDFC tiles turn red; within ~15 s an **HDFC incident** opens
3. Timeline: evidence (SQL) → memory (finds the **Aug 12 HDFC** incident) → AI root cause (Jarvislabs)
4. Click **Approve fix**
5. Recovery checks turn green → **Resolved in N s**

✅ You reach "Resolved" using only the UI.

---

## Step 7: Terminal checks (when the UI misbehaves)

Health and live stats:

```bash
curl -s localhost:8080/healthz; echo
curl -s localhost:8000/api/status | python3 -m json.tool
curl -s "localhost:8080/stats?window_seconds=60" | python3 -m json.tool
```

Inject the incident:

```bash
curl -s -X POST localhost:8080/chaos -H 'Content-Type: application/json' \
  -d '{"bank":"HDFC","type":"timeout","rate":0.6}'; echo
```

Follow the investigation:

```bash
docker compose logs -f worker
```

Incident list and live progress:

```bash
curl -s localhost:8000/api/incidents | python3 -m json.tool
curl -s localhost:8000/api/incidents/incident-HDFC | python3 -m json.tool
```

Approve the fix:

```bash
curl -s -X POST localhost:8000/api/incidents/incident-HDFC/decision \
  -H 'Content-Type: application/json' -d '{"approved":true}'; echo
```

Clear all faults:

```bash
curl -s -X DELETE localhost:8080/chaos; echo
```

---

## Step 8: Save the working version (2 min)

In Claude, type:

```text
push
```

Then open the pull request and merge it into `main`:

```bash
open https://github.com/YashAdake/paypulse/compare/main...feature/phase-2
```

---

## Step 9: Rehearse (15-20 min)

Run the demo 3 times. Between runs, either wait ~2 minutes (incident cooldown) or reset
everything:

```bash
docker compose down -v && docker compose up -d
```

Aim for under 2 minutes from **Inject fault** to **Resolved**. One line per partner,
said when its badge lights up:

- **Temporal:** "The investigation is a durable workflow. Right now it's paused, waiting
  for my approval, and it would survive a crash."
- **Supermemory:** "It remembered we fixed exactly this in August."
- **Jarvislabs:** "An open model on Jarvislabs explains the cause. Card numbers and UPI IDs
  are masked, and payment data never goes to a public API."
- **Kepler:** "Kepler by RubixKube is the engineer-facing surface; integration in progress."

---

## Demo-day checklist

- [ ] Docker Desktop running; stack started **15 minutes before**:
  ```bash
  cd ~/Desktop/paypulse && docker compose up -d && docker compose ps
  ```
- [ ] Wait 60 s after startup before injecting (charts need data)
- [ ] Command Center full screen (`Ctrl+Cmd+F`); Temporal UI in a second tab
- [ ] Terminal ready with the fallback: `docker compose logs -f worker`
- [ ] No active faults left over from rehearsal:
  ```bash
  curl -s -X DELETE localhost:8080/chaos; echo
  ```

---

## Troubleshooting

Status and logs (send these to Claude when stuck):

```bash
docker compose ps
docker compose logs --tail 80 worker
docker compose logs --tail 80 api ui payment-service
```

Rebuild one service after a fix:

```bash
docker compose up --build -d worker
```

Full reset (wipes the database and Temporal history):

```bash
docker compose down -v && docker compose up --build -d
```

Re-load the past incidents into Supermemory (already done; safe to repeat):

```bash
docker compose run --rm memory-seed
```

| Symptom | Likely cause |
|---|---|
| Partner strip: Jarvislabs "No API key" | `LLM_API_KEY` missing in `.env`; fix, then `docker compose up -d worker api` |
| Incident stuck at "AI root cause", then failed | Jarvislabs key or credits; check `docker compose logs worker` |
| Memory panel: "not configured" | `SUPERMEMORY_API_KEY` missing; same fix as above |
| No incident after injecting | Wait 15 s; check `docker compose logs worker` for "incident opened" |
| New incident won't open right after one | 2-minute cooldown per bank; wait or full reset |
| Command Center blank / api errors | `docker compose logs api ui` |
