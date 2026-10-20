"""Pydantic schemas for request and response validation.

Enforces strict input validation, consistent status types, and comprehensive
response structures for the support ticket API.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    """Allowed ticket categories."""
    BILLING = "Billing"
    TECHNICAL = "Technical"
    ACCESS = "Access"
    GENERAL = "General"


class Priority(str, Enum):
    """Documented priority levels."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TicketStatus(str, Enum):
    """Ticket workflow approval statuses."""
    PENDING_REVIEW = "Pending Review"
    READY = "Ready"


class SupportTeam(str, Enum):
    """Assigned support teams."""
    BILLING_SUPPORT = "Billing Support"
    TECHNICAL_SUPPORT = "Technical Support"
    ACCOUNT_SUPPORT = "Account Support"
    GENERAL_SUPPORT = "General Support"


class TicketCreate(BaseModel):
    """Request schema for creating a new support ticket."""

    ticket_id: str = Field(
        ...,
        description="Unique identifier for the ticket (e.g., TCK-001).",
        min_length=1,
        max_length=64,
        examples=["TCK-001"]
    )
    message: str = Field(
        ...,
        description="Customer complaint or inquiry message.",
        min_length=5,
        max_length=2000,
        examples=["I was charged twice for the same order"]
    )

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("ticket_id cannot be empty or whitespace-only.")
        # Ensure ticket_id has safe characters (alphanumeric, dashes, underscores)
        for char in trimmed:
            if not (char.isalnum() or char in ("-", "_", ".")):
                raise ValueError(
                    f"ticket_id contains invalid character: '{char}'. Only alphanumeric, '-', '_', '.' are permitted."
                )
        return trimmed

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message cannot be empty or whitespace-only.")
        if len(trimmed) < 5:
            raise ValueError("message must contain at least 5 characters.")
        if len(trimmed) > 2000:
            raise ValueError("message exceeds maximum allowed length of 2000 characters.")
        return trimmed


class TicketApproveRequest(BaseModel):
    """Optional payload for ticket approval."""
    reviewer_name: Optional[str] = Field(
        default="Support Lead",
        description="Name or ID of human reviewer who approved the response."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional internal notes logged during approval."
    )


class TicketResponse(BaseModel):
    """Complete ticket representation returned by API."""

    ticket_id: str
    message: str
    category: Category
    priority: Priority
    assigned_team: SupportTeam
    summary: str
    draft_response: str
    status: TicketStatus
    confidence_score: float = Field(
        ...,
        description="Explainable heuristic score (0.0 to 1.0) based on keyword matching signal strength."
    )
    classification_explanation: str = Field(
        ...,
        description="Human-readable explanation of why this category and priority were assigned."
    )
    needs_human_review: bool = Field(
        default=False,
        description="True if ambiguity or low confidence necessitates explicit human triage."
    )
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "ticket_id": "TCK-001",
                "message": "I was charged twice for the same order",
                "category": "Billing",
                "priority": "High",
                "assigned_team": "Billing Support",
                "summary": "Customer reports double charge for the same order.",
                "draft_response": "Hello, thank you for reaching out. We have logged your double charge inquiry and our Billing Support team is actively reviewing the transaction records. We will provide an update within 24 business hours.",
                "status": "Pending Review",
                "confidence_score": 0.85,
                "classification_explanation": "Matched billing keyword 'charged twice' with financial impact signaling High priority.",
                "needs_human_review": False,
                "approved_by": None,
                "approved_at": None,
                "created_at": "2026-10-14T12:00:00Z",
                "updated_at": "2026-10-14T12:00:00Z"
            }
        }
    }


class TicketListResponse(BaseModel):
    """Response schema for listing tickets."""
    total: int
    tickets: List[TicketResponse]


class HealthResponse(BaseModel):
    """Health check endpoint response."""
    status: str
    database: str
    version: str
    timestamp: str
