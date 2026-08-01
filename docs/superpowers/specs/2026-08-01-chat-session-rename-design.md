# Chat Session Rename — Design

## Problem

Every chat session is created with the fixed title `"New Chat"` (`frontend/app/(dashboard)/chat/page.tsx`'s `createSession` mutation posts `{ title: "New Chat" }`, and `ChatService.create_session`'s default matches). There's no way to rename a session afterward, so the session list in the chat page's sidebar becomes a wall of identical, indistinguishable "New Chat" entries as soon as a user has more than one.

The backend already has half of this built: `ChatService.update_session_title(session, title)` (`backend/app/services/chat_service.py`) exists and works, but no route in `backend/app/api/routes/chat.py` calls it — it's dead code today.

## Goals

- Let a user rename any of their own chat sessions from the chat page's session list.
- Reuse the existing `update_session_title` service method — just wire it to a route.
- Match the existing inline-mutation pattern already used in `chat/page.tsx` for create/delete (no new service file).

## Non-goals

- Renaming from anywhere other than the chat page's session list (e.g., no rename option elsewhere in the app — there isn't anywhere else sessions are listed).
- Auto-generating a title from the first message — out of scope, purely manual rename for this pass.

## Backend changes

**`backend/app/api/routes/chat.py`** — add:

```python
class ChatSessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)


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

Requires adding `Field` to the existing `from pydantic import BaseModel` import. Ownership/tenant scoping is enforced the same way every other session route already does it — via `ChatService.get_session(session_id, user)`, which filters on both `tenant_id` and `user_id` (`backend/app/services/chat_service.py:38-45`). `update_session_title` (`chat_service.py:76-79`) already truncates to 255 chars server-side; the new `Field(max_length=255)` makes that limit explicit at the API boundary too, and `min_length=1` rejects an empty rename (the frontend also blocks this — see below — so this is defense in depth, not the only guard).

## Frontend changes

**`frontend/app/(dashboard)/chat/page.tsx`** — add local state and a mutation, modeled directly on the existing `deleteSession` mutation in the same file:

```tsx
const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
const [editTitle, setEditTitle] = useState("");

const renameSession = useMutation({
  mutationFn: ({ id, title }: { id: string; title: string }) =>
    api.patch(`/chat/sessions/${id}`, { title }),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["chat-sessions"] }),
});

function startEditing(s: ChatSession) {
  setEditingSessionId(s.id);
  setEditTitle(s.title);
}

function commitEdit() {
  const title = editTitle.trim();
  if (editingSessionId && title) {
    renameSession.mutate({ id: editingSessionId, title });
  }
  setEditingSessionId(null);
}
```

In the session list item, the existing `<span className="truncate">{s.title}</span>` becomes conditional: when `editingSessionId === s.id`, render an autofocused `<input>` bound to `editTitle` instead, styled to fit inline in the same row. `onDoubleClick` on the title span starts editing; the input commits on Enter or blur (`commitEdit`), and cancels on Escape (`setEditingSessionId(null)` without mutating). The input's own click/double-click events call `stopPropagation()` so interacting with it doesn't also trigger the parent button's `onClick` (which switches the active session).

## Error handling

- Empty/whitespace-only title: blocked client-side in `commitEdit` (never sent) — matches the backend's `min_length=1`, which exists as defense in depth, not the primary guard the user interacts with.
- Rename on a session that's been deleted by another tab/device in the meantime: backend returns `404`; the mutation has no explicit error UI for this edge case — `onSuccess` simply won't fire and the input reverts to showing the (now stale) old title on next render. Acceptable for this pass; not worth a toast/error banner for a single-user hobby app.

## Testing

- **Backend**: extend `backend/app/tests/` with a new test (in a session-scoped test file, following the existing `client`/`admin_headers` fixture pattern already used throughout) covering: successful rename (200, title updated), renaming another tenant's/user's session (404), empty title (422).
- **Frontend**: no test framework in this repo (consistent with every other frontend change this session) — verify manually against the local dev server: double-click a title, edit, confirm Enter saves and the sidebar updates; confirm Escape cancels without saving; confirm clicking into the input doesn't switch the active session.
