# PREDICT — Vehicle Intelligence Platform

> Production-grade vehicle diagnostics, predictive maintenance AI, and fleet management platform.
> Self-hosted · FastAPI · PostgreSQL · PySide6 Desktop

---

## Overview

PREDICT is a full-stack vehicle intelligence platform that connects to a car's OBD-II port, collects real-time sensor data, and applies machine learning to predict component failures before they happen. It runs as a desktop application with an embedded FastAPI server, or as a headless server for cloud/Raspberry Pi deployments.

**Domain:** [previlium.com](https://previlium.com)

---

## Features

### Vehicle Intelligence
- OBD-II / ELM327 real-time sensor data collection (RPM, temperatures, voltages, fuel, MAF, O2 sensors)
- Nissan Consult-II protocol support (legacy vehicles)
- VIN decoding and vehicle profile management
- DTC (Diagnostic Trouble Code) lookup and explanation
- NHTSA recall alerts

### AI & Predictive Maintenance
- LSTM time-series failure prediction (time-to-failure in km and days)
- Ensemble voting across multiple models (sklearn, XGBoost, LightGBM)
- SHAP-based explainability — human-readable factor analysis
- Local LLM assistant (GGUF via llama.cpp) — offline, private
- Automated model retraining pipeline with validation safeguards
- Driving score and behaviour analysis

### Platform
- Guardian mode — parental monitoring of linked vehicles
- Fleet management — multi-vehicle, multi-driver
- Trip analytics with detailed telemetry
- PDF report generation (vehicle health, predictions, service history)
- Data export: CSV, JSON, Parquet
- Push notifications via Firebase Cloud Messaging (FCM)
- Subscription tiers with Fatora billing integration
- Full audit log for all write operations

### Infrastructure
- Async FastAPI with 162+ endpoints across 16 routers
- PostgreSQL with async SQLAlchemy 2.0 — 49 tables, 8 domain models
- Redis caching (API key validation < 10ms), pub/sub for WebSocket scaling
- ARQ background workers (email, FCM, PDF generation, backups, GDPR cleanup)
- AES-256-GCM field-level encryption for sensitive data
- JWT + API key authentication with bcrypt
- Redis-backed sliding window rate limiting
- Circuit breakers, health monitoring, in-memory metrics
- Alembic database migrations
- Docker Compose for full-stack deployment

### Desktop GUI (PySide6)
- Embedded FastAPI server runs inside the desktop app
- Real-time server health polling
- Dashboard, logs, and settings tabs
- Launch mode: `--desktop` (default) or `--headless` (server only)

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 async (asyncpg) |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7 + ARQ |
| Migrations | Alembic |
| Desktop GUI | PySide6 |
| AI / ML | LSTM, XGBoost, LightGBM, scikit-learn, SHAP |
| Local LLM | llama-cpp-python (GGUF models) |
| Auth | JWT (python-jose) + bcrypt API keys |
| Encryption | AES-256-GCM (cryptography) |
| Push | Firebase Admin SDK (FCM) |
| Billing | Fatora payment gateway |
| PDF | ReportLab |
| Monitoring | Sentry SDK, custom circuit breakers |
| Containerisation | Docker + Docker Compose |
| Language | Python 3.11+ |

---

## Project Structure

```
predict/
├── predict/                  # Main Python package
│   ├── __main__.py           # Entry point (--headless / --desktop)
│   ├── core/
│   │   ├── config.py         # Centralised config singleton
│   │   ├── version.py        # App version (3.0.0)
│   │   ├── db/
│   │   │   ├── engine.py     # Async engine factory (pool 5–20)
│   │   │   ├── session.py    # Async session management
│   │   │   ├── base.py       # DeclarativeBase + TimestampMixin
│   │   │   ├── models/       # 49 ORM models across 8 domains
│   │   │   ├── repositories/ # Repository pattern (BaseRepository + domain repos)
│   │   │   └── migrations/   # Alembic migrations
│   │   ├── api/
│   │   │   ├── app.py        # FastAPI factory with lifespan
│   │   │   ├── deps.py       # Shared dependencies (get_db, get_current_user)
│   │   │   └── v1/           # 16 routers: auth, vehicles, dtc, predictions,
│   │   │                     #   guardian, fleet, billing, reports, admin,
│   │   │                     #   dashboard, driving, tiers, ai_chat, legal, health
│   │   ├── middleware/       # error_handler, api_key, cors, rate_limiter,
│   │   │                     #   request_tracing, validation, audit
│   │   ├── services/         # auth_service, email_service, export_service
│   │   ├── cache/            # redis_client, api_key_cache, pubsub
│   │   ├── jobs/             # ARQ worker + tasks (email, FCM, PDF, backup, cleanup)
│   │   ├── ai/               # model_loader, lstm_predictor, ensemble_voter,
│   │   │                     #   explainability, unified_ai_module, llm/assistant
│   │   ├── monitoring/       # health, circuit_breaker, metrics
│   │   └── security/         # secrets_loader (fail-fast validation)
│   └── desktop/
│       ├── app.py            # Qt application entry point
│       ├── main_window.py    # PySide6 main window
│       └── server_thread.py  # Embedded FastAPI server thread
├── docker-compose.yml        # Full stack: app + postgres + redis + nginx + worker
├── Dockerfile
├── alembic.ini
├── pyproject.toml            # 70+ dependencies
└── .env.example              # All required environment variables (copy to .env)
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 16
- Redis 7
- (Optional) Docker + Docker Compose for containerised deployment

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/predict.git
cd predict
```

### 2. Create and configure `.env`

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Required
DATABASE_URL=postgresql+asyncpg://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:5432/predict
SECRET_KEY=your-random-secret-key-here
ADMIN_API_KEY=your-admin-api-key-here

# Email (required for user registration)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Firebase (required for push notifications)
FCM_CREDENTIALS_PATH=config/firebase-credentials.json

# Optional
REDIS_URL=redis://localhost:6379/0
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
FATORA_API_KEY=
SENTRY_DSN=
```

Generate `SECRET_KEY` with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Install dependencies

```bash
pip install -e ".[desktop]"
# or without GUI:
pip install -e .
```

### 4. Set up the database

```bash
# Create the database
createdb predict

# Run migrations
alembic upgrade head
```

### 5. Run

**Desktop mode (GUI + embedded server):**
```bash
python -m predict --desktop
```

**Headless server mode:**
```bash
python -m predict --headless
```

**Docker Compose (full stack):**
```bash
docker compose up -d
```

API docs available at: `http://localhost:8000/docs`

---

## ARQ Background Worker

Run the background job worker separately:

```bash
arq predict.core.jobs.worker.WorkerSettings
```

Scheduled jobs:
- 03:00 daily — database backup
- 04:00 daily — GDPR data cleanup

---

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL asyncpg connection string |
| `SECRET_KEY` | Yes | JWT signing key (generate randomly) |
| `ADMIN_API_KEY` | Yes | Master admin API key |
| `SMTP_HOST` | Yes | SMTP server for email |
| `SMTP_USER` | Yes | SMTP username |
| `SMTP_PASSWORD` | Yes | SMTP app password |
| `FCM_CREDENTIALS_PATH` | Yes | Path to Firebase service account JSON |
| `REDIS_URL` | No | Redis URL (default: `redis://localhost:6379/0`) |
| `CLOUDFLARE_TUNNEL_TOKEN` | No | Cloudflare tunnel token for remote access |
| `LLM_MODEL_PATH` | No | Path to GGUF model file |
| `OPENAI_API_KEY` | No | OpenAI key for cloud LLM fallback |
| `ANTHROPIC_API_KEY` | No | Anthropic key for cloud LLM fallback |
| `FATORA_API_KEY` | No | Fatora billing API key |
| `SENTRY_DSN` | No | Sentry error tracking DSN |
| `SERPER_API_KEY` | No | Serper.dev for vehicle research search |
| `BRAVE_API_KEY` | No | Brave Search API (fallback) |

---

## Security

- All secrets are loaded via `predict/core/security/secrets_loader.py` using Pydantic Settings — the app **refuses to start** if required secrets are missing or contain placeholder values
- API keys are hashed with bcrypt (SHA-256 fallback for migration)
- Sensitive fields (phone numbers) encrypted with AES-256-GCM
- Never commit `.env`, `config/email_config.json`, `config/remote_server.json`, or any `firebase*.json` files — all are excluded by `.gitignore`

---

## API Overview

Base URL: `/api/v1/`

| Router | Prefix | Description |
|---|---|---|
| Health | `/health` | Service health checks |
| Auth | `/auth` | Register, login, verify, API keys |
| Profiles | `/profiles` | User and vehicle profiles |
| Vehicle Data | `/vehicle-data` | OBD telemetry upload and retrieval |
| DTC | `/dtc` | Diagnostic trouble codes |
| Predictions | `/predictions` | AI health scores and failure predictions |
| Guardian | `/guardian` | Parental vehicle monitoring |
| Fleet | `/fleet` | Fleet and driver management |
| Billing | `/billing` | Subscriptions and invoices (Fatora) |
| Reports | `/reports` | PDF report generation and download |
| Admin | `/admin` | User management, system stats |
| Dashboard | `/dashboard` | Server metrics and circuit breaker status |
| Driving | `/driving` | Driving score and trip behaviour |
| Tiers | `/tiers` | Subscription tier information |
| AI Chat | `/ai-chat` | LLM assistant (local or cloud) |

Full interactive docs: `http://localhost:8000/docs`

---

## License

See [LICENSE](LICENSE) for details.

---

## Contact

**Omar**
[previlium.com](https://previlium.com)
For business inquiries or partnerships, reach out via the website.
