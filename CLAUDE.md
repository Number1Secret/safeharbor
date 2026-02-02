# SafeHarbor AI - OBBB Tax Compliance Engine

## Project Overview

SafeHarbor AI is a specialized Tax Logic Wrapper that sits between operational data sources (payroll, POS, timekeeping, HRIS) and payroll systems. It calculates qualified amounts for the One Big Beautiful Bill Act (OBBB) tax exemptions: qualified overtime pay, qualified tips, and qualified senior citizen wages.

## Quick Start

```bash
# Install dependencies
cd /Users/emmanuelakindele/Downloads/safeharbor
pip install -e ".[dev]"

# Run the API server
uvicorn backend.main:app --reload --port 8000

# Run the MCP calculation engines
python -m engines.server
```

## Project Structure

```
safeharbor/
├── backend/                 # FastAPI application
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic API schemas
│   ├── routers/v1/         # API route handlers
│   ├── services/           # Business logic
│   ├── db/                 # Database session management
│   ├── config.py           # Settings
│   └── main.py             # FastAPI app
├── engines/                 # MCP Calculation Engines
│   ├── tools/              # MCP tool implementations
│   ├── services/           # Pure calculation logic
│   ├── schemas/            # Engine I/O schemas
│   └── server.py           # FastMCP server
├── integrations/           # External API connectors
│   ├── base.py            # Abstract base classes
│   ├── oauth_manager.py   # Token lifecycle management
│   ├── payroll/           # ADP, Gusto, Paychex, QuickBooks
│   ├── pos/               # Toast, Square, Clover
│   ├── timekeeping/       # Deputy
│   └── hris/              # BambooHR, Rippling
├── workers/                # Celery background jobs
│   ├── celery_app.py      # Celery config + beat schedule
│   └── tasks/             # sync, calculation, compliance, notification
├── compliance_vault/       # Immutable audit ledger
│   ├── ledger.py          # Append-only hash chain
│   ├── integrity.py       # Chain verification
│   ├── retention.py       # 7-year retention processing
│   └── export.py          # Audit Defense Pack generation
├── frontend/               # Next.js 16 application
│   └── src/
│       ├── app/           # Pages (dashboard, approvals, employees, etc.)
│       ├── components/    # React components
│       ├── lib/           # Hooks and utilities
│       └── types/         # TypeScript types
└── tests/                  # Test suite
```

## Key Models

| Model | Purpose |
|-------|---------|
| `Organization` | Multi-tenant employer with tax settings |
| `Employee` | Employee records with TTOC classification |
| `CalculationRun` | Batch calculation for a pay period |
| `EmployeeCalculation` | Per-employee calculation results |
| `Integration` | OAuth connections to external systems |
| `ComplianceVault` | Immutable audit ledger with hash chain |
| `TTOCClassification` | AI occupation code classification |

## Core Calculation Engines

### 1. Premium Engine (FLSA Regular Rate)
Calculates the FLSA Section 7 Regular Rate of Pay:
- Regular Rate = Total Compensation / Total Hours
- Qualified OT Premium = Regular Rate × 0.5 × OT Hours (excludes double-time)

```python
from engines.services.regular_rate_calculator import calculate_regular_rate
```

### 2. Phase-Out Filter (MAGI Tracking)
Applies OBBB phase-out rules based on income:
- Single: $75,000 - $100,000 (4% per $1,000)
- Married Joint: $150,000 - $200,000 (2% per $1,000)
- Head of Household: $112,500 - $150,000 (2.67% per $1,000)

```python
from engines.services.magi_tracker import calculate_phase_out
```

### 3. Occupation AI (TTOC Classification)
LLM-based Treasury Tipped Occupation Code classifier:
- 70+ occupation codes from IRS
- Determinism envelope for reproducibility
- Human verification workflow

## API Endpoints

### Organizations
- `POST /api/v1/organizations` - Create organization
- `GET /api/v1/organizations/{id}` - Get organization
- `PATCH /api/v1/organizations/{id}` - Update organization

### Employees
- `POST /api/v1/organizations/{org_id}/employees` - Create employee
- `GET /api/v1/organizations/{org_id}/employees` - List employees
- `POST /api/v1/organizations/{org_id}/employees/{id}/classify` - Trigger TTOC classification

### Calculations
- `POST /api/v1/organizations/{org_id}/calculations` - Create calculation run
- `GET /api/v1/organizations/{org_id}/calculations/{id}` - Get run details
- `POST /api/v1/organizations/{org_id}/calculations/{id}/approve` - Approve/reject
- `POST /api/v1/organizations/{org_id}/calculations/{id}/finalize` - Finalize to vault

### Integrations
- `GET /api/v1/organizations/{org_id}/integrations` - List integrations
- `POST /api/v1/organizations/{org_id}/integrations/connect/{provider}` - Connect
- `POST /api/v1/organizations/{org_id}/integrations/{id}/sync` - Trigger sync

## Environment Variables

```env
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=safeharbor
POSTGRES_PASSWORD=safeharbor
POSTGRES_DB=safeharbor

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Security
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-fernet-key

# Anthropic
ANTHROPIC_API_KEY=your-api-key
```

## Current Implementation Status

### Phase 1: Foundation (Complete)
- [x] Project structure and configuration
- [x] Database models (all 7 core entities)
- [x] Pydantic API schemas
- [x] Premium Engine (Regular Rate calculator)
- [x] Phase-Out Filter (MAGI tracking)
- [x] Basic API routes
- [x] MCP server entry point

### Phase 2: AI Integration (Complete)
- [x] Occupation AI (TTOC classifier with LLM + rule-based fallback)
- [x] Classification UI (Approval Queue with bulk actions)
- [x] Retro-Audit Report (risk assessment + penalty exposure)
- [x] Toast POS integration
- [x] Phase-Out Filter (MAGI tracking)

### Phase 3: API Bridge (Complete)
- [x] Payroll integrations (ADP, Gusto, Paychex, QuickBooks)
- [x] POS integrations (Toast, Square, Clover)
- [x] Timekeeping integrations (Deputy)
- [x] HRIS integrations (BambooHR, Rippling)
- [x] Write-back engine (W-2 Box 12 codes TT, TP, TS)
- [x] Compliance Vault (hash chain ledger, integrity verification, retention, export)
- [x] Background workers (Celery with sync, calculation, compliance, notification queues)

### Phase 4: Scale (Complete)
- [x] Dashboard UI (Next.js 15 + React 19 + TailwindCSS 4)
- [x] Employee Detail screen (timeline, breakdown, audit log)
- [x] Enterprise features (SSO SAML/OIDC, RBAC with 5 roles + 24 permissions, API keys)
- [x] Admin routes (user management, API keys, SSO config, org settings)
- [x] Deployment config (render.yaml, docker-compose.yml, Dockerfiles)

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov=engines

# Run specific test file
pytest tests/unit/engines/test_premium_engine.py
```

## Development Notes

- All monetary calculations use `Decimal` for precision
- SSNs are hashed before storage (never store raw)
- OAuth tokens are encrypted with Fernet
- Compliance Vault uses SHA-256 hash chain for integrity
- All LLM calls include determinism envelope (model_id, prompt_hash, response_hash)

## PRD Reference

Full PRD available at: SafeHarbor AI PRD v2.0 (Build-Ready Specification)
Target: 50,000 employees on platform, 200 customers, >95% retention in Year 1
