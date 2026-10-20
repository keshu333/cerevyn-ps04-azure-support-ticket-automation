"""FastAPI route handlers for support ticket automation.

Implements ticket creation, classification, retrieval, listing, human-in-the-loop approval,
and health checks.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.database import (
    check_db_health,
    get_ticket,
    insert_ticket,
    list_tickets,
    update_ticket_approval,
)
from app.models.schemas import (
    Category,
    HealthResponse,
    TicketApproveRequest,
    TicketCreate,
    TicketListResponse,
    TicketResponse,
    TicketStatus,
)
from app.services.classifier import classify_ticket
from app.services.responder import generate_draft_response, generate_summary

router = APIRouter()


def get_current_db_path() -> str:
    """Dependency provider for database path, facilitating isolated testing."""
    return settings.DATABASE_PATH


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and classify a support ticket",
    description="Ingests a customer complaint, runs deterministic NLP classification, assigns priority and support team, generates a draft response, and sets status to Pending Review."
)
def create_ticket(
    payload: TicketCreate,
    db_path: str = Depends(get_current_db_path)
) -> TicketResponse:
    # 1. Check for duplicate ticket_id to prevent accidental overwrites
    existing = get_ticket(payload.ticket_id, custom_path=db_path)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket with ID '{payload.ticket_id}' already exists. Duplicate IDs are rejected."
        )

    # 2. Run deterministic domain classification
    classification = classify_ticket(payload.message)

    # 3. Deterministic summary and draft generation
    summary = generate_summary(payload.message, classification.category)
    draft_response = generate_draft_response(
        ticket_id=payload.ticket_id,
        category=classification.category,
        priority=classification.priority,
        assigned_team=classification.assigned_team,
        summary=summary,
    )

    now = datetime.now(timezone.utc).isoformat()

    ticket_record = {
        "ticket_id": payload.ticket_id,
        "message": payload.message,
        "category": classification.category.value,
        "priority": classification.priority.value,
        "assigned_team": classification.assigned_team.value,
        "summary": summary,
        "draft_response": draft_response,
        "status": TicketStatus.PENDING_REVIEW.value,
        "confidence_score": classification.confidence_score,
        "classification_explanation": classification.classification_explanation,
        "needs_human_review": classification.needs_human_review,
        "approved_by": None,
        "approved_at": None,
        "created_at": now,
        "updated_at": now,
    }

    # 4. Persist in SQLite
    try:
        saved = insert_ticket(ticket_record, custom_path=db_path)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket with ID '{payload.ticket_id}' already exists."
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist ticket record: {str(exc)}"
        )

    return TicketResponse(**saved)


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Retrieve a ticket by ID",
    description="Fetches stored details, classification signals, and current approval state for a single ticket."
)
def get_single_ticket(
    ticket_id: str,
    db_path: str = Depends(get_current_db_path)
) -> TicketResponse:
    ticket = get_ticket(ticket_id, custom_path=db_path)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found."
        )
    return TicketResponse(**ticket)


@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List all tickets",
    description="Retrieve stored tickets with optional status and category filters."
)
def get_all_tickets(
    status_filter: Optional[TicketStatus] = Query(None, alias="status", description="Filter by ticket status"),
    category_filter: Optional[Category] = Query(None, alias="category", description="Filter by category"),
    db_path: str = Depends(get_current_db_path)
) -> TicketListResponse:
    rows = list_tickets(
        status=status_filter.value if status_filter else None,
        category=category_filter.value if category_filter else None,
        custom_path=db_path
    )
    tickets = [TicketResponse(**r) for r in rows]
    return TicketListResponse(total=len(tickets), tickets=tickets)


@router.post(
    "/tickets/{ticket_id}/approve",
    response_model=TicketResponse,
    summary="Approve ticket draft response",
    description="Human agent approval step. Transitions ticket from 'Pending Review' to 'Ready'. Repeated approvals return an error."
)
def approve_ticket_endpoint(
    ticket_id: str,
    payload: Optional[TicketApproveRequest] = None,
    db_path: str = Depends(get_current_db_path)
) -> TicketResponse:
    # 1. Fetch ticket to verify existence and check current state
    ticket = get_ticket(ticket_id, custom_path=db_path)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found."
        )

    # 2. Validate current workflow state
    current_status = ticket.get("status")
    if current_status == TicketStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ticket '{ticket_id}' is already in 'Ready' status. Cannot approve again."
        )

    if current_status != TicketStatus.PENDING_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition: Cannot approve ticket with status '{current_status}'."
        )

    reviewer = payload.reviewer_name if payload and payload.reviewer_name else "Support Lead"

    # 3. Transition to Ready
    updated = update_ticket_approval(
        ticket_id=ticket_id,
        reviewer_name=reviewer,
        custom_path=db_path
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update approval status for ticket '{ticket_id}'."
        )

    return TicketResponse(**updated)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Returns server status and database connectivity status."
)
def health_check(db_path: str = Depends(get_current_db_path)) -> HealthResponse:
    db_ok = check_db_health(custom_path=db_path)
    db_status = "connected" if db_ok else "unreachable"

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database=db_status,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
