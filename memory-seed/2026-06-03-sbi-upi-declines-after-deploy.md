# 2026-06-03 SBI UPI failures after upi-router deploy

Bank: SBI. Method affected: UPI only. CARD was healthy.

Symptoms: SBI UPI success rate dropped to 70%. Failures were mostly INVALID_VPA and
latency stayed normal. The drop started four minutes after deploy upi-router v3.2.0.

Root cause: the deploy shipped a stricter VPA format check that rejected valid handles.

Fix: rolled back upi-router to v3.1.4 (manual, by the on-call engineer). Restarting
connectors did not help, because the bank was never slow.

Lesson: failures on one method, with normal latency and a deploy just before, point to
our own release. Escalate for a rollback; do not restart connectors.
