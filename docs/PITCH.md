# PayPulse pitch and demo script

For the team presenting to judges and partner sponsors. Target: **5 minutes**
(about 2 talking, 2.5 live demo, 0.5 close), then Q&A.

**One-liner:** *When payments start failing, PayPulse finds out why in seconds, remembers
past fixes, and repairs it with one click of approval.*

---

## Roles

| Person | Job |
|---|---|
| **Presenter** | Talks: problem, solution, partner callouts, close |
| **Driver** | Runs the Command Center: inject fault, click Approve, switch to Temporal UI |
| **Backup** | Watches `docker compose logs -f worker`; has the backup video ready |

With two people, the presenter also takes the backup role.

---

## Before you go on stage (15 minutes before)

```bash
docker compose up -d && docker compose ps
curl -s -X DELETE localhost:8080/chaos; echo
open http://localhost:3000
```

- [ ] Command Center full screen (`Ctrl+Cmd+F`); all four banks green
- [ ] Partner strip: Temporal **Live**, Jarvislabs **Ready**, Supermemory **Ready**
- [ ] Temporal UI open in a second tab: http://localhost:8233
- [ ] Wait **60 s** after startup so the chart is full
- [ ] Notifications off (Focus mode), laptop on power, screen brightness up
- [ ] **Backup video** of a full successful run (record during rehearsal: `Cmd+Shift+5`)

---

## The script

### 1. Hook (15 s)

> "Every time a payment fails, someone is standing at a checkout counter, or a train
> ticket is slipping away. In India, payments run through UPI and cards billions of times
> a month. When one bank starts failing, every second counts."

### 2. Problem (30 s)

> "Today, when the payment success rate drops, an on-call engineer is woken up and starts
> digging: which bank? Which method? Was there a deploy? Have we seen this before? The
> answer is spread across dashboards, logs and old incident notes, and the fix that worked
> last time lives in someone's memory. That triage is slow, it's stressful, and it happens
> again for every incident."

Three pains to land:
1. **Slow diagnosis**: humans correlate bank, method, errors and deploys by hand.
2. **Lost knowledge**: past fixes are forgotten or buried.
3. **Risky automation**: nobody wants an AI changing production on its own.

### 3. Solution (20 s)

> "PayPulse is an AI copilot for payment incidents. It detects the drop, investigates
> automatically, recalls how we fixed similar incidents, and proposes a fix. A human
> approves with one click, and PayPulse applies the fix, verifies recovery, and saves what
> it learned for next time."

Say the key idea once, clearly:
> "**The AI investigates and proposes; a human decides.** And everything runs as a durable
> workflow, so nothing gets lost halfway."

### 4. Live demo (2.5 min)

Driver acts; presenter narrates. Point at the screen element as you mention it.

| # | Driver does | Presenter says | Partner to credit |
|---|---|---|---|
| 1 | Shows the Command Center | "This is a live payment gateway: four banks, UPI and cards, about 98% success. Top strip: our partners, all live." | All (point at the strip) |
| 2 | Demo controls → HDFC · timeouts · 60% → **Inject fault** | "Now HDFC's gateway starts timing out. Watch the red line." | |
| 3 | Wait for HDFC tiles to turn red | "HDFC drops below our 90% threshold. Nobody is paging anyone. PayPulse already noticed." | |
| 4 | Incident appears; timeline starts | "An incident opened by itself. This investigation is a **Temporal** workflow: each step is durable and retried, and it survives crashes." | **Temporal** |
| 5 | Evidence step done | "Step one: evidence. All the maths (success rate per method, error mix, latency, recent deploys) is done in SQL. The AI never invents numbers." | |
| 6 | Memory panel fills | "Step two: memory. **Supermemory** found that we had exactly this on 12 August: HDFC timeouts, fixed by restarting the connector." | **Supermemory** |
| 7 | AI root cause appears | "Step three: root cause. An open model on **Jarvislabs** reads the evidence and the memory, and returns a structured diagnosis with a confidence score and a proposed fix. Card numbers and UPI IDs are masked first, and payment data never goes to a public AI API." | **Jarvislabs** |
| 8 | Point at Approval panel | "And now it **stops**. The workflow is paused, waiting for a human. It could wait 15 minutes, survive a restart, and still be here." | **Temporal** (signal) |
| 9 | Switch to the Temporal UI tab briefly, then back | "Here it is in Temporal: the run is waiting on our approval signal." | **Temporal** |
| 10 | Click **Approve fix** | "One click." | |
| 11 | Recovery bars turn green | "PayPulse runs the fix, then keeps checking until HDFC is healthy again, using Temporal timers." | **Temporal** |
| 12 | "Resolved in N s" | "Resolved: N seconds from detection to verified recovery, and most of that was me deciding. And it saved this incident back to Supermemory, so next time it'll be even faster." | **Supermemory** |

