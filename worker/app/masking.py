"""Removes payment identifiers before anything is sent to the LLM.

Evidence is aggregates today, so this is a safety net: if a UPI ID or card number ever
slips into a deploy note or error text, it is masked before leaving our network.
"""

import re

# 13-19 digits, optionally grouped by spaces or dashes: the shape of a card number.
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
# name@handle, e.g. ravi.k@okhdfcbank. Also catches email addresses, which is fine.
_UPI = re.compile(r"\b[\w.\-]{2,256}@[a-zA-Z][a-zA-Z0-9.\-]{1,63}\b")


def _mask_card(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return f"[CARD ****{digits[-4:]}]"


def mask_sensitive(text: str) -> str:
    text = _CARD.sub(_mask_card, text)
    return _UPI.sub("[UPI-ID]", text)
