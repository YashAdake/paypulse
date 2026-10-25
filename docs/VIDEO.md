# PayPulse demo video: storyboard, snippets and editing guide

Target: **about 3 minutes**, 1080p. A screen recording of the live demo, with short
inserts ("snippets") cut in between: title cards, an architecture card, and code that
shows each partner technology doing its job.

Tools (all free on the Mac): **Cmd+Shift+5** (screen recording), **Keynote** (title and
architecture cards), **iMovie** (editing, voiceover, export).

---

## 1. Storyboard

`SCREEN` = demo screen recording. `CARD` = Keynote slide exported as an image.
`CODE` = code snippet image (section 3).

| Time | Type | What's on screen | Voiceover (read slowly) |
|---|---|---|---|
| 0:00-0:07 | CARD 1 | **PayPulse**: AI copilot for payment incidents. One-liner underneath | "When payments start failing, PayPulse finds out why in seconds, remembers past fixes, and repairs it with one click of approval." |
| 0:07-0:25 | CARD 2 | **The problem**: 3 bullets: slow manual diagnosis · fixes forgotten · AI can't be trusted alone | "When a bank starts failing, an on-call engineer has to work out which bank, which method, whether there was a deploy, and whether we've seen this before. That knowledge is scattered, and it's slow." |
| 0:25-0:37 | CARD 3 | **The loop**: Detect → Investigate → Remember → Propose → Approve → Fix → Verify → Learn | "PayPulse automates the whole loop. The AI investigates and proposes; a human decides." |
| 0:37-0:50 | SCREEN | Command Center, all green; pan over the partner strip | "This is a live payment gateway: four banks, UPI and cards, about 98% success. Our partners are live at the top." |
| 0:50-1:02 | SCREEN | Demo controls → HDFC · timeouts · 60% → Inject fault; HDFC turns red | "Now HDFC's gateway starts timing out. Nobody is paging anyone." |
| 1:02-1:10 | SCREEN | Incident appears; timeline starts | "PayPulse opens an incident by itself, as a Temporal workflow." |
| 1:10-1:16 | **CODE A** | Temporal: one workflow per bank | "Each bank gets a fixed workflow ID, so Temporal guarantees one incident per bank: no duplicates." |
| 1:16-1:26 | SCREEN | Evidence step done; memory panel fills (Aug-12 HDFC) | "Evidence is computed in SQL. Then Supermemory recalls that we had exactly this in August, fixed by restarting the connector." |
| 1:26-1:32 | **CODE B** | Supermemory: search past incidents | "That's a single Supermemory search over our past postmortems." |
| 1:32-1:46 | SCREEN | AI root cause panel: summary, confidence, proposed fix | "An open model on Jarvislabs reads the evidence and the memory, and returns a structured diagnosis and a proposed fix." |
| 1:46-1:54 | **CODE C** | Jarvislabs call + runbook allow-list | "It answers in strict JSON, and it can only choose from an allow-list of runbooks. It never writes commands." |
| 1:54-2:04 | SCREEN | Approval panel; switch to Temporal UI showing the run waiting | "Now the workflow stops and waits for a human. It's durable: it would survive a crash." |
| 2:04-2:10 | **CODE D** | Temporal: signal + durable wait | "That wait is a Temporal signal with a timeout." |
| 2:10-2:30 | SCREEN | Click Approve → recovery bars go green → "Resolved in N s" | "One click. PayPulse runs the fix, checks recovery with Temporal timers, and saves the incident back to Supermemory." |
| 2:30-2:45 | CARD 4 | **Architecture** + partner logos/names | "Temporal runs the durable investigation, Supermemory is the incident memory, Jarvislabs hosts the model, and Kepler by RubixKube is our next step for the engineer surface." |
| 2:45-2:55 | CARD 5 | **Guardrails**: allow-listed runbooks · human approval · verified, idempotent fixes · identifiers masked | "And it's safe by design." |
| 2:55-3:00 | CARD 6 | One-liner + github.com/YashAdake/paypulse + team names | "PayPulse. Thank you." |

