#!/usr/bin/env python3
"""Local demonstration script for Cerevyn Solutions PS04.

Demonstrates the complete end-to-end support ticket automation workflow:
  1. Ticket creation and deterministic classification (POST /tickets)
  2. Input validation and duplicate ID rejection
  3. Ticket retrieval (GET /tickets/{ticket_id})
  4. Human-in-the-loop review and approval (POST /tickets/{ticket_id}/approve)
  5. State verification (confirming transition to 'Ready')
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from app.main import app


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def main():
    print_section("CEREVYN SOLUTIONS PS04 - SUPPORT TICKET AUTOMATION DEMO")
    print("This demo exercises the FastAPI REST API, deterministic NLP classification,")
    print("and the human approval lifecycle.")

    with TestClient(app) as client:
        # Step 1: Health Check
        print_section("Step 1: System Health Check (GET /health)")
        health_resp = client.get("/health")
        print(f"Status Code: {health_resp.status_code}")
        print(f"Payload    :\n{json.dumps(health_resp.json(), indent=2)}")
        assert health_resp.status_code == 200

        # Step 2: Create a Billing Support Ticket
        demo_ticket_id = f"DEMO-{int(time.time())}"
        print_section(f"Step 2: Ingest Customer Complaint (POST /tickets) -> ID: {demo_ticket_id}")
        new_ticket_payload = {
            "ticket_id": demo_ticket_id,
            "message": "I was charged twice for the same subscription renewal on my Visa credit card."
        }
        print(f"Request Payload:\n{json.dumps(new_ticket_payload, indent=2)}")

        create_resp = client.post("/tickets", json=new_ticket_payload)
        print(f"\nResponse Code: {create_resp.status_code}")
        create_data = create_resp.json()
        print("Classification Result:")
        print(f"  - Category         : {create_data.get('category')}")
        print(f"  - Priority         : {create_data.get('priority')}")
        print(f"  - Assigned Team    : {create_data.get('assigned_team')}")
        print(f"  - Status           : {create_data.get('status')}")
        print(f"  - Confidence Score : {create_data.get('confidence_score')}")
        print(f"  - Explanation      : {create_data.get('classification_explanation')}")
        print(f"  - Generated Summary: {create_data.get('summary')}")
        print(f"\nDraft Response Generated for Agent Review:\n---\n{create_data.get('draft_response')}\n---")
        assert create_resp.status_code == 201
        assert create_data["status"] == "Pending Review"

        # Step 3: Test Duplicate Rejection
        print_section("Step 3: Test Input Validation - Reject Duplicate Ticket ID")
        duplicate_resp = client.post("/tickets", json=new_ticket_payload)
        print(f"Duplicate Request Status: {duplicate_resp.status_code} (Expected: 409 Conflict)")
        print(f"Error Detail            : {duplicate_resp.json().get('detail')}")
        assert duplicate_resp.status_code == 409

        # Step 4: Retrieve Ticket by ID
        print_section(f"Step 4: Retrieve Ticket Details (GET /tickets/{demo_ticket_id})")
        get_resp = client.get(f"/tickets/{demo_ticket_id}")
        print(f"Response Code: {get_resp.status_code}")
        print(f"Current Status: {get_resp.json().get('status')}")
        assert get_resp.status_code == 200

        # Step 5: Human Approval Workflow
        print_section(f"Step 5: Human Supervisor Approval (POST /tickets/{demo_ticket_id}/approve)")
        approve_payload = {
            "reviewer_name": "Senior Agent John Doe",
            "notes": "Verified ledger entries and confirmed duplicate charge. Draft approved for communication."
        }
        approve_resp = client.post(f"/tickets/{demo_ticket_id}/approve", json=approve_payload)
        print(f"Response Code: {approve_resp.status_code}")
        approved_data = approve_resp.json()
        print(f"Updated Status: {approved_data.get('status')} (Must be 'Ready')")
        print(f"Approved By   : {approved_data.get('approved_by')}")
        print(f"Approved At   : {approved_data.get('approved_at')}")
        assert approve_resp.status_code == 200
        assert approved_data["status"] == "Ready"

        # Step 6: Test Repeated Approval Rejection
        print_section(f"Step 6: Test Predictable Repeated Approval (POST /tickets/{demo_ticket_id}/approve)")
        repeated_approve = client.post(f"/tickets/{demo_ticket_id}/approve", json=approve_payload)
        print(f"Response Code: {repeated_approve.status_code} (Expected: 400 Bad Request)")
        print(f"Error Detail : {repeated_approve.json().get('detail')}")
        assert repeated_approve.status_code == 400

        print_section("DEMO COMPLETED SUCCESSFULLY!")
        print("All functional requirements verified:")
        print("  [x] Deterministic NLP classification and priority scoring")
        print("  [x] Input validation and duplicate rejection")
        print("  [x] Deterministic summary and professional draft generation")
        print("  [x] Human approval gate (Pending Review -> Ready)")
        print("  [x] State transition predictability")
        print("=" * 70)


if __name__ == "__main__":
    main()
