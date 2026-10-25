# 2026-08-12 HDFC gateway timeouts

Bank: HDFC. Methods affected: UPI and CARD.

Symptoms: HDFC success rate fell from 98% to about 35% within two minutes. Almost every
failure was BANK_TIMEOUT and p95 latency jumped from about 600 ms to over 10 seconds.
SBI, ICICI and AXIS stayed healthy at around 98%. No deploys in the hour before.

Root cause: the HDFC bank connector's connection pool filled with stuck connections after
a short latency spike on HDFC's gateway. New payments waited for a free connection and
timed out at the 10 second gateway limit.

Fix: restarted the HDFC bank connector (runbook restart_bank_connector). Stuck
connections were dropped and HDFC success rate was back to 98% about 40 seconds later.

Lesson: one bank timing out on all methods while other banks are fine points to that
bank's connector, not to our own code. A connector restart is safe and fast.
