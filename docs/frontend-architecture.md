# Frontend Architecture

## Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript (strict) |
| Styling | TailwindCSS v3 |
| Components | Custom UI components (shadcn/ui-compatible patterns) |
| State | Zustand (auth, chat stream state) |
| Server state | TanStack Query v5 |
| HTTP | Axios with auth interceptor |
| Icons | lucide-react |

---

## Directory Layout

```
frontend/
  app/
    (auth)/
      login/page.tsx          Login form
    (dashboard)/
      layout.tsx              Sidebar + main wrapper
      dashboard/page.tsx      Overview with doc count, audit events
      documents/
        page.tsx              Document list, upload, delete, reindex
        [id]/page.tsx         Document detail, classification, PII findings
      chat/page.tsx           Chat sessions + streaming RAG
      audit/page.tsx          Audit log with filters
      users/page.tsx          User management + invite flow
      pii/page.tsx            PII findings overview
      evals/page.tsx          RAGAS evaluation run scores
    layout.tsx                Root layout (QueryProvider)
    globals.css
  components/
    layout/
      Sidebar.tsx             Role-filtered nav links
      Header.tsx              Page title + role badge
    ui/
      button.tsx, input.tsx, badge.tsx, card.tsx
  hooks/
    useAuth.ts                Login/logout, reads from authStore
    useStream.ts              SSE streaming state machine
  lib/
    api.ts                    Axios instance + auth interceptor + streamUrl
    utils.ts                  cn(), formatDate(), classificationColor()
  providers/
    QueryProvider.tsx         TanStack Query client wrapper
  services/
    auth.ts, documents.ts, rag.ts, audit.ts, users.ts, evals.ts
  stores/
    authStore.ts              Zustand: token + user, persisted to localStorage
    chatStore.ts              Zustand: streaming token accumulation
  types/index.ts              Shared TypeScript interfaces
  middleware.ts               Auth gate: redirects unauthenticated users to /login
```

---

## Authentication

1. User submits login form → `authService.login()` → POST `/api/v1/auth/login`
2. Token stored in `localStorage` (for axios interceptor) and as a cookie (for middleware)
3. `middleware.ts` checks `aegis_token` cookie on every request; redirects to `/login` if missing
4. Axios interceptor reads `aegis_token` from localStorage and sets `Authorization: Bearer …`
5. On 401 response: clears token and redirects to `/login`

---

## Streaming (SSE)

`useStream` hook wraps `ragService.streamQuery()`:

1. Opens a `fetch` with `method: POST` to `/api/v1/rag/query-stream`
2. Reads body as a `ReadableStream`, decodes lines
3. Each `data: <json>` line is parsed; callbacks fire for `token`, `sources`, `done`, `error`
4. `answer` string is built up token by token in local state
5. Returns an `abort` function that calls `AbortController.abort()`

---

## Role-Based UI

`Sidebar.tsx` filters nav items by `user.role` from the auth store. Restricted pages (audit, users, PII, evals) only render their nav links for `tenant_admin` and `compliance_officer`. The backend enforces the same restrictions — the frontend filtering is UX-only.

---

## Running the Frontend

### Development

```bash
cd frontend
cp .env.local.example .env.local
# Edit NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Frontend available at http://localhost:3000.

### Production (Docker)

```bash
cd infra
docker compose up --build frontend
```

The frontend container builds a standalone Next.js output. `NEXT_PUBLIC_API_URL` is baked in at build time — set it as a build arg or use the rewrite proxy in `next.config.ts`.
