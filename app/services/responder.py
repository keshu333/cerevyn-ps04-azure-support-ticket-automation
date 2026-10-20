"""Summary extraction and draft response generation.

Generates concise summaries and professional draft responses using category templates.
Drafts are strictly intended for internal human review and avoid asserting unverified
actions (e.g., falsely claiming refunds or completed account fixes).
"""

import re
from typing import Dict
from app.models.schemas import Category, Priority, SupportTeam

DRAFT_TEMPLATES: Dict[Category, str] = {
    Category.BILLING: (
        "Hello,\n\n"
        "Thank you for contacting Cerevyn Support. We have received your billing inquiry regarding ticket "
        "[{ticket_id}]. Our Billing Support team is currently reviewing the transaction logs and payment "
        "records associated with your account. A billing specialist will follow up with verified details "
        "and next steps.\n\n"
        "Best regards,\n"
        "Cerevyn Billing Support Team\n"
        "[INTERNAL DRAFT - Pending Human Agent Verification]"
    ),
    Category.TECHNICAL: (
        "Hello,\n\n"
        "Thank you for reporting this technical issue (Ticket: [{ticket_id}]). Our Technical Support team "
        "has logged the incident and is analyzing service telemetry, logs, and potential error states. "
        "We are actively diagnosing the root cause and will follow up with troubleshooting steps or a status update.\n\n"
        "Best regards,\n"
        "Cerevyn Technical Support Team\n"
        "[INTERNAL DRAFT - Pending Human Agent Verification]"
    ),
    Category.ACCESS: (
        "Hello,\n\n"
        "Thank you for reaching out regarding your account access (Ticket: [{ticket_id}]). Our Account Support team "
        "has received your request and is reviewing your account state and verification records in accordance "
        "with our security policies. A support agent will verify your identity before any credential or access changes.\n\n"
        "Best regards,\n"
        "Cerevyn Account Support Team\n"
        "[INTERNAL DRAFT - Pending Human Agent Verification]"
    ),
    Category.GENERAL: (
        "Hello,\n\n"
        "Thank you for contacting Cerevyn Support (Ticket: [{ticket_id}]). We have received your message and "
        "our General Support team is reviewing your question. We will provide helpful guidance and documentation "
        "shortly.\n\n"
        "Best regards,\n"
        "Cerevyn General Support Team\n"
        "[INTERNAL DRAFT - Pending Human Agent Verification]"
    ),
}


def generate_summary(message: str, category: Category) -> str:
    """Extract a concise, deterministic single-line summary from the message."""
    # Clean whitespace
    single_line = " ".join(message.split()).strip()

    # Split into first sentence
    sentences = re.split(r"(?<=[.!?])\s+", single_line)
    first_sentence = sentences[0] if sentences else single_line

    # Cap length to 120 characters
    if len(first_sentence) > 120:
        first_sentence = first_sentence[:117] + "..."

    # Ensure it ends with a period
    if not first_sentence.endswith((".", "!", "?")):
        first_sentence += "."

    return f"[{category.value}] {first_sentence}"


def generate_draft_response(
    ticket_id: str,
    category: Category,
    priority: Priority,
    assigned_team: SupportTeam,
    summary: str,
) -> str:
    """Generate a template-based professional draft response for human agent review."""
    template = DRAFT_TEMPLATES.get(category, DRAFT_TEMPLATES[Category.GENERAL])
    return template.format(
        ticket_id=ticket_id,
        category=category.value,
        priority=priority.value,
        team=assigned_team.value,
    )
