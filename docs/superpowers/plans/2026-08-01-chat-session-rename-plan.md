# Chat Session Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user rename a chat session by double-clicking its title in the chat page's session list.

**Architecture:** One new backend route (`PATCH /chat/sessions/{session_id}`) wires the already-existing `ChatService.update_session_title` into the API. One frontend change adds inline-edit state to the session list already rendered in `chat/page.tsx`. Full design: `docs/superpowers/specs/2026-08-01-chat-session-rename-design.md`.

**Tech Stack:** FastAPI + Pydantic v2 (backend), Next.js 15 + TanStack Query (frontend), pytest.

## Global Constraints

- Title constraints: `min_length=1, max_length=255` (matches `ChatService.update_session_title`'s existing 255-char truncation).
- Ownership/tenant scoping: reuse `ChatService.get_session(session_id, user)` exactly as every other session route already does — do not write a new authorization check.
- Backend route-level tests require local Postgres reachable at `localhost:5432` with `aegisrag_test` present: `cd "/home/lenovo/Own Projects/AegisRAG/infra" && docker compose up -d postgres`.

---

## File Structure

- Modify: `backend/app/api/routes/chat.py` — add `ChatSessionRename` schema + `PATCH /sessions/{session_id}` route
- Create: `backend/app/tests/test_chat_api.py` — route-level tests (no route-level chat test file exists yet; `test_chat_service.py` only covers the service layer, including the pre-existing `update_session_title` service test — do not duplicate that one)
- Modify: `frontend/app/(dashboard)/chat/page.tsx` — inline-edit state + UI in the session list

---

## Task 1: Backend — rename route

**Files:**
- Modify: `backend/app/api/routes/chat.py`
- Create: `backend/app/tests/test_chat_api.py`

**Interfaces:**
- Produces: `PATCH /api/v1/chat/sessions/{session_id}` with body `{"title": str}` → `200` + `ChatSessionResponse` on success, `404` if the session doesn't exist or isn't owned by the caller, `422` if title is empty or over 255 chars.

- [ ] **Step 1: Ensure the local test Postgres is running**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/infra" && docker compose up -d postgres
```

- [ ] **Step 2: Write the test file**

Create `backend/app/tests/test_chat_api.py`:

```python
"""API integration tests for chat session rename."""


class TestRenameSession:
    def test_rename_session_updates_title(self, client, admin_headers):
        created = client.post(
            "/api/v1/chat/sessions", json={"title": "New Chat"}, headers=admin_headers
        )
        session_id = created.json()["id"]

        resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"title": "Renamed Chat"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed Chat"

    def test_rename_other_users_session_rejected(self, client, admin_headers, analyst_headers):
        created = client.post(
            "/api/v1/chat/sessions", json={"title": "Admin's chat"}, headers=admin_headers
        )
        session_id = created.json()["id"]

        resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"title": "Hijacked"},
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    def test_rename_empty_title_rejected(self, client, admin_headers):
        created = client.post(
            "/api/v1/chat/sessions", json={"title": "New Chat"}, headers=admin_headers
        )
        session_id = created.json()["id"]

        resp = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"title": ""},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_rename_nonexistent_session_returns_404(self, client, admin_headers):
        resp = client.patch(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000",
            json={"title": "Doesn't matter"},
            headers=admin_headers,
        )
        assert resp.status_code == 404
```

- [ ] **Step 3: Run the tests and confirm they fail (route doesn't exist yet)**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest app/tests/test_chat_api.py -v
```

Expected: all 4 tests **FAIL** with `405 Method Not Allowed` — no `PATCH /chat/sessions/{id}` route is registered yet, so every one of these requests hits Starlette's default "method not allowed on this path" response regardless of which session ID or body it used.

- [ ] **Step 4: Add the route**

In `backend/app/api/routes/chat.py`, change the import line:

```python
from pydantic import BaseModel
```

to:

```python
from pydantic import BaseModel, Field
```

Then add this class near `ChatSessionCreate` (after it):

```python
class ChatSessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)
```

