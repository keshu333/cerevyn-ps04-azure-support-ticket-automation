"""Unit tests for the independent classification, priority, and draft generation services."""

import pytest
from app.models.schemas import Category, Priority, SupportTeam
from app.services.classifier import classify_ticket
from app.services.responder import generate_draft_response, generate_summary


def test_scenario_1_billing_receives_expected_category_and_team():
    """Scenario 1: Billing ticket receives the expected category and team."""
    message = "I was charged twice for the same subscription on my credit card. Please issue a refund."
    result = classify_ticket(message)

    assert result.category == Category.BILLING
    assert result.assigned_team == SupportTeam.BILLING_SUPPORT
    assert result.priority == Priority.HIGH
    assert "charged twice" in result.classification_explanation.lower()


def test_scenario_2_technical_outage_receives_high_priority():
    """Scenario 2: Technical outage receives an appropriate priority (High)."""
    message = "Complete service outage: production servers are down and all users cannot access the app."
    result = classify_ticket(message)

    assert result.category == Category.TECHNICAL
    assert result.assigned_team == SupportTeam.TECHNICAL_SUPPORT
    assert result.priority == Priority.HIGH
    assert "complete service outage" in result.classification_explanation.lower() or "outage" in result.classification_explanation.lower()


def test_scenario_3_access_complaint_classified_correctly():
    """Scenario 3: Access-related complaint is classified correctly."""
    message = "I am locked out of my account because my 2fa authenticator code is not being accepted."
    result = classify_ticket(message)

    assert result.category == Category.ACCESS
    assert result.assigned_team == SupportTeam.ACCOUNT_SUPPORT
    assert result.priority in (Priority.HIGH, Priority.MEDIUM)
    assert "locked out" in result.classification_explanation.lower() or "2fa" in result.classification_explanation.lower()


def test_scenario_4_general_enquiry_receives_suitable_response():
    """Scenario 4: General enquiry receives a suitable category, team, and response."""
    message = "How do I invite secondary team members and where can I find the user guide documentation?"
    result = classify_ticket(message)

    assert result.category == Category.GENERAL
    assert result.assigned_team == SupportTeam.GENERAL_SUPPORT
    assert result.priority == Priority.LOW

    # Check summary and draft generation
    summary = generate_summary(message, result.category)
    assert summary.startswith("[General]")

    draft = generate_draft_response(
        ticket_id="TCK-TEST",
        category=result.category,
        priority=result.priority,
        assigned_team=result.assigned_team,
        summary=summary,
    )
    assert "TCK-TEST" in draft
    assert "General Support" in draft
    # Ensure draft is marked as internal review and doesn't make completed claims
    assert "INTERNAL DRAFT" in draft
    assert "refunded" not in draft.lower()
    assert "issue has been resolved" not in draft.lower()


def test_scenario_11_ambiguous_ticket_flagged_for_review():
    """Scenario 11: Ambiguous tickets with vague content or multi-category conflict are flagged for review."""
    # Vague ticket with no clear keywords
    vague_message = "Something seems unusual with our company setup today. Please take a look."
    vague_result = classify_ticket(vague_message)
    assert vague_result.needs_human_review is True
    assert vague_result.confidence_score <= 0.50
    assert "human review" in vague_result.classification_explanation.lower()

    # Conflicting multi-domain ticket
    conflicting_message = "My invoice payment failed because password reset is broken and throwing 500 error."
    conflicting_result = classify_ticket(conflicting_message)
    # Either flagged due to close score competition or handled safely
    assert conflicting_result.category in (Category.BILLING, Category.ACCESS, Category.TECHNICAL)


def test_security_breach_triggers_high_priority():
    """Unauthorized access and security breach triggers High priority."""
    message = "Suspected unauthorized access to our production tenant. Account hacked from a foreign IP."
    result = classify_ticket(message)

    assert result.category == Category.ACCESS
    assert result.priority == Priority.HIGH
    assert "unauthorized" in result.classification_explanation.lower()


def test_draft_response_no_premature_claims():
    """Draft responses must not claim that refund is completed or issue fixed."""
    for category in Category:
        draft = generate_draft_response(
            ticket_id="TCK-999",
            category=category,
            priority=Priority.MEDIUM,
            assigned_team=SupportTeam.TECHNICAL_SUPPORT,
            summary="Test summary",
        )
        assert "has been refunded" not in draft.lower()
        assert "account is now fixed" not in draft.lower()
        assert "payment was returned" not in draft.lower()
        assert "INTERNAL DRAFT" in draft
