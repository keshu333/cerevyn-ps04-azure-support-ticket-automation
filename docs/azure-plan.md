# Azure Deployment Plan: Cerevyn Support Ticket Automation (PS04)

This document provides the cloud deployment strategy for the **Cerevyn Solutions PS04 - Azure Support Ticket Automation API**, targeting **Azure App Service (Linux)**.

---

## 1. Request Flow and Application Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │            Customer / Support Agent          │
                    └──────────────────────┬───────────────────────┘
                                           │ HTTPS (TLS 1.3)
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │      Azure App Service Front Door / SSL      │
                    │   (Custom Domain / *.azurewebsites.net)      │
                    └──────────────────────┬───────────────────────┘
                                           │ Port 8000 (Internal)
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │         FastAPI ASGI App (Gunicorn/Uvicorn)   │
                    │                                              │
                    │  ┌─────────────────┐    ┌─────────────────┐  │
                    │  │ /tickets API    │    │ /health check   │  │
                    │  └────────┬────────┘    └─────────────────┘  │
                    │           │                                  │
                    │           ▼                                  │
                    │  ┌─────────────────┐    ┌─────────────────┐  │
                    │  │ Rule Classifier │    │ Responder Draft │  │
                    │  │ & Ambiguity Eng │    │ Generator       │  │
                    │  └────────┬────────┘    └─────────────────┘  │
                    └───────────┼──────────────────────────────────┘
                                │ Parameterized Queries
                                ▼
                    ┌──────────────────────────────────────────────┐
                    │           Durable Persistence Layer          │
                    │  (Azure DB for PostgreSQL Flexible Server /  │
                    │   Azure Files Persistent SMB Mount)          │
                    └──────────────────────────────────────────────┘
```

### Flow Breakdown
1. **Inbound Traffic**: HTTPS requests arrive at the Azure App Service front-end load balancer on port 443. App Service terminates TLS and enforces HTTPS-only communication.
2. **Reverse Proxy & Routing**: Traffic forwards to the container running FastAPI managed by Uvicorn.
3. **Application Processing**:
   - `POST /tickets`: Validates input, passes complaint text to the deterministic rule classifier, computes heuristic confidence, flags edge cases for human review, extracts a concise summary, generates a category-specific draft response, and writes the ticket with status `Pending Review`.
   - `POST /tickets/{ticket_id}/approve`: Validates the ticket state, transitions status to `Ready`, and records the human reviewer identifier and timestamp.
   - `GET /health`: Probes database connectivity and returns HTTP 200 for container orchestrator health checks.

---

## 2. Hosting Target: Azure App Service (Linux)

Azure App Service (Linux) provides a fully managed PaaS hosting platform for Python web applications:
- **Runtime**: Python 3.11 or Custom Linux Container (`python:3.11-slim`).
- **Startup Command**:
  ```bash
  gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
  ```
- **Scale Out**: Supports automatic scaling based on CPU or memory thresholds.

---

## 3. Database Persistence Considerations

> [!WARNING]
> **Ephemeral Container Storage Warning:**
> In local development, SQLite stores data in a local file (`data/tickets.db`). However, in Azure App Service:
> - Container restarts, multi-instance scale-outs, and platform maintenance cycles replace the local container filesystem.
> - Multiple App Service worker instances sharing a local SQLite file causes file-locking errors (`sqlite3.OperationalError: database is locked`).

### Production Persistence Strategy
For a production deployment on Azure, choose one of two durable options:

1. **Option A: Managed Relational Database (Recommended for Production)**
   - **Service**: **Azure Database for PostgreSQL Flexible Server** (or Azure SQL Database).
   - **Rationale**: Full ACID compliance, automatic daily backups, connection pooling, multi-instance horizontal scaling, and zero risk of file locking.
   - **Configuration**: Set `DATABASE_URL=postgresql://user:password@server.postgres.database.azure.com:5432/cerevyn_db?sslmode=require`.

2. **Option B: Azure Storage Files SMB Mount (Low-Cost SQLite Persistence)**
   - **Service**: Azure Storage Account with an Azure Files Share.
   - **Configuration**: Mount the Azure File Share directly into App Service at `/app/data` using `az webapp config storage-account add`.
   - **Limitation**: Suitable only for single-instance App Service (`WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT=1`).

---

## 4. Identity, Security, and Secret Management

### A. Managed Identity (Passwordless Access)
- Enable **System-Assigned Managed Identity** on the Azure App Service instance:
  ```bash
  az webapp identity assign --name <app-name> --resource-group <rg-name>
  ```
- Grant the Managed Identity the **Key Vault Secrets User** role on Azure Key Vault. This eliminates hardcoded credentials in application configuration files.

### B. Azure Key Vault & App Settings
- Store sensitive configuration (database passwords, API secrets) in **Azure Key Vault**.
- Reference secrets directly from Azure App Service configuration using Key Vault reference syntax:
  ```
  DATABASE_PASSWORD=@Microsoft.KeyVault(SecretUri=https://<vault-name>.vault.azure.net/secrets/db-password/<version>)
  ```