Then add this route after `get_session` (and before `delete_session`, to keep the file's existing read-then-write-then-delete ordering):

```python
@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
def rename_session(
    session_id: uuid.UUID,
    body: ChatSessionRename,
    db: Session = Depends(get_db),
    user: User = Depends(get_tenant_user),
) -> ChatSessionResponse:
    svc = ChatService(db)
    session = svc.get_session(session_id, user)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    updated = svc.update_session_title(session, body.title)
    return _session_to_response(updated)
```

- [ ] **Step 5: Run the tests again — all pass**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest app/tests/test_chat_api.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Run the full backend suite as a regression check**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/backend" && uv run pytest -q
```

Expected: `264 passed` (the 260-test baseline plus the 4 new tests).

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add backend/app/api/routes/chat.py backend/app/tests/test_chat_api.py
git commit -m "Add PATCH /chat/sessions/{id} route to rename a chat session"
```

---

## Task 2: Frontend — inline rename in the session list

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

**Interfaces:**
- Consumes: `PATCH /api/v1/chat/sessions/{session_id}` from Task 1.

- [ ] **Step 1: Add the mutation and edit state**

In `frontend/app/(dashboard)/chat/page.tsx`, right after the existing `deleteSession` mutation (which ends with its closing `});`), add:

```tsx
  const renameSession = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch(`/chat/sessions/${id}`, { title }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-sessions"] }),
  });
```

And add this state near the top of the component, right after the existing `const [question, setQuestion] = useState("");` line:

```tsx
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
```

- [ ] **Step 2: Add the start/commit/cancel handlers**

Add these functions right after `handleSend` (after its closing `}`):

```tsx
  function startEditingSession(s: ChatSession) {
    setEditingSessionId(s.id);
    setEditTitle(s.title);
  }

  function commitSessionRename() {
    const title = editTitle.trim();
    if (editingSessionId && title) {
      renameSession.mutate({ id: editingSessionId, title });
    }
    setEditingSessionId(null);
  }
```

- [ ] **Step 3: Replace the session title rendering**

Find this block in the session list (`<ul className="flex-1 overflow-y-auto p-2 space-y-1">`):

```tsx
                  <span className="truncate">{s.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete session?")) deleteSession.mutate(s.id);
                    }}
                    className="hidden group-hover:block shrink-0"
                  >
                    <X className="h-3 w-3 text-slate-400" />
                  </button>
```

Replace it with:

```tsx
                  {editingSessionId === s.id ? (
                    <input
                      autoFocus
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onDoubleClick={(e) => e.stopPropagation()}
                      onBlur={commitSessionRename}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitSessionRename();
                        if (e.key === "Escape") setEditingSessionId(null);
                      }}
                      className="min-w-0 flex-1 rounded border border-slate-300 bg-white px-1 text-sm text-slate-900"
                    />
                  ) : (
                    <span
                      className="truncate"
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        startEditingSession(s);
                      }}
                    >
                      {s.title}
                    </span>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete session?")) deleteSession.mutate(s.id);
                    }}
                    className="hidden group-hover:block shrink-0"
                  >
                    <X className="h-3 w-3 text-slate-400" />
                  </button>
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd "/home/lenovo/Own Projects/AegisRAG/frontend" && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 5: Commit and push**

```bash
cd "/home/lenovo/Own Projects/AegisRAG" && git add "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "Add inline chat session rename (double-click the title)"
git push origin main
```

- [ ] **Step 6: Manually verify against the live deployment**

Once Railway's deploy finishes:
1. Open `/chat`, double-click an existing session's title in the sidebar → confirm it turns into an editable input, pre-filled with the current title.
2. Type a new title, press Enter → confirm the sidebar updates to the new title immediately.
3. Double-click another session's title, change it, click elsewhere (blur) instead of pressing Enter → confirm it still saves.
4. Double-click a title, change it, press Escape → confirm it reverts to the original title (no save).
5. Double-click a title, clear it entirely, press Enter → confirm it does *not* save an empty title (title stays as it was).
6. Click into the rename input, then click elsewhere inside the input — confirm this does not switch which session is active (i.e., clicking inside the input doesn't trigger the parent `<button>`'s session-switch `onClick`).
