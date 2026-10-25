import pytest

from app.masking import mask_sensitive


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("card 4111111111111111 failed", "card [CARD ****1111] failed"),
        ("card 4111 1111 1111 1234 failed", "card [CARD ****1234] failed"),
        ("card 4111-1111-1111-9876", "card [CARD ****9876]"),
        ("payer ravi.k@okhdfcbank timed out", "payer [UPI-ID] timed out"),
        ("vpa 9876543210@ybl", "vpa [UPI-ID]"),
    ],
)
def test_identifiers_are_masked(raw: str, expected: str) -> None:
    assert mask_sensitive(raw) == expected


@pytest.mark.parametrize(
    "text",
    [
        "success_rate 0.3898 p95 10218 ms",
        "2026-10-25T10:36:45 deploy v2.4.1",
        '{"total": 59, "bank": "HDFC"}',
    ],
)
def test_ordinary_evidence_is_untouched(text: str) -> None:
    assert mask_sensitive(text) == text
