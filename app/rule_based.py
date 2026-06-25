"""Rule-based ticket classifier — used as a fallback when the LLM is unavailable."""

import re
from typing import Tuple

from app.models import CaseType, Department, Severity


# ─── Keyword patterns ───────────────────────────────────────────────────────

_PATTERNS: list[Tuple[re.Pattern, CaseType]] = [
    # Phishing / social-engineering (checked first — highest priority)
    (
        re.compile(
            r"\b(otp|pin|password|phish|scam|fraud|hack|social.?engineering|"
            r"suspicious.?call|suspicious.?sms|asking.?for.?otp|asking.?for.?pin|"
            r"share.?otp|share.?pin|share.?password|someone.?called|"
            r"fake.?call|fake.?sms|impersonat|pretend)\b",
            re.IGNORECASE,
        ),
        CaseType.PHISHING_OR_SOCIAL_ENGINEERING,
    ),
    # Wrong transfer
    (
        re.compile(
            r"\b(wrong.?transfer|wrong.?number|wrong.?account|wrong.?person|"
            r"sent.?to.?wrong|transfer.?wrong|mistaken.?transfer|"
            r"accidental.?transfer|accidentally.?sent|sent.?money.?wrong|"
            r"wrong.?recipient|ভুল.?নম্বর|ভুল.?ট্রান্সফার)\b",
            re.IGNORECASE,
        ),
        CaseType.WRONG_TRANSFER,
    ),
    # Payment failed
    (
        re.compile(
            r"\b(payment.?fail|transaction.?fail|balance.?deduct|deducted.?but|"
            r"money.?deducted|failed.?transaction|charge.?but.?not|"
            r"debited.?but|amount.?deducted|পেমেন্ট.?ফেইল|ব্যালেন্স.?কাটা)\b",
            re.IGNORECASE,
        ),
        CaseType.PAYMENT_FAILED,
    ),
    # Refund request
    (
        re.compile(
            r"\b(refund|money.?back|return.?money|reimburse|changed.?my.?mind|"
            r"cancel.?order|cancel.?transaction|want.?back|give.?back|"
            r"রিফান্ড|টাকা.?ফেরত)\b",
            re.IGNORECASE,
        ),
        CaseType.REFUND_REQUEST,
    ),
]

# ─── Department mapping ──────────────────────────────────────────────────────

_DEPARTMENT_MAP: dict[CaseType, Department] = {
    CaseType.WRONG_TRANSFER: Department.DISPUTE_RESOLUTION,
    CaseType.PAYMENT_FAILED: Department.PAYMENTS_OPS,
    CaseType.REFUND_REQUEST: Department.CUSTOMER_SUPPORT,
    CaseType.PHISHING_OR_SOCIAL_ENGINEERING: Department.FRAUD_RISK,
    CaseType.OTHER: Department.CUSTOMER_SUPPORT,
}

# ─── Severity mapping ───────────────────────────────────────────────────────

_SEVERITY_MAP: dict[CaseType, Severity] = {
    CaseType.WRONG_TRANSFER: Severity.HIGH,
    CaseType.PAYMENT_FAILED: Severity.HIGH,
    CaseType.REFUND_REQUEST: Severity.LOW,
    CaseType.PHISHING_OR_SOCIAL_ENGINEERING: Severity.CRITICAL,
    CaseType.OTHER: Severity.LOW,
}


def _classify_case_type(message: str) -> Tuple[CaseType, float]:
    """Return (case_type, confidence) based on keyword matching."""
    for pattern, case_type in _PATTERNS:
        if pattern.search(message):
            return case_type, 0.70
    return CaseType.OTHER, 0.40


def _build_summary(message: str, case_type: CaseType) -> str:
    """Generate a brief, neutral agent summary."""
    # Truncate very long messages
    short = message[:200].strip()
    if len(message) > 200:
        short += "…"

    label = case_type.value.replace("_", " ")
    return f"Customer message classified as {label}. Original: \"{short}\""


def classify_ticket_rule_based(message: str) -> dict:
    """
    Classify a CRM ticket using keyword/rule-based logic.

    Returns a dict matching the LLMClassification shape (without ticket_id).
    """
    case_type, confidence = _classify_case_type(message)
    severity = _SEVERITY_MAP[case_type]
    department = _DEPARTMENT_MAP[case_type]

    # Disputed refund requests get escalated
    if case_type == CaseType.REFUND_REQUEST and re.search(
        r"\b(dispute|unauthorized|didn.?t.?make|not.?my)\b", message, re.IGNORECASE
    ):
        department = Department.DISPUTE_RESOLUTION
        severity = Severity.HIGH
        confidence = 0.65

    human_review = severity == Severity.CRITICAL or case_type == CaseType.PHISHING_OR_SOCIAL_ENGINEERING

    return {
        "case_type": case_type.value,
        "severity": severity.value,
        "department": department.value,
        "agent_summary": _build_summary(message, case_type),
        "human_review_required": human_review,
        "confidence": confidence,
    }
