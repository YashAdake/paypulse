# 2026-09-21 ICICI card issuer declines

Bank: ICICI. Method affected: CARD.

Symptoms: ICICI CARD success rate fell to 60%. Failures were ISSUER_DECLINED and came
back fast (normal latency, about 400 ms). UPI was unaffected. No deploys.

Root cause: ICICI's own risk engine started declining a range of cards after a rule
change on the bank's side.

Fix: escalated to ICICI's operations desk, who reverted the rule. Nothing on our side
could fix it; a connector restart was tried and changed nothing.

Lesson: fast declines from one issuer are the bank's decision, not a connectivity
problem. Escalate to the bank instead of restarting anything.
