# Self-Service Registration & Tenant Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public self-service signup flow (register account → create organization → land on dashboard as `tenant_admin`), and close the password-strength, slug-format, and rate-limiting gaps in the two backend endpoints it relies on.

**Architecture:** Two new Next.js pages under `frontend/app/(auth)/` reuse the existing `POST /auth/register` and `POST /tenants` endpoints via the existing `authService` and a new `tenantsService`. Three backend hardening changes (Pydantic field constraints on two schemas, `slowapi` rate limits on two routes) close the gaps identified in the design spec. Full design: `docs/superpowers/specs/2026-08-01-self-service-registration-design.md`.

**Tech Stack:** FastAPI + Pydantic v2 (backend), Next.js 15 + Zustand + axios (frontend), pytest (backend tests).

## Global Constraints

- Backend route-level tests require a local Postgres reachable at `localhost:5432` with the `aegisrag_test` database present. Start it with `cd "/home/lenovo/Own Projects/AegisRAG/infra" && docker compose up -d postgres` before running any test in this plan that uses the `client`/`db` fixtures. Verified baseline: **253 passed** via `cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest -q`.
- No automated test asserts `429` rate-limit responses in this codebase — `backend/app/tests/conftest.py` sets `os.environ["RATE_LIMIT_ENABLED"] = "false"` globally for the whole test suite, and the existing `/auth/login` rate limit (which this plan's two new limits are modeled on) isn't tested for `429` either. This plan follows that existing precedent: rate-limit wiring is verified by code review (decorator present, correct setting referenced) plus a full-suite regression run, not a dedicated 429 test.
- Slug format regex, used identically in the backend Pydantic constraint and the frontend client-side check: `^[a-z0-9]+(-[a-z0-9]+)*$` (lowercase letters, digits, hyphens; no leading/trailing/double hyphens by construction since each segment must be non-empty alphanumeric).
- Minimum password length: `8` characters, enforced both server-side (Pydantic) and client-side (form validation) — server-side is the actual security boundary.
- `frontend/services/auth.ts`'s existing `authService.register` signature is `register(email: string, password: string, full_name: string)` — note the argument order (email first, not full name first). Use it as-is; do not change its signature.
- Rate limit values: `"10/minute"` for both new limits, matching the existing `settings.LOGIN_RATE_LIMIT` value exactly.

---

## File Structure

- Modify: `backend/app/schemas/auth.py` — add password min-length constraint
- Modify: `backend/app/schemas/tenant.py` — add slug format/length constraints
- Modify: `backend/app/core/config.py` — add `REGISTER_RATE_LIMIT`, `TENANT_CREATE_RATE_LIMIT` settings
- Modify: `backend/app/api/routes/auth.py` — rate-limit `/auth/register`
- Modify: `backend/app/api/routes/tenants.py` — rate-limit `POST /tenants`
- Create: `backend/app/tests/test_auth_api.py` — route-level tests for register
- Create: `backend/app/tests/test_tenant_api.py` — route-level tests for tenant creation
- Create: `frontend/services/tenants.ts` — `tenantsService.create(name, slug)`
- Create: `frontend/app/(auth)/register/page.tsx`
- Create: `frontend/app/(auth)/create-organization/page.tsx`
- Modify: `frontend/app/(auth)/login/page.tsx` — add "Sign up" link

---

## Task 1: Backend — password length validation on register

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Create: `backend/app/tests/test_auth_api.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/register` returns `422` when `password` is under 8 characters. `201`/`400` behavior for valid password / duplicate email is unchanged (pre-existing, covered by new tests for regression safety).

- [ ] **Step 1: Ensure the local test Postgres is running**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/infra" && docker compose up -d postgres
```

- [ ] **Step 2: Write the test file**

Create `backend/app/tests/test_auth_api.py`:

```python
"""API integration tests for auth registration."""


class TestRegister:
    def test_register_happy_path_returns_viewer(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@test.com", "password": "longenough123", "full_name": "New User"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@test.com"
        assert body["role"] == "viewer"
        assert body["tenant_id"] is None

    def test_register_duplicate_email_rejected(self, client):
        payload = {"email": "dupe@test.com", "password": "longenough123", "full_name": "Dupe"}
        first = client.post("/api/v1/auth/register", json=payload)
        assert first.status_code == 201
        second = client.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 400
        assert second.json()["detail"] == "Email already registered."

    def test_register_password_too_short_rejected(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "shortpw@test.com", "password": "short", "full_name": "Short"},
        )
        assert resp.status_code == 422
```

- [ ] **Step 3: Run the tests and confirm only the new constraint is unmet**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest app/tests/test_auth_api.py -v
```

Expected: `test_register_happy_path_returns_viewer` and `test_register_duplicate_email_rejected` **PASS** (pre-existing behavior), `test_register_password_too_short_rejected` **FAILS** (currently no length constraint exists, so a 5-character password is accepted with `201`, not `422`).

- [ ] **Step 4: Add the constraint**

In `backend/app/schemas/auth.py`, change:

```python
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
```

to:

```python
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
```

- [ ] **Step 5: Run the tests again — all pass**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest app/tests/test_auth_api.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add backend/app/schemas/auth.py backend/app/tests/test_auth_api.py
git commit -m "Require an 8+ character password on registration"
```

---

## Task 2: Backend — tenant slug format validation

**Files:**
- Modify: `backend/app/schemas/tenant.py`
- Create: `backend/app/tests/test_tenant_api.py`

**Interfaces:**
- Consumes: `client` fixture's `admin_headers` fixture from `conftest.py` (an already-tenant-scoped `tenant_admin` user, for the "already has a tenant" case).
- Produces: `POST /api/v1/tenants` returns `422` for a slug that doesn't match `^[a-z0-9]+(-[a-z0-9]+)*$` or is outside 3-50 characters. `201`/`400`/`409` behavior for valid/duplicate-tenant/duplicate-slug cases is unchanged (pre-existing, covered by new tests for regression safety).

- [ ] **Step 1: Write the test file**

Create `backend/app/tests/test_tenant_api.py`:

```python
"""API integration tests for tenant creation."""


def _register_and_token(client, email):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "longenough123", "full_name": "Creator"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "longenough123"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestCreateTenant:
    def test_create_tenant_happy_path_promotes_creator(self, client):
        headers = _register_and_token(client, "admin1@test.com")
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "Acme Corp", "slug": "acme-corp"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "acme-corp"

        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.json()["role"] == "tenant_admin"
        assert me.json()["tenant_id"] is not None

    def test_create_tenant_duplicate_slug_rejected(self, client):
        headers1 = _register_and_token(client, "admin2@test.com")
        client.post("/api/v1/tenants", json={"name": "First", "slug": "shared-slug"}, headers=headers1)

        headers2 = _register_and_token(client, "admin3@test.com")
        resp = client.post(
            "/api/v1/tenants", json={"name": "Second", "slug": "shared-slug"}, headers=headers2
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Tenant slug already taken."

    def test_create_tenant_user_already_has_tenant_rejected(self, client, admin_headers):
        resp = client.post(
            "/api/v1/tenants", json={"name": "New Org", "slug": "new-org"}, headers=admin_headers
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "User already belongs to a tenant."

    def test_create_tenant_invalid_slug_format_rejected(self, client):
        headers = _register_and_token(client, "admin4@test.com")
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "Bad Slug Co", "slug": "Not A Valid Slug!!"},
            headers=headers,
        )
        assert resp.status_code == 422
```

- [ ] **Step 2: Run the tests and confirm only the new constraint is unmet**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest app/tests/test_tenant_api.py -v
```

Expected: `test_create_tenant_happy_path_promotes_creator`, `test_create_tenant_duplicate_slug_rejected`, and `test_create_tenant_user_already_has_tenant_rejected` **PASS** (pre-existing behavior). `test_create_tenant_invalid_slug_format_rejected` **FAILS** (currently no format constraint, so the malformed slug is accepted with `201`, not `422`).

- [ ] **Step 3: Add the constraint**

In `backend/app/schemas/tenant.py`, change:

```python
from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    slug: str
```

to:

```python
from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
```

- [ ] **Step 4: Run the tests again — all pass**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest app/tests/test_tenant_api.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add backend/app/schemas/tenant.py backend/app/tests/test_tenant_api.py
git commit -m "Validate tenant slug format (lowercase alphanumeric + hyphens) on creation"
```

---

## Task 3: Backend — rate limit register and create-tenant

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/routes/tenants.py`

**Interfaces:**
- Consumes: `backend/app/tests/test_auth_api.py` and `backend/app/tests/test_tenant_api.py` from Tasks 1-2, run here as a regression check (both files' tests must still pass — `RATE_LIMIT_ENABLED=false` in the test environment per Global Constraints means these new decorators don't change their behavior).
- Produces: `settings.REGISTER_RATE_LIMIT`, `settings.TENANT_CREATE_RATE_LIMIT` (both `"10/minute"`).

- [ ] **Step 1: Add the two settings**

In `backend/app/core/config.py`, change:

```python
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT: str = "10/minute"
```

to:

```python
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT: str = "10/minute"
    REGISTER_RATE_LIMIT: str = "10/minute"
    TENANT_CREATE_RATE_LIMIT: str = "10/minute"
```

- [ ] **Step 2: Rate-limit the register route**

In `backend/app/api/routes/auth.py`, `Request`, `settings`, and `limiter` are already imported. Change:

```python
@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)) -> User:
    return AuthService(db).register(data)
```

to:

```python
@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
def register(data: UserRegister, request: Request, db: Session = Depends(get_db)) -> User:
    return AuthService(db).register(data)
```

- [ ] **Step 3: Rate-limit the create-tenant route**

In `backend/app/api/routes/tenants.py`, change the imports from:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantService
```

to:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantResponse
from app.services.audit_service import AuditService
from app.services.tenant_service import TenantService
```

Then change:

```python
@router.post("", response_model=TenantResponse, status_code=201)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TenantResponse:
```

to:

```python
@router.post("", response_model=TenantResponse, status_code=201)
@limiter.limit(settings.TENANT_CREATE_RATE_LIMIT)
def create_tenant(
    data: TenantCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TenantResponse:
```

- [ ] **Step 4: Run the full backend suite as a regression check**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest -q
```

Expected: `257 passed` (the 253-test baseline from Global Constraints plus the 3 + 4 tests added in Tasks 1-2 — `RATE_LIMIT_ENABLED=false` in tests means the new decorators are inert here, so nothing should newly fail).

- [ ] **Step 5: Commit**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add backend/app/core/config.py backend/app/api/routes/auth.py backend/app/api/routes/tenants.py
git commit -m "Rate-limit /auth/register and POST /tenants to match /auth/login"
git push origin main
```

Pushing here (rather than batching with later frontend tasks) lets Railway rebuild and deploy the backend service independently, so the API-side hardening is live before the frontend pages that depend on it are built.

---

## Task 4: Frontend — /register page

**Files:**
- Create: `frontend/app/(auth)/register/page.tsx`

**Interfaces:**
- Consumes: `authService.register(email, password, full_name)` and `authService.login(email, password)` and `authService.me()` from `frontend/services/auth.ts` (all pre-existing, signatures unchanged). `useAuthStore` from `frontend/stores/authStore.ts` (pre-existing, `setAuth(token, user)`).
- Produces: route `/register`. On success, calls `setAuth` and navigates to `/create-organization` (consumed by Task 5's route guard).

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authService } from "@/services/auth";
import { useAuthStore } from "@/stores/authStore";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await authService.register(email, password, fullName);
      const { access_token } = await authService.login(email, password);
      if (typeof window !== "undefined") {
        localStorage.setItem("aegis_token", access_token);
      }
      const me = await authService.me();
      setAuth(access_token, me);
      router.push("/create-organization");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Registration failed";
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">AegisRAG</CardTitle>
          <CardDescription>Create your account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="fullName">
                Full name
              </label>
              <Input
                id="fullName"
                type="text"
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="email">
                Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="password">
                Password
              </label>
              <Input
                id="password"
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating account…" : "Create account"}
            </Button>
            <p className="text-center text-sm text-slate-600">
              Already have an account?{" "}
              <Link href="/login" className="font-medium text-slate-900 underline">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build compiles**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/frontend" && npm run build
```

Expected: build succeeds, `/register` appears in the route list output.

- [ ] **Step 3: Commit**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add frontend/app/\(auth\)/register/page.tsx
git commit -m "Add self-service registration page"
```

---

## Task 5: Frontend — /create-organization page

**Files:**
- Create: `frontend/services/tenants.ts`
- Create: `frontend/app/(auth)/create-organization/page.tsx`

**Interfaces:**
- Consumes: `useAuthStore` (`token`, `setAuth`) from `frontend/stores/authStore.ts`; `authService.me()` from `frontend/services/auth.ts`; the `api` axios instance from `frontend/lib/api.ts` (already attaches the bearer token from `localStorage` via its request interceptor, so no manual header needed).
- Produces: `tenantsService.create(name: string, slug: string): Promise<Tenant>` (new); route `/create-organization`, reachable only when `useAuthStore().token` is set (redirects to `/login` otherwise).

- [ ] **Step 1: Create the tenants service**

```typescript
import { api } from "@/lib/api";
import type { Tenant } from "@/types";

export const tenantsService = {
  async create(name: string, slug: string): Promise<Tenant> {
    const { data } = await api.post("/tenants", { name, slug });
    return data;
  },
};
```

- [ ] **Step 2: Create the page**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { tenantsService } from "@/services/tenants";
import { authService } from "@/services/auth";
import { useAuthStore } from "@/stores/authStore";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

export default function CreateOrganizationPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    }
  }, [token, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!SLUG_PATTERN.test(slug)) {
      setError("Slug must be lowercase letters, numbers, and hyphens only.");
      return;
    }
    setLoading(true);
    try {
      await tenantsService.create(name, slug);
      const me = await authService.me();
      if (token) setAuth(token, me);
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Could not create organization";
      setError(String(msg));
    } finally {
      setLoading(false);
    }
  }

  if (!token) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">AegisRAG</CardTitle>
          <CardDescription>Name your organization</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="orgName">
                Organization name
              </label>
              <Input
                id="orgName"
                type="text"
                placeholder="Acme Corp"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="orgSlug">
                Organization slug
              </label>
              <Input
                id="orgSlug"
                type="text"
                placeholder="acme-corp"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating…" : "Create organization"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Verify the build compiles**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/frontend" && npm run build
