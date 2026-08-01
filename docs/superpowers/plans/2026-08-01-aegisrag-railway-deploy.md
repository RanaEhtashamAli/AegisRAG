# AegisRAG Railway Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect AegisRAG's GitHub repo to Railway as 3 services (backend, Celery worker, frontend) on their own domains with HTTPS, such that pushing to `main` automatically rebuilds and redeploys.

**Architecture:** Three Railway services all built from this one repo: `aegisrag-backend` (root directory `backend/`, serves the FastAPI app and gets custom domain `api.$AEGISRAG_DOMAIN`), `aegisrag-worker` (same root directory and image, Celery worker via a custom start command, no public domain), and `aegisrag-frontend` (root directory `frontend/`, gets custom domain `$AEGISRAG_DOMAIN`). All 3 connect to the shared Postgres/Redis/Qdrant/Ollama services already running in the `homelab` Railway project via private networking. Once each service is linked to this GitHub repo, Railway rebuilds and redeploys it automatically on every push to `main` — no workflow files, no registry, no SSH.

**Tech Stack:** Railway, Docker (backend and frontend both already have Dockerfiles), `uv`, Next.js 15.

## Prerequisites (from the `homelab-infra` plan — do not start here first)

This plan assumes `homelab-infra`'s plan (`homelab-infra/docs/superpowers/plans/2026-08-01-railway-foundation-and-shared-services.md`) is already done. In particular, you need, all recorded during that plan:
- The `homelab` Railway project already exists, with Postgres, Redis, Qdrant, and Ollama services running in it
- `AEGISRAG_DB_PASSWORD` — the password generated for the `aegisrag` Postgres role/database
- Postgres, Redis, and Qdrant's exact private networking domains (each ends in `.railway.internal`)
- Ollama's private networking domain and port `11434`, with `llama3.2:3b` already pulled
- Your purchased domain (referred to below as `$AEGISRAG_DOMAIN`, e.g. `aegisrag.dev`) — not yet pointed at anything, that happens in Task 3

## Global Constraints

