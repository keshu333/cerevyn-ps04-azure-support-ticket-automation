"""Integration tests for FastAPI endpoints, database persistence, and approval workflow."""

import pytest
from fastapi.testclient import TestClient


def test_scenario_5_duplicate_ticket_ids_are_rejected(client: TestClient):
    """Scenario 5: Duplicate ticket IDs are rejected and do not overwrite existing records."""
    payload = {
        "ticket_id": "TCK-DUP-001",
        "message": "Original message: I was charged twice for order 12345."
    }
    # Initial creation succeeds
    resp1 = client.post("/tickets", json=payload)
    assert resp1.status_code == 201
    assert resp1.json()["summary"] is not None

    # Duplicate attempt must fail with 409 Conflict
    duplicate_payload = {
        "ticket_id": "TCK-DUP-001",
        "message": "Overwriting message: Something completely different."
    }
    resp2 = client.post("/tickets", json=duplicate_payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()

    # Verify original record was not overwritten
    resp3 = client.get("/tickets/TCK-DUP-001")
    assert resp3.status_code == 200
    assert "Original message" in resp3.json()["message"]


def test_scenario_6_empty_or_whitespace_messages_are_rejected(client: TestClient):
    """Scenario 6: Empty or whitespace-only messages are rejected with validation error."""
    # Empty message
    resp1 = client.post("/tickets", json={"ticket_id": "TCK-EMPTY", "message": ""})
    assert resp1.status_code == 422

    # Whitespace-only message
    resp2 = client.post("/tickets", json={"ticket_id": "TCK-WS", "message": "   \n\t   "})
    assert resp2.status_code == 422


def test_scenario_7_unknown_ticket_ids_return_404(client: TestClient):
    """Scenario 7: Unknown ticket IDs return 404 Not Found."""
    resp = client.get("/tickets/TCK-DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_scenario_8_ticket_creation_persists_in_database(client: TestClient):
    """Scenario 8: Ticket creation persists in the database and is accurately retrievable."""
    payload = {
        "ticket_id": "TCK-PERSIST-001",
        "message": "System down: our primary database crashed with an unhandled exception."
    }
    create_resp = client.post("/tickets", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()

    # Retrieve from DB via GET
    get_resp = client.get("/tickets/TCK-PERSIST-001")
    assert get_resp.status_code == 200
    retrieved_data = get_resp.json()

    assert retrieved_data["ticket_id"] == "TCK-PERSIST-001"
    assert retrieved_data["category"] == "Technical"
    assert retrieved_data["priority"] == "High"
    assert retrieved_data["status"] == "Pending Review"
    assert retrieved_data["assigned_team"] == "Technical Support"


def test_scenario_9_ticket_cannot_become_ready_without_approval(client: TestClient):
    """Scenario 9: Ticket cannot become Ready without explicit approval."""
    payload = {
        "ticket_id": "TCK-READY-GATE",
        "message": "How do I upgrade our subscription tier for next quarter?"
    }
    create_resp = client.post("/tickets", json=payload)
    assert create_resp.status_code == 201
    assert create_resp.json()["status"] == "Pending Review"

    # Verify upon retrieval that it remains in 'Pending Review'
    get_resp = client.get("/tickets/TCK-READY-GATE")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "Pending Review"
    assert get_resp.json()["approved_by"] is None
    assert get_resp.json()["approved_at"] is None


def test_scenario_10_explicit_approval_changes_status_to_ready(client: TestClient):
    """Scenario 10: Explicit approval changes the status to Ready and records reviewer metadata."""
    payload = {
        "ticket_id": "TCK-APPROVE-001",
        "message": "Cannot login to our workspace account due to expired credentials."
    }
    client.post("/tickets", json=payload)

    # Approve ticket
    approve_payload = {
        "reviewer_name": "Supervisor Sarah Conner",
        "notes": "Reviewed and verified user account identity."
    }
    approve_resp = client.post("/tickets/TCK-APPROVE-001/approve", json=approve_payload)
    assert approve_resp.status_code == 200
    data = approve_resp.json()

    assert data["status"] == "Ready"
    assert data["approved_by"] == "Supervisor Sarah Conner"
    assert data["approved_at"] is not None

    # Repeated approval request must return 400 Bad Request
    repeat_resp = client.post("/tickets/TCK-APPROVE-001/approve", json=approve_payload)
    assert repeat_resp.status_code == 400
    assert "already in 'ready' status" in repeat_resp.json()["detail"].lower()


def test_scenario_12_invalid_requests_return_appropriate_errors(client: TestClient):
    """Scenario 12: Invalid requests return appropriate errors (422, 400, etc.)."""
    # Missing ticket_id
    resp1 = client.post("/tickets", json={"message": "Valid complaint message without ID."})
    assert resp1.status_code == 422

    # Message exceeding 2000 characters
    long_message = "A" * 2005
    resp2 = client.post("/tickets", json={"ticket_id": "TCK-LONG", "message": long_message})
    assert resp2.status_code == 422
    assert "2000" in str(resp2.json())

    # Invalid ticket_id characters
    resp3 = client.post("/tickets", json={"ticket_id": "TCK/123$!#", "message": "Valid complaint."})
    assert resp3.status_code == 422

    # Malformed JSON body
    resp4 = client.post(
        "/tickets",
        content="This is not JSON",
        headers={"Content-Type": "application/json"}
    )
    assert resp4.status_code == 422

    # Approve non-existent ticket returns 404
    resp5 = client.post("/tickets/NON-EXISTENT/approve")
    assert resp5.status_code == 404


def test_list_tickets_and_filtering(client: TestClient):
    """Test listing tickets with status and category query filters."""
    client.post("/tickets", json={"ticket_id": "TCK-L-1", "message": "Billing invoice question."})
    client.post("/tickets", json={"ticket_id": "TCK-L-2", "message": "Server crash outage error."})

    # List all
    resp_all = client.get("/tickets")
    assert resp_all.status_code == 200
    assert resp_all.json()["total"] >= 2

    # Filter by category Billing
    resp_billing = client.get("/tickets?category=Billing")
    assert resp_billing.status_code == 200
    assert any(t["ticket_id"] == "TCK-L-1" for t in resp_billing.json()["tickets"])

    # Filter by status Ready (should be empty initially)
    resp_ready = client.get("/tickets?status=Ready")
    assert resp_ready.status_code == 200
    assert all(t["status"] == "Ready" for t in resp_ready.json()["tickets"])


def test_health_check_endpoint(client: TestClient):
    """Test /health endpoint returns 200 OK and database connected status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "version" in data
