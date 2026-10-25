"""Decides when to open an incident. Pure: no I/O, so it is unit-tested directly."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from app.contracts import Trigger


def find_triggers(
    groups: Iterable[Mapping[str, Any]], min_success_rate: float, min_payments: int
) -> list[Trigger]:
    """One trigger per bank: its worst bank+method group below the threshold.

    Groups with fewer than min_payments are ignored so a couple of unlucky failures
    in a quiet minute can't page anyone. No maths here: /stats already did it in SQL.
    """
    worst: dict[str, Mapping[str, Any]] = {}
    for group in groups:
        if group["total"] < min_payments or group["success_rate"] >= min_success_rate:
            continue
        current = worst.get(group["bank"])
        if current is None or group["success_rate"] < current["success_rate"]:
            worst[group["bank"]] = group

    return [
        Trigger(
            bank=g["bank"],
            method=g["method"],
            success_rate=g["success_rate"],
            total=g["total"],
            top_error_code=g.get("top_error_code"),
        )
        for g in sorted(worst.values(), key=lambda g: g["bank"])
    ]


def may_open_incident(
    is_running: bool, last_closed_at: datetime | None, now: datetime, cooldown_s: float
) -> bool:
    """Open a new incident only if none is running and the last one closed a while ago.

    Right after a fix the detector's stats window still holds the bad minute; the
    cooldown stops it from reopening an incident for a bank that already recovered.
    """
    if is_running:
        return False
    return last_closed_at is None or (now - last_closed_at).total_seconds() >= cooldown_s
