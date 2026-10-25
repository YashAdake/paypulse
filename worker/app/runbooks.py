"""The only remediations PayPulse may run. The LLM picks one; it never writes commands."""

ESCALATE = "escalate"

RUNBOOKS: dict[str, str] = {
    "restart_bank_connector": (
        "Restart the bank connector: drops stuck connections to the bank's gateway. "
        "Use when one bank's payments time out across methods while other banks are healthy."
    ),
    ESCALATE: "No safe automatic fix: hand over to the on-call engineer.",
}


def describe(runbook: str, bank: str) -> str:
    if runbook == "restart_bank_connector":
        return f"Restart the {bank} bank connector"
    return "Escalate to the on-call engineer"