Waiting parts (detection, recovery) can be sped up in editing. If you do, add a small
caption "sped up 2×", so viewers aren't misled about timings.

---

## 2. Cards to make in Keynote (10 min)

Keynote → New → dark theme (e.g. "Basic Black"), 1920×1080. One slide per card:

1. **PayPulse**: subtitle *AI copilot for payment incidents*; one-liner below
2. **The problem**:
   - Slow diagnosis: bank? method? deploy? done by hand
   - Lost knowledge: last fix lives in someone's memory
   - Risky automation: nobody trusts AI to change production alone
3. **The loop**: `Detect → Investigate → Remember → Propose → Approve → Fix → Verify → Learn`
   (highlight **Approve** as "human")
4. **Architecture**: copy the diagram from `README.md` ("How it works"), plus four rows:
   - Temporal: durable workflow, approval signal, recovery timers
   - Supermemory: recalls past incidents, saves postmortems
   - Jarvislabs: open model (DeepSeek V4.1 Flash) on Token Factory
   - Kepler by RubixKube: engineer surface (next step)
5. **Guardrails**: allow-listed runbooks · human approval · verified, idempotent fixes · card/UPI IDs masked
6. **Close**: one-liner, `github.com/YashAdake/paypulse`, team names

Export: **File → Export To → Images → PNG** → saves one image per slide.

Only use partner logos if the hackathon allows it; plain names are always safe.

---

## 3. Code snippets

Taken from the repo, trimmed to the essential lines (C, the SQL and masking extras also
have a few comments added for viewers). If debugging on the demo Mac changed these files,
open them and use the current lines (same idea).

**How to turn each into an image:** open https://ray.so (or https://carbon.now.sh), paste
the snippet, choose a dark theme and Python, set padding to 64, then **Export PNG**.
Or open the file in VS Code (dark theme, font size ~22), select the lines and screenshot
with **Cmd+Shift+4**.

### CODE A: Temporal, one incident per bank (`worker/app/contracts.py`)

```python
def incident_workflow_id(bank: str) -> str:
    # One fixed ID per bank: Temporal refuses a second running workflow with the same ID,
    # so a bank can never have two open incidents.
    return f"incident-{bank}"
```

### CODE B: Supermemory, recall past incidents (`worker/app/activities.py`)

```python
resp = await self._memory.post(
    "/v4/search",
    json={
        "q": query,
        "containerTag": self._settings.supermemory_container_tag,
        "limit": 3,
        "threshold": self._settings.supermemory_threshold,
        "searchMode": "hybrid",
        "include": {"documents": True},
    },
)
```

### CODE C: Jarvislabs, structured root cause + allow-list (`worker/app/activities.py`, `worker/app/rca.py`)

```python
resp = await self._llm.post(
    "/chat/completions",
    json={
        "model": s.llm_model,  # deepseek-v4.1-flash-1017 on Jarvislabs Token Factory
        "messages": build_messages(req.evidence, req.recall),
        "response_format": {"type": "json_object"},
    },
)

# rca.py: the model can only pick a known runbook
if runbook not in RUNBOOKS:
    raise RcaParseError(f"runbook {runbook!r} is not in the allowed list")
```

### CODE D: Temporal, human approval as a durable wait (`worker/app/workflows.py`)

```python
@workflow.signal(name=DECISION_SIGNAL)
def submit_decision(self, decision: ApprovalDecision) -> None:
    # First decision wins: a double-click or a retried request can't flip it.
    if self._decision is None:
        self._decision = decision

# A durable timer: the wait survives worker restarts.
await workflow.wait_condition(
    lambda: self._decision is not None,
    timeout=timedelta(seconds=cfg.approval_timeout_s),
)
```

### Optional extras (for a longer video)