If a step is slow, fill the silence with the guardrails (section 6) rather than waiting
quietly.

### 5. Architecture and partners (40 s)

Show the README diagram or say:

> "Four pieces. A detector watches payment stats. A Temporal workflow runs the
> investigation. Supermemory is our incident memory. Jarvislabs hosts the model that
> explains the cause. And the Command Center you just saw shows it all live."

| Partner | What it does in PayPulse | Why it matters |
|---|---|---|
| **Temporal** | The whole investigation is one durable workflow: retries, the human-approval signal, the 15-minute approval timer, recovery checks | Incidents never get lost halfway; a crash or restart resumes exactly where it stopped |
| **Supermemory** | Recalls similar past incidents before diagnosing; saves every resolved incident as a postmortem | The team's knowledge compounds instead of living in one person's head |
| **Jarvislabs** | Token Factory serves an open model (DeepSeek V4.1 Flash) behind an OpenAI-compatible API | Open model, our choice of provider, no payment data to public AI APIs; about a second per answer in our tests |
| **Kepler (RubixKube)** | Planned engineer-facing surface for incidents | Say honestly: "next step"; it's not integrated yet |

### 6. Why you can trust it (20 s)

> "Three guardrails. One: the AI can only choose from an allow-list of runbooks; it never
> writes commands. Two: nothing changes without a human approval. Three: every fix is
> idempotent and verified, so if recovery doesn't happen, PayPulse says so and escalates."

### 7. What's next (15 s)

> "Next: connect to real payment telemetry, add Kepler as the engineer surface, and grow
> the runbook library: failover to a backup acquirer, roll back a deploy, throttle a
> failing method."

### 8. Close (10 s)

> "PayPulse: when payments start failing, it finds out why in seconds, remembers past
> fixes, and repairs it with one click of approval. Thank you."

---

## Q&A: likely questions, honest answers

**Is this real payment data?**
No. It's a realistic simulator: four banks, UPI and cards, real-looking error codes and
latency. We inject faults on purpose. The detection, investigation, memory, AI and
workflow are all real and running live.

**What does "restart the connector" actually do here?**
In the simulator it clears the injected fault, the same effect a connector restart has
in the real incident it mirrors. In production that runbook would call your real ops API.

**Why Temporal instead of a cron job or a queue?**
An incident is a long, multi-step process with a human in the middle. Temporal gives
durable state, automatic retries, timers and signals out of the box. If the worker
crashes while waiting for approval, nothing is lost.

**What if the AI is wrong?**
It can't act on its own: a human approves every fix, it can only pick allow-listed
runbooks, and we verify recovery afterwards. If the model's answer is malformed, the
step is retried; if it's not confident, it can choose "escalate".

**Why not just use GPT?**
Payment data is sensitive. We use an open model hosted on Jarvislabs, mask identifiers
before anything is sent, and only send aggregated numbers.

**How does memory help, concretely?**
Before diagnosing, PayPulse searches Supermemory for similar incidents. Today it found
the August HDFC incident and its fix, and the model cited it. After resolution, the new
postmortem is saved, so the system learns from every incident.

**How fast is it?**
Detection in ~10-15 s, AI diagnosis in ~1-5 s, recovery verified ~20-30 s after approval.
The human decision is the only wait.

**How would you deploy it for real?**
Point the detector at real metrics, replace the simulator runbooks with real ops APIs,
run Temporal Cloud or a Temporal cluster, and keep the approval step.

**Where is Kepler?**
Planned as the engineer-facing surface; we prioritised a working end-to-end loop for the
hackathon. (Don't claim it's integrated.)

---

## If something breaks live

| Problem | What to do |
|---|---|
| Incident doesn't appear after 20 s | Presenter keeps talking (guardrails); backup checks `docker compose logs worker`. If nothing in 30 s, play the backup video |
| AI step fails | "The workflow caught the failure and marked it; that's the durability we want." Then switch to the backup video |
| UI won't load | Show the Temporal UI and narrate from the workflow history, or play the video |
| Need a clean restart (takes ~1 min) | `docker compose down -v && docker compose up -d` |

**Never debug on stage.** Switch to the video and keep the story going.

---

## Rehearsal checklist

- [ ] Full run 3 times; aim for 5 minutes total
- [ ] Each person knows their lines for their partner callouts
- [ ] Record one clean run as the backup video
- [ ] Between runs: wait 2 minutes, or `docker compose down -v && docker compose up -d`
- [ ] Note: each rehearsal saves another postmortem to Supermemory, so the memory panel may
  show rehearsal incidents too. That's fine: "it remembered our run from 10 minutes ago."
