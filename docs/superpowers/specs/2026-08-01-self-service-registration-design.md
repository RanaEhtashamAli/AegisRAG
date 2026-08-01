# Self-Service Registration & Tenant Creation — Design

## Problem

AegisRAG has no way for a new user to get their first account except calling `POST /auth/register` and `POST /tenants` directly via `curl` — there is no frontend page for it (only `/login` exists under `frontend/app/(auth)/`). This was fine for a one-time manual bootstrap, but the deployment is public (`https://aegisrag.dev`), so it should support normal self-service signup like any SaaS product.

Two related backend gaps make the existing endpoints unsafe to expose behind a public "Sign up" button as-is:
- `POST /auth/register`'s `UserRegister` schema (`backend/app/schemas/auth.py`) has no password length/complexity requirement — even an empty string passes.
- `POST /tenants`'s `TenantCreate` schema (`backend/app/schemas/tenant.py`) has no slug format validation — `"My Org!!"` would pass and produce a broken, non-URL-safe slug.
- Neither endpoint is rate-limited (unlike `/auth/login`, which uses `@limiter.limit(settings.LOGIN_RATE_LIMIT)` via `slowapi`), leaving both open to abuse/spam once linked from the public UI.

## Goals

- A public, self-service "Sign up" flow: anyone can create an account and their own new organization (tenant), becoming its `tenant_admin`.
- Close the password-strength, slug-format, and rate-limiting gaps identified above, since this design is what turns those endpoints from obscure/API-only into a linked, public-facing feature.
- Reuse the existing two-call backend model (`/auth/register` then `/tenants`) — no new backend endpoints, only validation/rate-limit hardening of the existing two.

## Non-goals

- Email verification before login (out of scope — YAGNI for this pass; the existing invitation flow already handles adding *other* users to an existing tenant, which is a separate, already-solved problem).
- Joining an existing tenant via public signup (that's what the invitation flow is for; this design is specifically for creating a *new* tenant).
- Any new frontend test framework — the repo has none today (`frontend/package.json` only has `dev`/`build` scripts), and this change doesn't warrant introducing one.

## Architecture & Flow

Two new pages under `frontend/app/(auth)/`, matching the existing `login/page.tsx` Card-based layout and using the existing `lib/api.ts` axios client:

1. **`/register`** — full name, email, password fields.
   - Submit → `POST /auth/register` (creates a user with `role="viewer"`, `tenant_id=null`) → on success, `POST /auth/login` with the same credentials (reusing the existing login API call, not a new endpoint) to obtain a token → store token+user via the existing Zustand auth store (`setAuth`) → redirect to `/create-organization` (not `/dashboard` — the user has no tenant yet, so dashboard routes aren't meaningful).
   - The login page gets a new "Need an account? Sign up" link under the Sign in button, pointing to `/register`. `/register` gets a matching "Already have an account? Sign in" link back to `/login`.

2. **`/create-organization`** — org name, org slug (two separate fields, not auto-derived).
   - Route guard: requires a valid token (redirect to `/login` if missing). This is the one authenticated screen a user is allowed to be on *without* a tenant yet — every other `/dashboard/*` route assumes a tenant exists.
   - Submit → `POST /tenants` with the stored bearer token. `TenantService.create_tenant` (`backend/app/services/tenant_service.py:15`) creates the tenant and promotes the calling user to `tenant_admin` (existing behavior, unchanged).
   - On success: update the stored user object (now has `tenant_id` and `role="tenant_admin"`) → redirect to `/dashboard`.

## Backend changes

1. **`backend/app/schemas/auth.py`** — `UserRegister.password` gets `Field(min_length=8)`.
2. **`backend/app/schemas/tenant.py`** — `TenantCreate.slug` gets a pattern constraint: lowercase letters, digits, and hyphens only, not starting/ending with a hyphen (`^[a-z0-9]+(?:-[a-z0-9]+)*$`), length 3-50. `name` gets a reasonable length bound (1-100) but no format restriction.
3. **`backend/app/core/config.py`** — add `REGISTER_RATE_LIMIT: str = "10/minute"` and `TENANT_CREATE_RATE_LIMIT: str = "10/minute"`, alongside the existing `LOGIN_RATE_LIMIT`.
4. **`backend/app/api/routes/auth.py`** — add `@limiter.limit(settings.REGISTER_RATE_LIMIT)` to the register route, matching the existing decorator pattern on `/auth/login`.
5. **`backend/app/api/routes/tenants.py`** — add `@limiter.limit(settings.TENANT_CREATE_RATE_LIMIT)` to the create-tenant route.

These are additive, backward-compatible constraints — no existing valid registrations or tenant slugs are affected (the multi-tenant model, invitation flow, and role system are all unchanged).

## Frontend changes

- `frontend/app/(auth)/register/page.tsx` — new page, modeled on `login/page.tsx`'s structure (Card, CardHeader, CardTitle, form fields, error display pattern).
- `frontend/app/(auth)/create-organization/page.tsx` — new page, same structural pattern.
- `frontend/app/(auth)/login/page.tsx` — add the "Sign up" link.
- `frontend/services/auth.ts` — `authService.register(email, password, full_name)` already exists and already calls `POST /auth/register`; the new `/register` page just needs to call it (and then `authService.login`) rather than needing new API-layer code.
- `frontend/services/tenants.ts` — new file, following the existing `services/*.ts` pattern (see `auth.ts`): `tenantsService.create(name, slug)` calling `POST /tenants`.
- Client-side validation mirrors the backend constraints (password ≥ 8 chars, slug pattern) purely for immediate UX feedback — not a security boundary, the server still enforces both.

## Error handling

| Case | Backend response | Frontend behavior |
|---|---|---|
| Duplicate email | `400 {"detail": "Email already registered."}` | Inline error under the email field on `/register` |
| Password too short | `422` (Pydantic) | Inline error under the password field |
| Invalid slug format | `422` (Pydantic) | Inline error under the slug field |
| Duplicate slug | `409 {"detail": "Tenant slug already taken."}` | Inline error under the slug field on `/create-organization`; user edits just that field and resubmits — org name and their session are preserved |
| Rate limited | `429` | Generic "Too many attempts, try again in a minute" banner, same pattern as `/auth/login`'s existing 429 handling |
| Network/500 | n/a | Generic top-of-form red-text error banner, matching the existing pattern already used on `/login` |

## Testing

- **Backend**: extend `backend/app/tests/test_auth.py` with cases for password-too-short (`422`) and register rate-limiting (`429` after exceeding `REGISTER_RATE_LIMIT` within the window). Add equivalent tests for `/tenants`: invalid slug format (`422`), duplicate slug (`409`), rate-limiting (`429`).
- **Frontend**: no automated test framework exists in this repo today; verify manually against the local dev server (`npm run dev`), covering: happy path (register → create org → land on dashboard as `tenant_admin`), duplicate email, weak password, invalid slug format, duplicate slug, and the "already logged in, no tenant yet" guard on `/create-organization`.