- Non-sensitive variables are configured via standard App Settings:
  - `API_HOST`: `0.0.0.0`
  - `API_PORT`: `8000`
  - `ENVIRONMENT`: `production`
  - `MAX_MESSAGE_LENGTH`: `2000`
  - `CONFIDENCE_THRESHOLD`: `0.60`

### C. HTTPS & Network Security
- Enable **HTTPS Only** in App Service (`az webapp update --https-only true`).
- Enforce Minimum TLS Version `1.2` or `1.3`.
- Configure CORS with allowed production origins rather than wildcard `*`.

---

## 5. Health Checks, Logging, and Monitoring

### Health Checks
- Configure Azure App Service Health Check to ping `/health` every 1 to 2 minutes.
- If an instance fails 2 consecutive health checks, Azure automatically removes it from the load balancer rotation and restarts the unhealthy container instance.

### Logging & Diagnostics
- Enable **Application Insights** for distributed telemetry, request duration tracking, and failure tracking.
- Enable App Service Application Logging:
  ```bash
  az webapp log config --name <app-name> --resource-group <rg-name> \
    --application-logging filesystem --level information
  ```
- Stream live logs directly via CLI:
  ```bash
  az webapp log tail --name <app-name> --resource-group <rg-name>
  ```

---

## 6. GitHub Actions OIDC Federated Identity Setup

To allow `.github/workflows/deploy-azure.yml` to deploy without storing permanent passwords or service principal secrets in GitHub:

1. **Create an Azure AD Application & Service Principal**:
   ```bash
   az ad app create --display-name "github-actions-cerevyn"
   APP_ID=$(az ad app list --display-name "github-actions-cerevyn" --query "[0].appId" -o tsv)
   az ad sp create --id $APP_ID
   ```

2. **Add Federated Identity Credential**:
   Create a credential linking the GitHub repository branch to Azure:
   ```bash
   az ad app federated-credential create --id $APP_ID --parameters '{
     "name": "github-actions-main-branch",
     "issuer": "https://token.actions.githubusercontent.com",
     "subject": "repo:<YOUR_GITHUB_ORG>/<YOUR_REPO>:ref:refs/heads/main",
     "audiences": ["api://AzureADTokenExchange"]
   }'
   ```

3. **Assign Contributor Role on App Service Resource Group**:
   ```bash
   az role assignment create --role "Contributor" \
     --assignee $APP_ID \
     --scope "/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP>"
   ```

4. **Add GitHub Repository Secrets**:
   - `AZURE_CLIENT_ID`: The Application (Client) ID.
   - `AZURE_TENANT_ID`: The Azure Active Directory Directory (Tenant) ID.
   - `AZURE_SUBSCRIPTION_ID`: The Azure Subscription ID.
   - `AZURE_WEBAPP_NAME`: The name of the target Azure App Service Web App.

---

## 7. Cost Optimization & Free Tier Guidelines

To prevent unexpected billing during assessment and testing:

| Resource | Recommended Tier | Estimated Cost | Notes |
| :--- | :--- | :--- | :--- |
| **Azure App Service** | **F1 (Free)** or **B1 (Basic)** | \$0/mo (F1) / ~\$13/mo (B1) | F1 provides 60 CPU minutes/day, ideal for assessment grading. B1 allows custom domains and SSL. |
| **Azure Key Vault** | Standard Tier | < \$0.10/mo | Charges per 10,000 operations. |
| **Database** | Azure Files Share (5 GB) | < \$0.30/mo | Ultra-low cost for SQLite SMB mount. |
| **PostgreSQL (Optional)** | Flexible Server Burstable B1ms | ~\$15/mo (eligible for 12 months free on new Azure accounts) | Use burstable compute. |

### Avoiding Accidental Charges
- **Clean Up**: Delete the resource group immediately after assessment demonstration:
  ```bash
  az group delete --name cerevyn-assessment-rg --yes --no-wait
  ```
- **Disable Auto-Scale**: Fix instance count to 1 worker during testing.

---

## 8. Local Testing vs. Live Deployment

The system is architected to run identically locally and in the cloud:

| Environment | Database | Secrets | Health Probing |
| :--- | :--- | :--- | :--- |
| **Local Development** | SQLite file (`data/tickets.db`) | `.env` file | `curl http://localhost:8000/health` |
| **Automated Testing** | Isolated temporary SQLite (`tmp_path`) | Environment overrides | Pytest `TestClient` |
| **Docker Local** | Docker volume mount (`-v $(pwd)/data:/app/data`) | `docker run -e ...` | Docker `HEALTHCHECK` directive |
| **Azure App Service** | Azure Files SMB or Azure PostgreSQL | Azure App Settings / Key Vault | App Service Health Check (`/health`) |
