# ConvoAI

A conversational AI customer service platform with document-backed knowledge retrieval, voice support, and human escalation workflows.

## Features

- **AI Chat** — GPT-4-turbo agent with tool-calling and structured reasoning
- **RAG** — vector knowledge base (pgvector) searched before every factual answer
- **Human Escalation** — automatic (confidence threshold) or manual handoff with full conversation context
- **Voice I/O** — speech-to-text via OpenAI Whisper (hosted or self-hosted) and text-to-speech via ElevenLabs
- **Streaming** — token-level SSE streaming from the LLM to the browser
- **Admin Panel** — upload knowledge documents, review low-confidence sessions, manage escalation queue, live metrics dashboard
- **Background Ingestion** — Celery + Redis task queue for reliable async document processing
- **Observability** — Prometheus metrics, OpenTelemetry tracing, PagerDuty alerting
- **Auth & Security** — JWT auth, per-IP rate limiting, PII redaction middleware, circuit breaker for LLM API
- **CI/CD** — GitHub Actions pipeline (lint → test → k6 smoke test → Docker build → GCP Cloud Run canary deploy)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, LangChain, SQLAlchemy (async) |
| LLM | OpenAI GPT-4-turbo |
| Vector DB | PostgreSQL 16 + pgvector |
| Embeddings | OpenAI text-embedding-3-small |
| Memory / Queue | Redis 7 |
| Task Worker | Celery |
| STT | OpenAI Whisper / faster-whisper (self-hosted) |
| TTS | ElevenLabs |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Infra | Docker Compose · GCP Cloud Run |
| CI/CD | GitHub Actions · k6 load tests |
| Monitoring | Prometheus · Alertmanager · PagerDuty |

## Local Setup

### Prerequisites

- **Docker Desktop** (running)
- **Node.js 20+**
- **OpenAI API key**

### 1 — Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
OPENAI_API_KEY=sk-...
JWT_SECRET=any-long-random-string
API_KEY=any-string
```

Everything else (Postgres, Redis, Celery) has working defaults.

### 2 — Start the backend stack

```bash
docker compose up --build
```

This starts: **API** (port 8000) · **Postgres** (5432) · **Redis** (6379) · **Celery worker**

Optional profiles:

```bash
# Self-hosted Whisper STT sidecar
docker compose --profile voice up --build

# Prometheus + Alertmanager monitoring
docker compose --profile monitoring up --build
```

### 3 — Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4 — Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 5 — Verify

| Service | URL |
|---|---|
| API health | http://localhost:8000/api/v1/health |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:5173 |

### Admin panel access

Generate an admin JWT token:

```bash
cd backend
.venv/Scripts/python app/utils/gen_token.py --role admin   # Windows
# or
.venv/bin/python app/utils/gen_token.py --role admin       # Mac/Linux
```

Create `frontend/.env` with:

```env
VITE_API_URL=http://localhost:8000
VITE_API_KEY=any-string          # must match API_KEY in .env
VITE_ADMIN_JWT=<token from above>
```

Then restart `npm run dev` and navigate to `/admin`.

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `LLM_MODEL` | `gpt-4-turbo` | LLM model used by the agent |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for RAG |
| `ESCALATION_CONFIDENCE_THRESHOLD` | `0.65` | Auto-escalate when retrieval confidence falls below this |
| `RETRIEVAL_TOP_K` | `5` | Knowledge chunks returned to the agent per query |
| `MEMORY_WINDOW` | `10` | Conversation turns kept in Redis context window |
| `RATE_LIMIT_RPM` | `100` | Max requests per minute per IP |
| `PII_REDACTION` | `false` | Set `true` to enable Presidio PII redaction |
| `WHISPER_BACKEND` | `openai` | `openai` (hosted) or `sidecar` (self-hosted faster-whisper) |
| `ELEVENLABS_API_KEY` | — | Leave empty to disable TTS |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery broker (Redis db/1) |
| `ESCALATION_WEBHOOK_URL` | — | POST target for escalation tickets (Zendesk, Freshdesk, etc.) |

See `.env.example` for the full list.

## API Overview

Base path: `/api/v1`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Liveness / readiness probe |
| `POST` | `/chat` | API Key | Send message — returns SSE token stream |
| `GET` | `/conversations/{id}` | JWT | Full conversation transcript |
| `DELETE` | `/conversations/{id}` | JWT | Soft-delete a conversation |
| `POST` | `/admin/documents` | Admin JWT | Upload documents for RAG ingestion |
| `GET` | `/admin/documents` | Admin JWT | List documents (filterable by category/product/version) |
| `DELETE` | `/admin/documents/{id}` | Admin JWT | Remove document and its embeddings |
| `GET` | `/admin/metrics` | Admin JWT | Live dashboard metrics |
| `GET` | `/admin/review-queue` | Admin JWT | Low-confidence sessions pending review |
| `GET` | `/admin/escalations` | Admin JWT | Escalation ticket queue |
| `PATCH` | `/admin/escalations/{id}` | Admin JWT | Update ticket status |
| `POST` | `/voice/transcribe` | API Key | Transcribe audio (WAV/WebM) via Whisper |
| `POST` | `/voice/synthesize` | API Key | Synthesize text to audio via ElevenLabs |

## Project Structure

```
convo_ai/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangChain agent, tools, prompts, memory, circuit breaker
│   │   ├── api/v1/         # FastAPI route handlers
│   │   ├── middleware/     # Auth, rate limiting, PII redaction
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── rag/            # Document ingestion and vector retrieval
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Redis, TTS, Whisper, escalation, agent config
│   │   └── worker/         # Celery app and ingestion tasks
│   ├── alembic/            # Database migrations
│   └── tests/              # Pytest test suite (unit + integration)
├── frontend/
│   └── src/
│       ├── components/     # Chat and admin UI components
│       ├── hooks/          # useChat, useVoice, useMetrics
│       ├── pages/          # ChatPage, AdminPage
│       └── store/          # Zustand state management
├── deploy/                 # GCP Cloud Run service YAML files
├── eval/                   # RAG evaluation harness + golden dataset
├── loadtests/k6/           # k6 load test scripts (SSE chat, voice flow)
├── monitoring/             # Prometheus rules, Alertmanager + PagerDuty config
├── .github/workflows/      # GitHub Actions CI/CD pipeline
└── docker-compose.yml
```

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

Tests require a running Postgres and Redis. Use Docker:

```bash
docker compose up postgres redis -d
cd backend
pytest
```

## CI/CD Pipeline

Every push to `main` runs:

1. **Lint** — `ruff` + `mypy` (Python) · `eslint` (TypeScript)
2. **Tests** — `pytest` with coverage report
3. **k6 Smoke Test** — 50 VUs · 30s against a live API instance
4. **Docker Build** — image pushed to Google Artifact Registry
5. **Deploy** — canary revision (10% traffic) → smoke test → promote to 100%

A separate **nightly workflow** runs the full RAG evaluation harness and 500-VU load test.

## License

MIT