- Redis logical DB index for AegisRAG on the shared instance: `0` (fixed by the homelab-infra plan — do not change).
- Postgres database/role for AegisRAG on the shared instance: `aegisrag` / `aegisrag` (already created by the homelab-infra plan's init script).
- Ollama model: `llama3.2:3b` (not `llama3.1:8b` — too slow on CPU-only Railway compute).
- AegisRAG uses **two** subdomains, not one: `$AEGISRAG_DOMAIN` for the frontend, `api.$AEGISRAG_DOMAIN` for the backend — Railway routes one custom domain to one service, so this replaces the old single-domain-with-path-routing approach a self-managed reverse proxy would give you.
- Secrets are generated with `openssl rand -hex 32`, never hardcoded into a committed file — they're set as Railway service variables (dashboard), not `.env` files in this repo.

---

## File Structure

- Modify: `frontend/Dockerfile` — add build-time `ARG`/`ENV` for `NEXT_PUBLIC_API_URL` (unchanged reasoning from the original plan: Next.js inlines `NEXT_PUBLIC_*` vars at build time, and Railway automatically forwards a service's variables into the build as matching `ARG`s, so declaring the `ARG` here is what makes the `NEXT_PUBLIC_API_URL` variable you set on the `aegisrag-frontend` Railway service actually reach the build)
- No other files change — `docker-compose.prod.yml` and `.github/workflows/deploy.yml` from the earlier VPS-based version of this plan are **not** created; Railway's dashboard/GitHub integration replaces both entirely

---

## Task 1: Fix the frontend Dockerfile for build-time API URL

**Files:**
- Modify: `frontend/Dockerfile`

- [ ] **Step 1: Add the build ARG/ENV before `npm run build`**

Change the `builder` stage from:

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
```

to:

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build
```

- [ ] **Step 2: Verify the build accepts the arg locally**

```bash
cd "/home/lenovo/Own Projects/AegisRAG"
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.aegisrag.dev -t aegisrag-frontend-test ./frontend
docker run --rm aegisrag-frontend-test grep -r "aegisrag.dev" /app/.next/static 2>/dev/null | head -1
```

Expected: the grep finds at least one match, confirming the URL was baked into the built assets. Substitute your actual `$AEGISRAG_API_DOMAIN` if different from `api.aegisrag.dev`.

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -m "Accept NEXT_PUBLIC_API_URL as a build arg for production images"
git push origin main
```

---

## Task 2: Create the 3 Railway services from this repo

**Files:** none (Railway dashboard configuration only)

- [ ] **Step 1: Create the backend service**

In the `homelab` Railway project canvas: New → GitHub Repo → select `RanaEhtashamAli/AegisRAG` (authorize Railway's GitHub App for this repo if prompted — one-time). Once created, rename the service to `aegisrag-backend` and set:
- Settings → Source → Root Directory: `backend`
- Settings → Source → Dockerfile Path: `Dockerfile` (relative to the root directory, i.e. `backend/Dockerfile`)
- Settings → Deploy → Branch: `main`

- [ ] **Step 2: Set the backend's environment variables**

Backend service → Variables tab → add each of these (Raw Editor is fastest — paste all at once):

```
APP_NAME=AegisRAG
APP_ENV=production
API_V1_PREFIX=/api/v1
SECRET_KEY=<generate with: openssl rand -hex 32>
ACCESS_TOKEN_EXPIRE_MINUTES=60
POSTGRES_HOST=<the Postgres service's private domain from homelab-infra Task 2>
POSTGRES_PORT=5432
POSTGRES_DB=aegisrag
POSTGRES_USER=aegisrag
POSTGRES_PASSWORD=<the AEGISRAG_DB_PASSWORD you saved from homelab-infra Task 3>
REDIS_URL=redis://default:<REDISPASSWORD from homelab-infra Task 2>@<Redis private domain from homelab-infra Task 2>:6379/0
QDRANT_HOST=<Qdrant's private domain from homelab-infra Task 4>
QDRANT_PORT=6333
QDRANT_COLLECTION=aegisrag_chunks
OLLAMA_BASE_URL=http://<Ollama's private domain from homelab-infra Task 4>:11434
OLLAMA_MODEL=llama3.2:3b
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
UPLOAD_DIR=/app/uploads
HYBRID_RETRIEVAL_ENABLED=true
RERANKING_ENABLED=false
PORT=8000
```

- [ ] **Step 3: Set the backend's start command and public domain**

Settings → Deploy → Custom Start Command:

```
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Settings → Networking → Custom Domain → enter `api.aegisrag.dev` (your actual `$AEGISRAG_API_DOMAIN`) → Railway shows you the exact CNAME record to add. Add it in Porkbun's DNS panel for that domain.

- [ ] **Step 4: Create the worker service from the same repo**

New → GitHub Repo → select `RanaEhtashamAli/AegisRAG` again (Railway allows multiple services from one repo). Rename it `aegisrag-worker` and set:
- Settings → Source → Root Directory: `backend`
- Settings → Source → Dockerfile Path: `Dockerfile`
- Settings → Deploy → Branch: `main`
- Settings → Deploy → Custom Start Command: `uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info --pool=solo` (`--pool=solo` is required — Celery's default prefork pool auto-detects the underlying *host's* CPU count, not the container's allocation, and on Railway that means spawning dozens of worker processes and getting OOM-killed in a restart loop)
- Variables tab: copy the exact same variables as Step 2 (no `PORT` needed since this service isn't web-facing — you can omit it or leave it, it's unused by the worker)
- No custom domain for this service — it's internal only

- [ ] **Step 5: Create the frontend service**

New → GitHub Repo → select `RanaEhtashamAli/AegisRAG` again. Rename it `aegisrag-frontend` and set:
- Settings → Source → Root Directory: `frontend`
- Settings → Source → Dockerfile Path: `Dockerfile`
- Settings → Deploy → Branch: `main`
- Variables tab: `NEXT_PUBLIC_API_URL=https://api.aegisrag.dev` (your actual `$AEGISRAG_API_DOMAIN` — Railway forwards this as the matching `ARG` during the build, per Task 1)
- Settings → Networking → Custom Domain → enter `aegisrag.dev` (your actual `$AEGISRAG_DOMAIN`) → add the CNAME Railway shows you in Porkbun

- [ ] **Step 6: Wait for DNS propagation and verify all 3 deploys succeeded**

```bash
for d in aegisrag.dev api.aegisrag.dev; do
  echo "$d -> $(dig +short $d)"
done
```

Expected: both resolve (may take a few minutes to an hour). In the Railway dashboard, confirm `aegisrag-backend`, `aegisrag-worker`, and `aegisrag-frontend` all show a green "Active" deployment.

```bash
curl -I https://api.aegisrag.dev/api/v1/health
curl -I https://aegisrag.dev
```

Expected: both return `HTTP/2 200` (adjust the backend health path if AegisRAG's actual health endpoint differs — check `backend/app/api/routes/` if this 404s).

---

## Task 3: Prove the auto-deploy loop works end to end

**Files:** none (verification only)

- [ ] **Step 1: Make a trivial, visible change and push it**

```bash
cd "/home/lenovo/Own Projects/AegisRAG"
echo "<!-- deploy test $(date -u +%FT%TZ) -->" >> frontend/README.md
git add frontend/README.md
git commit -m "Test auto-deploy"
git push origin main
```

- [ ] **Step 2: Confirm it deploys automatically, with no manual step**

Watch the `aegisrag-frontend` service's Deployments tab in the Railway dashboard — a new build should start within seconds of the push, with no manual trigger. Wait for it to go green, then:

```bash
curl -I https://aegisrag.dev
```

Expected: `HTTP/2 200`.

- [ ] **Step 3: Confirm all 3 services are stable**

In the Railway dashboard, check that `aegisrag-backend`, `aegisrag-worker`, and `aegisrag-frontend` all show "Active" with no crash/restart loop in their logs.

## Post-plan notes

- **Rollback**: Railway keeps every past deployment — Deployments tab → find the last good one → "Redeploy" to roll back a single service without touching the others.
- **Migrations**: if AegisRAG uses Alembic migrations, run them once against the new database via Railway's per-service Shell (backend service → open a deployment → shell/terminal icon) with `uv run alembic upgrade head` before the app is expected to work end-to-end — this plan doesn't automate that step, to avoid an untested migration running unattended in a deploy hook.
