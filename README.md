# ConvoAI

A conversational AI customer service platform with document-backed knowledge retrieval, voice support, and human escalation workflows.

## Features

- **AI Chat** — GPT-4-turbo agent with tool-calling for structured responses
- **RAG (Retrieval-Augmented Generation)** — searches a vector knowledge base before answering to ensure accuracy
- **Human Escalation** — automatically or manually transfers conversations to human agents with full context preserved
- **Voice I/O** — speech-to-text via OpenAI Whisper (hosted or self-hosted) and text-to-speech via ElevenLabs
- **Streaming** — token-level streaming of agent responses to the frontend
- **Admin Panel** — manage knowledge documents (PDF, DOCX, HTML) and review escalation queue
- **Auth & Rate Limiting** — JWT authentication, per-IP rate limiting, and PII redaction middleware

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, LangChain, SQLAlchemy (async) |
| LLM | OpenAI GPT-4-turbo |
| Vector DB | PostgreSQL + pgvector |
| Embeddings | OpenAI text-embedding-3-small |
| Memory | Redis |
| STT | OpenAI Whisper / faster-whisper (self-hosted) |
| TTS | ElevenLabs |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Infrastructure | Docker Compose |

## Getting Started

### Prerequisites

- Docker and Docker Compose
- OpenAI API key
- ElevenLabs API key (optional, for TTS)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ArunavaGhosh1708/ConvoAI.git
   cd ConvoAI
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in at minimum:
   ```
   OPENAI_API_KEY=sk-...
   JWT_SECRET=your-strong-secret
   API_KEY=your-api-key
   ```

3. **Start the stack**
   ```bash
   docker compose up --build
   ```

   To also run the self-hosted Whisper STT sidecar:
   ```bash
   docker compose --profile voice up --build
   ```

4. **Run database migrations**
   ```bash
   docker compose exec backend alembic upgrade head
   ```

The backend API will be available at `http://localhost:8000` and the frontend at `http://localhost:5173`.

## Configuration

All configuration is via environment variables. Key options:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `LLM_MODEL` | `gpt-4-turbo` | LangChain LLM model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for RAG |
| `ESCALATION_CONFIDENCE_THRESHOLD` | `0.65` | Below this score, auto-escalate to human |
| `RETRIEVAL_TOP_K` | `5` | Number of knowledge chunks returned to agent |
| `MEMORY_WINDOW` | `10` | Number of conversation turns kept in Redis |
| `RATE_LIMIT_RPM` | `100` | Max requests per minute per IP |
| `WHISPER_BACKEND` | `openai` | `openai` for hosted API or `sidecar` for self-hosted |
| `ELEVENLABS_API_KEY` | — | ElevenLabs key (leave empty to disable TTS) |

See `.env.example` for the full list.

## API Overview

Base path: `/api/v1`

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `POST /chat` | Send a message, returns streaming SSE response |
| `GET /conversations` | List conversations |
| `GET /conversations/{id}` | Get conversation with messages |
| `POST /admin/documents` | Upload a knowledge document |
| `GET /admin/documents` | List knowledge documents |
| `DELETE /admin/documents/{id}` | Delete a document |
| `GET /escalations` | List escalation tickets |
| `POST /voice/transcribe` | Transcribe audio to text |
| `POST /voice/synthesize` | Synthesize text to speech |

## Project Structure

```
convo_ai/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangChain agent, tools, prompts, memory
│   │   ├── api/v1/         # FastAPI route handlers
│   │   ├── middleware/     # Auth, rate limiting, PII redaction
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── rag/            # Document ingestion and retrieval
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   └── services/       # Redis, TTS, Whisper, escalation
│   ├── alembic/            # Database migrations
│   └── tests/              # Pytest test suite
├── frontend/
│   └── src/
│       ├── components/     # Chat and admin UI components
│       ├── hooks/          # useChat, useVoice, useMetrics
│       ├── pages/          # ChatPage, AdminPage
│       └── store/          # Zustand state
├── docker/                 # Postgres init SQL
├── eval/                   # RAG evaluation scripts
├── loadtests/              # k6 load test scripts
├── monitoring/             # Prometheus rules, PagerDuty config
└── docker-compose.yml
```

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## License

MIT
