# Cerevyn Solutions PS04 — Azure Support Ticket Automation

[![CI](https://github.com/placeholder-org/cerevyn-ps04/actions/workflows/ci.yml/badge.svg)](https://github.com/placeholder-org/cerevyn-ps04/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.13+-e92063.svg)](https://docs.pydantic.dev)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An AI-assisted support ticket REST API built for the **Cerevyn Solutions Software Developer Trainee Technical Assessment (Problem Statement PS04)**.

The system ingests customer support complaints, classifies them into functional categories, assigns priority levels and specialized support teams, extracts a deterministic summary, drafts an internal response template, and enforces **human-in-the-loop review** before any draft response can be finalized as **Ready**.

---

## Candidate Information

- **Candidate Name**: `[Candidate Name]`
- **Candidate Roll Number / ID**: `[Candidate Roll Number]`
- **Branch / Specialization**: `[Candidate Branch / Degree]`
- **Problem Statement ID**: `PS04 — Azure Support Ticket Automation`
- **Assessment Target**: Cerevyn Solutions Software Developer Trainee Technical Assessment

---

## 1. Project Overview & Features

### Core Objectives
1. **Deterministic NLP & Heuristic Classification**: Implements an explainable, transparent baseline classifier using phrase-weighted lexicons and precedence rules. Requires zero paid third-party LLMs or external API keys.
2. **Ambiguity & Uncertainty Routing**: Transparently flags vague tickets or multi-category conflicts for mandatory human triage (`needs_human_review = True`), avoiding fake confidence scores.
3. **Draft Response & Summary Generation**: Automatically generates a single-sentence problem summary and a polite, professional draft response. Drafts strictly avoid making unverified claims (such as claiming a refund was already processed or an account unlocked).
4. **Human Approval Lifecycle**: Guarantees that no response leaves the system in a finalized state without human sign-off (`Pending Review` &rarr; `Ready`).
5. **Reliable Persistence**: Uses parameterized SQLite operations to prevent SQL injection and duplicate ticket overwrites.
6. **Containerization & CI/CD**: Ready for local deployment via Docker and automated testing via GitHub Actions CI and manual Azure App Service OIDC deployment.

---

## 2. System Architecture

```
                               ┌─────────────────────────────────┐
                               │     Customer / Support Agent    │
                               └────────────────┬────────────────┘
                                                │ HTTP / JSON
                                                ▼
                               ┌─────────────────────────────────┐
                               │       FastAPI Application       │
                               │     (/tickets, /docs, /health)  │
                               └────────┬───────────────┬────────┘
                                        │               │
                           Classification & Drafting    │ Parameterized Queries
                                        ▼               ▼
         ┌──────────────────────────────────────┐  ┌───────────────────────────┐
         │     Deterministic Service Engine     │  │      SQLite Database      │
         │ - Multi-Phrase Weighted Scoring      │  │ - tickets table           │
         │ - Precedence: High > Medium > Low    │  │ - Parameterized SQL       │
         │ - Ambiguity & Tie-Breaker Detection  │  │ - Isolated DB in pytest   │
         │ - Professional Draft Generator       │  └───────────────────────────┘
         └──────────────────────────────────────┘
```

### Module Organization
```
cerevyn-ps04/
├── app/
│   ├── __init__.py           # Package version definition
│   ├── main.py               # FastAPI application entry point, lifespan, CORS
│   ├── config.py             # Environment configuration and settings
│   ├── database.py           # SQLite connection, DDL migration, parameterized queries
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py         # Endpoints: POST /tickets, GET /tickets, approval, health
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic v2 schemas and validation logic
│   └── services/
│       ├── __init__.py
│       ├── classifier.py     # Deterministic NLP classification and priority engine
│       └── responder.py      # Summary extraction and template draft generation
├── sample_data/
│   ├── tickets.json          # 32 diverse training/sample labeled tickets
│   └── evaluation_tickets.json # 12 independent held-out evaluation tickets
├── scripts/
│   ├── __init__.py
│   ├── evaluate_classifier.py # Standalone evaluation script (accuracy & confusion matrix)
│   └── demo.py               # End-to-end interactive CLI demonstration
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures and isolated temporary SQLite DB
│   ├── test_classifier.py    # Unit tests for classification, priority, and drafts
│   └── test_api.py           # Integration tests for routes, validation, and approval
├── docs/
│   └── azure-plan.md         # Production Azure App Service architecture and deployment guide
├── .github/
│   └── workflows/
│       ├── ci.yml            # Automated CI pipeline (lint, test, evaluate)
│       └── deploy-azure.yml  # Manual Azure deployment via GitHub Actions OIDC
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 3. Classification & Priority Rules

### Categories & Assigned Teams
| Category | Domain Focus | Assigned Support Team |
| :--- | :--- | :--- |
| **Billing** | Payments, invoices, refunds, charges, subscriptions | **Billing Support** |
| **Technical** | Server errors, outages, crashes, bugs, performance | **Technical Support** |
| **Access** | Authentication, SSO, 2FA, password resets, permissions | **Account Support** |
| **General** | Documentation, how-to, feature suggestions, contact | **General Support** |

### Priority Policy
- **High**: Payment failures with money deducted, duplicate or unauthorized billing transactions, suspected unauthorized access/account compromise, or complete service outages.
- **Medium**: Blocked core workflows (e.g., checkout broken, export failing, password reset failing), user lockouts, or application crashes.
- **Low**: How-to inquiries, documentation requests, feature suggestions, or non-urgent general questions.

### Explainable Heuristics & Ambiguity Routing
- Matches phrases using word-boundary regular expressions (`\bphrase\b`).
- Multi-word phrases (e.g., `"charged twice"`, `"service outage"`, `"unauthorized access"`) carry higher weights (3.0 &ndash; 3.5).
- If two categories have close match scores (score delta < 0.6) or if zero keywords match:
  - The ticket is assigned a calibrated heuristic confidence (< 0.50).
  - `needs_human_review` is set to `true`.
  - The `classification_explanation` explicitly details why human triage was mandated.
  - Scores are heuristic match strengths, not statistical Bayesian probabilities.

---

## 4. Prerequisites & Local Setup

### Prerequisites
- Python 3.9, 3.10, 3.11, or 3.12
- Git
- Docker (optional, for containerized execution)

### 1. Clone & Navigate to Repository
```bash
git clone <repository-url>
cd "Azure Support Ticket Automation"
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
*(On Windows: `.venv\Scripts\activate`)*

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment (Optional)
```bash
cp .env.example .env
```
Default settings run with local SQLite at `data/tickets.db` on `http://127.0.0.1:8000`.

---

## 5. Running the Application

### Option A: Local Uvicorn Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The interactive Swagger API documentation will be available at:
- **Interactive Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative Documentation (ReDoc)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Option B: Run End-to-End Local Demo
To verify the complete workflow automatically:
```bash
python scripts/demo.py
```

---

## 6. Docker Container Execution

### 1. Build the Docker Image
```bash
docker build -t cerevyn-ticket-api:latest .
```

### 2. Run Container with Persistent Local Storage Volume
Mount local directory `./data` to `/app/data` to ensure SQLite data persists across container restarts:
```bash
docker run -d \
  --name cerevyn-ticket-api \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  cerevyn-ticket-api:latest
```

### 3. Verify Container Health
```bash
docker ps
curl http://localhost:8000/health
```

### 4. Stop and Clean Up Container
```bash
docker stop cerevyn-ticket-api && docker rm cerevyn-ticket-api
```

---

## 7. API Endpoints & Usage Examples

### A. Create Ticket: `POST /tickets`

**Request**:
```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "TCK-101",
    "message": "I was charged twice for the same subscription renewal on my credit card."
  }'
```

**Response (`201 Created`)**:
```json
{
  "ticket_id": "TCK-101",
  "message": "I was charged twice for the same subscription renewal on my credit card.",
  "category": "Billing",
  "priority": "High",
  "assigned_team": "Billing Support",
  "summary": "[Billing] I was charged twice for the same subscription renewal on my credit card.",
  "draft_response": "Hello,\n\nThank you for contacting Cerevyn Support. We have received your billing inquiry regarding ticket [TCK-101]. Our Billing Support team is currently reviewing the transaction logs and payment records associated with your account. A billing specialist will follow up with verified details and next steps.\n\nBest regards,\nCerevyn Billing Support Team\n[INTERNAL DRAFT - Pending Human Agent Verification]",
  "status": "Pending Review",
  "confidence_score": 0.95,
  "classification_explanation": "Classified as Billing based on matched signals: 'charged twice' (x1), 'subscription' (x1), 'credit card' (x1), 'charged' (x1). Assigned High priority: Duplicate or unauthorized billing transaction with immediate financial impact.",
  "needs_human_review": false,
  "approved_by": null,
  "approved_at": null,
  "created_at": "2026-10-14T12:56:27.234102+00:00",
  "updated_at": "2026-10-14T12:56:27.234102+00:00"
}
```

---

### B. Retrieve Ticket: `GET /tickets/{ticket_id}`

```bash
curl http://127.0.0.1:8000/tickets/TCK-101
```

**Response (`200 OK`)**:
Returns the complete ticket record. If the ID does not exist, returns `404 Not Found`.

---

### C. List Tickets: `GET /tickets`

Supports query filters `status` and `category`:
```bash
# List all tickets
curl http://127.0.0.1:8000/tickets

# Filter by status and category
curl "http://127.0.0.1:8000/tickets?status=Pending%20Review&category=Billing"
```

---

### D. Human Review & Approval: `POST /tickets/{ticket_id}/approve`

Transitions the ticket from `Pending Review` to `Ready`. Approval represents internal sign-off; no emails are automatically transmitted.

**Request**:
```bash
curl -X POST http://127.0.0.1:8000/tickets/TCK-101/approve \
  -H "Content-Type: application/json" \
  -d '{
    "reviewer_name": "Supervisor Sarah",
    "notes": "Verified transaction ledger and confirmed duplicate charge. Approved draft."
  }'
```

**Response (`200 OK`)**:
```json
{
  "ticket_id": "TCK-101",
  "status": "Ready",
  "approved_by": "Supervisor Sarah",
  "approved_at": "2026-10-14T12:58:10.198271+00:00",
  ...
}
```

> [!NOTE]
> Attempting to re-approve a ticket already in `Ready` status returns `400 Bad Request` with message: `"Ticket 'TCK-101' is already in 'Ready' status. Cannot approve again."`

---

### E. Health Check: `GET /health`

```bash
curl http://127.0.0.1:8000/health
```

**Response (`200 OK`)**:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0",
  "timestamp": "2026-10-14T12:56:27.229179+00:00"
}
```

---

## 8. Automated Tests & Verification

### Running the Pytest Test Suite
Tests execute against an isolated temporary SQLite database managed by pytest's `tmp_path` fixture.

```bash
pytest -v tests/
```

### Verified Test Suite Output
```text
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0
rootdir: /Users/keshavsaini/Desktop/Azure Support Ticket Automation
plugins: anyio-4.12.1
collected 16 items

tests/test_api.py::test_scenario_5_duplicate_ticket_ids_are_rejected PASSED [  6%]
tests/test_api.py::test_scenario_6_empty_or_whitespace_messages_are_rejected PASSED [ 12%]
tests/test_api.py::test_scenario_7_unknown_ticket_ids_return_404 PASSED  [ 18%]
tests/test_api.py::test_scenario_8_ticket_creation_persists_in_database PASSED [ 25%]
tests/test_api.py::test_scenario_9_ticket_cannot_become_ready_without_approval PASSED [ 31%]
tests/test_api.py::test_scenario_10_explicit_approval_changes_status_to_ready PASSED [ 37%]
tests/test_api.py::test_scenario_12_invalid_requests_return_appropriate_errors PASSED [ 43%]
tests/test_api.py::test_list_tickets_and_filtering PASSED                [ 50%]
tests/test_api.py::test_health_check_endpoint PASSED                     [ 56%]
tests/test_classifier.py::test_scenario_1_billing_receives_expected_category_and_team PASSED [ 62%]
tests/test_classifier.py::test_scenario_2_technical_outage_receives_high_priority PASSED [ 68%]
tests/test_classifier.py::test_scenario_3_access_complaint_classified_correctly PASSED [ 75%]
tests/test_classifier.py::test_scenario_4_general_enquiry_receives_suitable_response PASSED [ 81%]
tests/test_classifier.py::test_scenario_11_ambiguous_ticket_flagged_for_review PASSED [ 87%]
tests/test_classifier.py::test_security_breach_triggers_high_priority PASSED [ 93%]
tests/test_classifier.py::test_draft_response_no_premature_claims PASSED [100%]

============================== 16 passed in 0.13s ==============================
```

---

## 9. Measured Evaluation Accuracy

The classifier was evaluated against the fixed, held-out evaluation dataset (`sample_data/evaluation_tickets.json`) containing 12 distinct tickets across all 4 categories and priority tiers.

### Run Evaluation Script
```bash
python scripts/evaluate_classifier.py
```

### Actual Measured Results
$$\text{Category Accuracy} = \frac{\text{Correct Evaluation Tickets}}{\text{Total Evaluation Tickets}} \times 100 = \frac{10}{12} \times 100 = 83.33\%$$

$$\text{Priority Accuracy} = \frac{11}{12} \times 100 = 91.67\%$$

### Confusion Matrix
| Expected \ Predicted | Billing | Technical | Access | General |
| :--- | :---: | :---: | :---: | :---: |
| **Billing** | **3** | 0 | 0 | 0 |
| **Technical** | 0 | **3** | 0 | 0 |
| **Access** | 0 | 1 | **2** | 0 |
| **General** | 0 | 0 | 1 | **2** |

### Ambiguity Routing Breakdown
- **3 out of 12 tickets** triggered ambiguity or low signal rules and were automatically marked with `needs_human_review = true` (EVAL-004, EVAL-011, EVAL-012).
- Rather than asserting false certainty, uncertain tickets are routed to human triage with confidence capped under 0.50.

---

## 10. CI/CD & Azure Cloud Deployment

### Continuous Integration (`.github/workflows/ci.yml`)
- Triggers on every push and pull request to `main`.
- Runs on Ubuntu with Python 3.11.
- Validates syntax, installs dependencies, executes pytest test suite (16 tests), executes the classifier evaluation script, and runs the end-to-end demo.

### Manual Azure Deployment Workflow (`.github/workflows/deploy-azure.yml`)
- Triggered manually via `workflow_dispatch`.
- Uses **GitHub Actions OIDC** (`azure/login@v2`) without storing permanent service principal passwords.
- Validates repository secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_WEBAPP_NAME`).
- Automatically verifies the `/health` endpoint upon deployment.

