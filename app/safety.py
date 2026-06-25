"""Safety validator for agent_summary — ensures no sensitive data requests."""

import re

_UNSAFE_PATTERNS = re.compile(
    r"\b(share.{0,20}(pin|otp|password|card.?number)|"
    r"send.{0,20}(pin|otp|password|card.?number)|"
    r"provide.{0,20}(pin|otp|password|card.?number)|"
    r"tell.{0,20}(pin|otp|password|card.?number)|"
    r"give.{0,20}(pin|otp|password|card.?number)|"
    r"enter.{0,20}(pin|otp|password|card.?number))\b",
    re.IGNORECASE,
)


def sanitize_summary(summary: str) -> str:
    """
    Return the summary if it is safe.
    If it contains unsafe language, return a generic safe replacement.
    """
    if _UNSAFE_PATTERNS.search(summary):
        return "Customer reported an issue. A human agent should review the original message."
    return summary
