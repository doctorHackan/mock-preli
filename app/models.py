"""Pydantic models for the CRM Ticket Sorting API."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────


class Channel(str, Enum):
    """Supported inbound channels."""

    APP = "app"
    SMS = "sms"
    CALL_CENTER = "call_center"
    MERCHANT_PORTAL = "merchant_portal"


class Locale(str, Enum):
    """Supported message locales."""

    BN = "bn"
    EN = "en"
    MIXED = "mixed"


class CaseType(str, Enum):
    """Classification category for a CRM ticket."""

    WRONG_TRANSFER = "wrong_transfer"
    PAYMENT_FAILED = "payment_failed"
    REFUND_REQUEST = "refund_request"
    PHISHING_OR_SOCIAL_ENGINEERING = "phishing_or_social_engineering"
    OTHER = "other"


class Severity(str, Enum):
    """Severity level of the ticket."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Department(str, Enum):
    """Responsible team for handling the ticket."""

    CUSTOMER_SUPPORT = "customer_support"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENTS_OPS = "payments_ops"
    FRAUD_RISK = "fraud_risk"


# ─── Request / Response ─────────────────────────────────────────────────────


class TicketRequest(BaseModel):
    """Incoming CRM ticket payload."""

    ticket_id: str = Field(..., description="Unique ticket identifier, echoed back in the response.")
    channel: Optional[Channel] = Field(None, description="Inbound channel (app, sms, call_center, merchant_portal).")
    locale: Optional[Locale] = Field(None, description="Message locale (bn, en, mixed).")
    message: str = Field(..., min_length=1, description="Free-text customer complaint.")


class TicketResponse(BaseModel):
    """Classified CRM ticket response."""

    ticket_id: str = Field(..., description="Echoed from the request.")
    case_type: CaseType = Field(..., description="Classification category.")
    severity: Severity = Field(..., description="Ticket severity level.")
    department: Department = Field(..., description="Team responsible for handling.")
    agent_summary: str = Field(..., description="Neutral one- or two-sentence summary for the agent.")
    human_review_required: bool = Field(..., description="True for phishing or critical cases.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score.")


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str = "ok"
    service: str = "crm-ticket-sorting-api"
    version: str = "1.0.0"


# ─── LLM structured output helper ───────────────────────────────────────────


class LLMClassification(BaseModel):
    """Shape we ask the LLM to return (no ticket_id, we inject that ourselves)."""

    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    human_review_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
