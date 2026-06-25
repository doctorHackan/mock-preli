"""CRM Ticket Sorting API — FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.llm_classifier import classify_ticket_llm
from app.models import HealthResponse, TicketRequest, TicketResponse
from app.rule_based import classify_ticket_rule_based
from app.safety import sanitize_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CRM Ticket Sorting API",
    description="Classifies customer CRM tickets by type, severity, and department.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoints ───────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Return service health status."""
    return HealthResponse()


@app.post("/sort-ticket", response_model=TicketResponse)
async def sort_ticket(ticket: TicketRequest):
    """Classify and structure a CRM ticket.

    Strategy:
    1. Try the LLM classifier (OpenRouter openai/gpt-oss-120b).
    2. On any failure, fall back to the rule-based classifier.
    3. Sanitize the agent_summary for safety.
    """
    logger.info("Processing ticket %s (channel=%s, locale=%s)", ticket.ticket_id, ticket.channel, ticket.locale)

    # 1. Attempt LLM classification
    result = await classify_ticket_llm(ticket.message)

    if result is None:
        # 2. Fallback to rule-based
        logger.info("[LLM unavailable]: using rule-based classifier for %s", ticket.ticket_id)
        result = classify_ticket_rule_based(ticket.message)

    # 3. Sanitize summary
    result["agent_summary"] = sanitize_summary(result["agent_summary"])

    return TicketResponse(ticket_id=ticket.ticket_id, **result)
