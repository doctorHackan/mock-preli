"""LLM-based ticket classifier using OpenRouter (openai/gpt-oss-120b)."""

import json
import logging
import re

import httpx

from app.config import settings
from app.models import LLMClassification

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = """\
You are a precise backend microservice classification engine for a digital finance wallet support line.

Given a customer message, analyze it, classify it, and return ONLY a raw, valid JSON object. Do not include markdown code fences (such as ```json), do not include any conversational explanations, and do not include extra text.

Strict Classification & Mapping Rules:
1. Money sent to an incorrect number / recipient:
   - case_type: "wrong_transfer"
   - severity: "high"
   - department: "dispute_resolution"
2. Transaction failed, but customer balance was or might be deducted:
   - case_type: "payment_failed"
   - severity: "high"
   - department: "payments_ops"
3. Customer is asking to return money or cancel a transaction out of a change of mind:
   - case_type: "refund_request"
   - severity: "low"
   - department: "customer_support"
4. Suspicious calls, SMS, fake cash-out offers, or anyone asking for secret credentials:
   - case_type: "phishing_or_social_engineering"
   - severity: "critical"
   - department: "fraud_risk"
5. General system issues, app crashes, or queries not covered above:
   - case_type: "other"
   - severity: "low"
   - department: "customer_support"

Field Requirements:
- human_review_required (boolean): Must be true if severity is "critical" OR case_type is "phishing_or_social_engineering". Otherwise, false.
- confidence (float): A value between 0.0 and 1.0 representing classification certainty.
- agent_summary (string): A neutral 1-2 sentence description of the customer's issue (e.g., "Customer reports..."). 

CRITICAL SAFETY RULE:
The agent_summary field must NEVER ask or suggest asking the customer to share a PIN, OTP, password, or full card number. Frame the summary purely as a passive observation of what the customer reported.

Example for expected JSON Output Format (Strictly follow this structure):
{
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending funds to an incorrect number and requests recovery support.",
  "human_review_required": true,
  "confidence": 0.95
}
"""

# Regex to strip markdown code fences the LLM might add despite instructions
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


async def classify_ticket_llm(message: str) -> dict | None:
    """
    Call OpenRouter to classify a ticket.

    Returns a dict matching `LLMClassification` fields on success, or `None`
    on any failure (network, auth, malformed response, etc.).
    """
    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY not set, skipping LLM classification.")
        return None

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
    }

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/crm-ticket-sorting-api",
        "X-Title": "CRM Ticket Sorting API",
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        raw_content: str = data["choices"][0]["message"]["content"]

        # Strip markdown fences if present
        fence_match = _FENCE_RE.search(raw_content)
        json_str = fence_match.group(1).strip() if fence_match else raw_content.strip()

        parsed = json.loads(json_str)

        # Validate through Pydantic
        classification = LLMClassification(**parsed)
        return classification.model_dump()

    except httpx.HTTPStatusError as exc:
        logger.error("OpenRouter HTTP error %s: %s", exc.response.status_code, exc.response.text[:300])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error("Failed to parse LLM response: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error during LLM classification: %s", exc)

    return None
