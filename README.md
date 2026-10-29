# Dana AI

Dana AI is a multi-tenant, agentic marketing-model training product. A chat agent, built on the DeepAgent architecture, reads each organization's connector data (Meta Ads, Google Ads, and others), asks the user what to model, writes the training code for that data, and trains the model. Training runs locally for now and can move to Azure ML later. MMM is the first model family, and more predictive models will follow.

Frontend styling follows the analytics-studio branding.

## Status

| Milestone | Scope | Status |
|---|---|---|
| 1 | Docker Compose stack (Mongo, Azurite), FastAPI with JWT auth and org membership checks, Next.js shell | Done |
| Nav | Stacked Chat and Jobs navigation (tabs, no toggle) | Done |
| 2 | Read-only Key Vault config, Claude via Foundry, deepagents chat with SSE streaming, todos, tool-call events, Mongo persistence | Done ([#9](https://github.com/ai-shubham-mishra/Dana-AI/issues/9)) |
| 3 (first slice) | HITL approvals (`ask_user`, approve/edit/reject) and durable Mongo-backed checkpoints | In progress ([#15](https://github.com/ai-shubham-mishra/Dana-AI/issues/15)) |

## Architecture

- `backend/`: FastAPI service
  - `api/`: routes (`/api/v1/me`, `/chats`, `/jobs`, chat approvals) and the app factory
  - `agent/`: deepagents orchestrator. Folders: `config/` (`AGENTS.md` memory and `parent_skill.md` playbook), `skills/` (one folder per skill with `SKILL.md`), `tools/` (per-domain tools, e.g. `training/`), `components/` (todos, hitl policy and `ask_user`, and other per-domain components), `middleware/` (custom deepagents middleware)
  - `integrations/`: `auth/` (JWT verification and the Key Vault JWT secret loader), `keyvault/` (read-only secret reader), `llm/` (Claude via Azure AI Foundry), `mongo/` (users, chats, messages, jobs), `checkpoint/` (Mongo-backed LangGraph checkpointer)
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
   ./.venv/bin/uvicorn api.main:app --reload --port 8001
   ```

3. Frontend (in a second terminal):

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open http://localhost:3000. Paste a valid access token into the sign-in dialog. The frontend reads `NEXT_PUBLIC_API_BASE_URL` and defaults to `http://localhost:8001`.

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
| `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_LEEWAY_SECONDS` | Access-token verification settings. The HS256 secret comes from Key Vault `JWT-MASTER-TOKEN` (same scheme as analytics-studio and DeepAgent) |
| `CORS_ORIGINS`, `APP_ENV` | Browser origins and environment name |
| `AZURE_KEYVAULT_URL` | Key Vault URL |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Bootstrap credentials for the read-only service principal |
| `LLM_MODEL` | Claude deployment name (default `claude-sonnet-5-5`) |

### Key Vault access

The backend reads secrets through a read-only service principal. It only calls `get_secret`. Secrets used:

- `JWT-MASTER-TOKEN`: HS256 key for access tokens. Loaded once at startup. If it cannot be read, auth returns 503 (fail closed).
- `AZURE-FOUNDARY-SC-API-ENDPOINT`, `AZURE-FOUNDARY-SC-API-KEY`: Claude via Foundry. The LLM uses these.

The "FOUNDARY" spelling is intentional and matches the DeepAgent vault. If the bootstrap variables are missing, the chat endpoints return 503 and do not fall back to any other credential.

To mint a dev token from the vault secret: `cd backend && PYTHONPATH=. ./.venv/bin/python scripts/seed_dev.py --user-id U --org-id O --mint-token`.

## Approvals (HITL) and checkpoints

- The agent pauses before a gated action and emits an `interrupt` SSE event instead of `done`. The payload lists each action with its `allowed_decisions`.
- `GET /api/v1/chats/{id}/pending` returns the pending approval, or `null`.
- `POST /api/v1/chats/{id}/resume` with `{"decisions": [...]}` continues the run. Decision types: `approve`, `edit` (with `edited_action: {name, args}`), `reject` (optional `message`), and `respond` (the user's answer for `ask_user`).
- `ask_user` accepts only `respond`. `start_training_job` accepts `approve`, `edit`, or `reject`. Decisions that do not match are rejected with 422. Resume without a pending approval returns 409. Sending a new message while an approval is pending returns 409.
- Run state is stored in the `agent_checkpoints` and `agent_checkpoint_writes` collections in Mongo, so a pending approval survives a backend restart.

## Thinking and run progress

- Text the agent writes before its last tool event is process. It is stored in the message's `thinking` field and shown in a collapsible **Thinking** block. The text after the last tool event is the answer, stored in `content`. A run that pauses for approval stores its text as thinking only.
- The approval card renders outside the Thinking block.
- A finished run stays mounted in the thread, and its Thinking block stays open. It is not swapped for the saved message during the same session. After a page reload, the saved message is shown instead, without tool or todo chips.

## Git workflow

- `main` is the release branch. The owner merges it manually.
- `staging` is the integration branch. Every issue and feature merges here first.
- For each change: open an issue, create a branch linked to it with `gh issue develop <n> --name feature/<n>-<slug> --base staging`, push, open a PR into `staging` that says `Refs #<n>`, test, then merge.
- Commit messages carry a tag and the issue number: `(feature) #9 ...` or `(bugfix) #12 ...`.