For complete cloud deployment instructions, database persistence strategies (e.g. Azure Database for PostgreSQL Flexible Server), Key Vault integration, and cost optimization, refer to:
[Azure Deployment Plan (docs/azure-plan.md)](file:///Users/keshavsaini/Desktop/Azure%20Support%20Ticket%20Automation/docs/azure-plan.md).

---

## 11. Known Limitations & Future Improvements

1. **Rule-Based Baseline vs. Embeddings**: The current keyword lexicon performs deterministically with zero latency and zero API cost. In production, augmenting the classifier with sentence embeddings (e.g., small local models via `sentence-transformers` or ONNX runtime) would improve semantic matching for complex paraphrases.
2. **SQLite File Persistence**: SQLite is ideal for lightweight local development and single-container execution. For high-availability, multi-worker deployments on Azure App Service, migrating to **Azure Database for PostgreSQL Flexible Server** prevents file-lock contention.
3. **Audit History Log**: Adding an audit log table to record all reviewer comments and state transitions over time.
4. **Rate Limiting**: Implementing IP/token-based rate limiting (e.g., using `slowapi`) for public endpoints.

---

## 12. AI-Assisted Development Disclosure

This project was developed with the assistance of agentic AI coding tools (Antigravity by Google DeepMind) to scaffold boilerplate code, assist with unit test cases, generate realistic synthetic sample datasets, and format technical documentation. All business logic, deterministic rule patterns, database constraints, input validators, state transition guards, and test suites were verified, executed, and validated locally.
