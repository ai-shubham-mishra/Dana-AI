# Dana AI

Dana AI is a multi-tenant, agentic marketing-model training product. A chat agent, built on the DeepAgent architecture, reads each organization's connector data (Meta Ads, Google Ads, and others), asks the user what to model, writes the training code for that data, and trains the model. Training runs locally for now and can move to Azure ML later. MMM is the first model family, and more predictive models will follow.

Frontend styling follows the analytics-studio branding.

## Status

| Milestone | Scope | Status |
|---|---|---|
| 1 | Docker Compose stack (Mongo, Azurite), FastAPI with JWT auth and org membership checks, Next.js shell | Done |
| Nav | Stacked Chat and Jobs navigation (tabs, no toggle) | Done |
| 2 | Read-only Key Vault config, Claude via Foundry, deepagents chat with SSE streaming, todos, tool-call events, Mongo persistence | In progress ([#9](https://github.com/ai-shubham-mishra/Dana-AI/issues/9)) |

## Architecture

- `backend/`: FastAPI service
  - `api/`: routes (`/api/v1/me`, `/chats`, `/jobs`) and the app factory
  - `agent/`: deepagents orchestrator, `AGENTS.md` memory, and `skills/` (one folder per skill with `SKILL.md`)
  - `integrations/`: `keyvault/` (read-only secret reader), `llm/` (Claude via Azure AI Foundry), `mongo/` (users, chats, messages, jobs)
  - `config/`: settings loaded from `backend/.env`
  - `tests/`: pytest suite
- `frontend/`: Next.js app (React, Tailwind, TanStack Query)
  - `app/`: routes `/chat` and `/jobs` in the `(app)` group
  - `components/`: sidebar, chat window, jobs dashboard
  - `lib/`: API client, SSE reader, chat streaming client, auth token helpers
- `docker-compose.yml`: local Mongo 7 (port 27017) and Azurite blob storage (port 10000)

## Prerequisites

- Docker (for Mongo and Azurite)
- Python 3.12 or newer
- Node.js 20 or newer and npm

## Local setup

1. Start the local infrastructure:

   ```bash
   docker compose up -d
   ```

2. Backend:

   ```bash
   cd backend
   python3 -m venv .venv
   ./.venv/bin/pip install -r requirements.txt
   cp .env.example .env   # then fill in the values listed below
   ./.venv/bin/uvicorn api.main:app --reload --port 8000
   ```

3. Frontend (in a second terminal):

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open http://localhost:3000. Paste a valid access token into the sign-in dialog. The frontend reads `NEXT_PUBLIC_API_BASE_URL` and defaults to `http://localhost:8000`.

4. Tests and checks:

   ```bash
   cd backend && ./.venv/bin/python -m pytest -q
   cd frontend && npm run lint && npx tsc --noEmit && npm run build
   ```

## Configuration

Copy `backend/.env.example` to `backend/.env`. Never commit `.env` files. Values are listed by name only here.

| Variable | Purpose |
|---|---|
| `MONGO_URI`, `MONGO_DB` | Local Mongo connection |
| `BLOB_CONNECTION_STRING`, `BLOB_CONTAINER` | Azurite blob storage |
| `JWT_MASTER_TOKEN`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_LEEWAY_SECONDS` | HS256 access-token verification, same scheme as analytics-studio and DeepAgent |
| `CORS_ORIGINS`, `APP_ENV` | Browser origins and environment name |
| `AZURE_KEYVAULT_URL` | Key Vault URL |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Bootstrap credentials for the read-only service principal |
| `LLM_MODEL` | Claude deployment name (default `claude-sonnet-5-5`) |

### Key Vault access

The backend reads secrets through a read-only service principal. It only calls `get_secret`. The LLM uses these secret names:

- `AZURE-FOUNDARY-SC-API-ENDPOINT`
- `AZURE-FOUNDARY-SC-API-KEY`

The "FOUNDARY" spelling is intentional and matches the DeepAgent vault. If the bootstrap variables are missing, the chat endpoints return 503 and do not fall back to any other credential.

## Git workflow

- `main` is the release branch. The owner merges it manually.
- `staging` is the integration branch. Every issue and feature merges here first.
- For each change: open an issue, create a branch linked to it (for example `feature/9-llm-agent-chat`), push, open a PR into `staging`, test, then merge.
- Commit messages carry a tag and the issue number: `(feature) #9 ...` or `(bugfix) #12 ...`.