Maths in SQL (`payment-service/app/services/stats.py`):
```sql
round(avg((status = 'SUCCESS')::int) FILTER (WHERE is_current), 4)     AS current_success_rate,
round(avg((status = 'SUCCESS')::int) FILTER (WHERE NOT is_current), 4) AS baseline_success_rate,
```

Masking before the LLM (`worker/app/masking.py`):
```python
def mask_sensitive(text: str) -> str:
    text = _CARD.sub(_mask_card, text)       # 4111 1111 1111 1234 -> [CARD ****1234]
    return _UPI.sub("[UPI-ID]", text)        # ravi.k@okhdfcbank   -> [UPI-ID]
```

Learning: saving the postmortem (`worker/app/activities.py`):
```python
# customId makes this idempotent: a retried activity updates the same document.
"customId": f"paypulse-{req.incident_id}",
```

---

## 4. Recording the demo (15 min)

Prepare the screen:
```bash
docker compose up -d
curl -s -X DELETE localhost:8080/chaos; echo
open http://localhost:3000
```
- Wait **60 s** so the chart is full; all banks green
- Browser: hide the bookmarks bar (`Cmd+Shift+B`), zoom to 110-125% (`Cmd +`), full screen (`Ctrl+Cmd+F`)
- Turn on **Do Not Disturb**; close other apps
- Open the Temporal UI (http://localhost:8233) in a second tab

Record:
1. Press **Cmd+Shift+5** → **Record Entire Screen** → Options: Microphone **None**
   (voiceover is added later; cleaner audio) → **Record**
2. Do the demo once, calmly, in one take: show the healthy screen (5 s) → inject the HDFC fault →
   wait for the incident → let the steps finish → switch to the Temporal UI tab (5 s) → back →
   **Approve fix** → wait for **Resolved**
3. Stop with the stop button in the menu bar. The file lands on the Desktop

Record **two takes**, then keep the cleaner one.

Between takes, wait 2 minutes (incident cooldown) or reset:
```bash
docker compose down -v && docker compose up -d
```

---

## 5. Editing in iMovie (30 min)

1. iMovie → **Create New → Movie**
2. **Import** the screen recording, the Keynote PNGs and the code PNGs
3. Drag them into the timeline in storyboard order (section 1)
4. **Cut the screen recording** at each insert point: move the playhead, then **Cmd+B**
   (split clip). Drop the CODE image into the gap
5. **Image durations:** select an image → clock icon (Speed/duration) → 5-7 s for code,
   5-15 s for cards (see storyboard)
6. **Stop the zoom effect on images:** select the image → Crop icon → **Fit**
   (otherwise iMovie applies Ken Burns zoom and code gets cut off)
7. **Speed up waiting parts:** select the clip → speedometer icon → **Fast 2×**, then add a
   small title "sped up 2×" (**Titles** → "Lower Third")
8. **Captions** on demo shots (optional but helps with sound off): **Titles → Lower Third**,
   e.g. "Supermemory recalls the Aug-12 HDFC incident"
9. **Transitions:** use **Cross Dissolve** only, 0.5 s, between cards and screen
10. **Voiceover:** Window → **Record Voiceover** (mic icon below the viewer). Read each
    storyboard line while watching its section. Use a quiet room; AirPods or the Mac's mic are fine
11. **Music (optional):** **Audio & Video → Soundtracks**, pick a calm one, volume about 10-15%
    under the voice
12. **Export:** **File → Share → File** → Resolution **1080p**, Quality **High** → Next → save

Check the export plays from start to finish with sound, then upload.

---

## 6. Final checklist

- [ ] Under the time limit (check the hackathon rules; 3 minutes is common)
- [ ] All four partners named; Kepler described honestly as the next step
- [ ] Code snippets readable at full screen (font big enough)
- [ ] Sped-up parts labelled
- [ ] No API keys visible anywhere (terminal, `.env`, browser tabs)
- [ ] Repo link on the last card
- [ ] Exported 1080p, plays with sound