```

Expected: build succeeds, `/create-organization` appears in the route list output.

- [ ] **Step 4: Commit**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add frontend/services/tenants.ts frontend/app/\(auth\)/create-organization/page.tsx
git commit -m "Add organization-creation page"
```

---

## Task 6: Frontend — link from login page, then full manual verification

**Files:**
- Modify: `frontend/app/(auth)/login/page.tsx`

**Interfaces:**
- Consumes: `/register` route from Task 4.

- [ ] **Step 1: Add the sign-up link**

In `frontend/app/(auth)/login/page.tsx`, add the import and the link. Change:

```tsx
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function LoginPage() {
```

to:

```tsx
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import Link from "next/link";

export default function LoginPage() {
```

And change the closing of the form (the `Button` and the `</form>` that follows it):

```tsx
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
```

to:

```tsx
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-sm text-slate-600">
              Need an account?{" "}
              <Link href="/register" className="font-medium text-slate-900 underline">
                Sign up
              </Link>
            </p>
          </form>
```

- [ ] **Step 2: Verify the build compiles**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/frontend" && npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Commit and push**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add frontend/app/\(auth\)/login/page.tsx
git commit -m "Link to the new sign-up flow from the login page"
git push origin main
```

Pushing triggers Railway to auto-rebuild `aegisrag-frontend` (and `aegisrag-backend`/`aegisrag-worker` already have Task 3's push live).

- [ ] **Step 4: Manually verify the full flow against the live deployment**

Once Railway's deploy finishes, walk through every case from the design's error-handling table against `https://aegisrag.dev`:

1. **Happy path**: `/register` → fill in a new email/name/8+ char password → lands on `/create-organization` → fill in a name/slug → lands on `/dashboard` logged in as `tenant_admin`.
2. **Duplicate email**: register again with the same email → inline error "Email already registered."
3. **Password too short**: try a 4-character password → inline error before submit (client-side) — also confirm the server rejects it if the client check is bypassed (e.g. via browser devtools removing `minLength`).
4. **Invalid slug**: on `/create-organization`, try a slug with spaces/uppercase → inline error before submit.
5. **Duplicate slug**: register a second new account, try to reuse a slug from step 1 → inline error "Tenant slug already taken.", and confirm you can fix just the slug field and resubmit successfully.
6. **Guard**: while logged out, visit `https://aegisrag.dev/create-organization` directly → redirected to `/login`.
7. **Login page link**: from `/login`, click "Sign up" → lands on `/register`. From `/register`, click "Sign in" → lands on `/login`.

Fix anything that doesn't match the design before considering this plan complete.
