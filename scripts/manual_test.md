# AegisRAG Manual API Test Guide

All commands assume the backend is running on `http://localhost:8000`.  
Set `BASE=http://localhost:8000/api/v1` in your shell for brevity.

```bash
BASE=http://localhost:8000/api/v1
```

---

## Phase 1 Flows

### 1. Health check
```bash
curl $BASE/health
```

---

### 2. Register admin user
```bash
curl -s -X POST $BASE/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"adminpass123","full_name":"Admin User"}' | jq
```

---

### 3. Login and capture token
```bash
ADMIN_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"adminpass123"}' \
  | jq -r '.access_token')
echo "ADMIN_TOKEN=$ADMIN_TOKEN"
```

---

### 4. Create tenant
After creation, the user's role is automatically set to `tenant_admin`.
```bash
curl -s -X POST $BASE/tenants \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp","slug":"acme"}' | jq
```

---

### 5. Verify role is tenant_admin
```bash
curl -s $BASE/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.role'
# Should print: "tenant_admin"
```

---

## Phase 2 Flows

### 6. Invite an analyst
Token is returned in the response — there is no email in Phase 2.
```bash
INVITE_RESPONSE=$(curl -s -X POST $BASE/users/invite \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@acme.com","full_name":"Data Analyst","role":"analyst"}')

INVITE_TOKEN=$(echo $INVITE_RESPONSE | jq -r '.invite_token')
echo "INVITE_TOKEN=$INVITE_TOKEN"
```

---

### 7. Accept invite (as the invited user)
```bash
curl -s -X POST $BASE/users/accept-invite \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$INVITE_TOKEN\",\"password\":\"analystpass123\",\"full_name\":\"Data Analyst\"}" | jq
```

---

### 8. Login as analyst
```bash
ANALYST_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@acme.com","password":"analystpass123"}' \
  | jq -r '.access_token')
```

---

### 9. Invite a viewer
```bash
VIEWER_INVITE=$(curl -s -X POST $BASE/users/invite \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@acme.com","role":"viewer"}')

VIEWER_INVITE_TOKEN=$(echo $VIEWER_INVITE | jq -r '.invite_token')

curl -s -X POST $BASE/users/accept-invite \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$VIEWER_INVITE_TOKEN\",\"password\":\"viewerpass123\"}" | jq

VIEWER_TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@acme.com","password":"viewerpass123"}' \
  | jq -r '.access_token')
```

---

### 10. Upload a PDF as admin (internal classification)
```bash
DOC_RESPONSE=$(curl -s -X POST $BASE/documents/upload \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "classification=internal")

DOC_ID=$(echo $DOC_RESPONSE | jq -r '.id')
echo "DOC_ID=$DOC_ID"
```

---

### 11. Upload a restricted document as admin
```bash
RESTRICTED_DOC=$(curl -s -X POST $BASE/documents/upload \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/path/to/sensitive.pdf" \
  -F "classification=restricted")

RESTRICTED_ID=$(echo $RESTRICTED_DOC | jq -r '.id')
```

---

### 12. Verify viewer CANNOT upload documents
```bash
curl -s -X POST $BASE/documents/upload \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "classification=internal"
# Expected: 403 Forbidden
```

---

### 13. Check document status (wait for indexed)
```bash
curl -s $BASE/documents/$DOC_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.status'
```

---

### 14. Update classification to confidential
```bash
curl -s -X PATCH $BASE/documents/$DOC_ID/classification \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"classification":"confidential"}' | jq
```

---

### 15. Verify viewer cannot see confidential documents
```bash
curl -s $BASE/documents \
  -H "Authorization: Bearer $VIEWER_TOKEN" | jq
# Should return empty list or only public/internal docs
```

---

### 16. Verify analyst CANNOT see restricted documents from others
```bash
curl -s $BASE/documents/$RESTRICTED_ID \
  -H "Authorization: Bearer $ANALYST_TOKEN" | jq
# Expected: 403 Forbidden
```

---

### 17. RAG query as admin (sees all classifications)
```bash
curl -s -X POST $BASE/rag/query \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the main findings?","top_k":5}' | jq
```

---

### 18. RAG query as viewer (only public/internal chunks returned)
```bash
curl -s -X POST $BASE/rag/query \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the main findings?","top_k":5}' | jq
```

---

### 19. View audit logs as admin
```bash
curl -s "$BASE/audit/events?limit=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

Filter by event type:
```bash
curl -s "$BASE/audit/events?event_type=rag.query&limit=10" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

---

### 20. Verify viewer CANNOT view audit logs
```bash
curl -s "$BASE/audit/events" \
  -H "Authorization: Bearer $VIEWER_TOKEN"
# Expected: 403 Forbidden
```

---

### 21. View PII findings (admin/compliance officer only)
```bash
curl -s $BASE/documents/$DOC_ID/pii-findings \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

---

### 22. Delete a document (admin only)
```bash
curl -s -X DELETE $BASE/documents/$RESTRICTED_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Expected: 204 No Content
```

---

### 23. Reindex a document (admin/compliance officer)
```bash
curl -s -X POST $BASE/documents/$DOC_ID/reindex \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

---

### 24. Update a user's role (admin only)
```bash
ANALYST_ID=$(curl -s $BASE/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | jq -r '.[] | select(.email=="analyst@acme.com") | .id')

curl -s -X PATCH $BASE/users/$ANALYST_ID/role \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"compliance_officer"}' | jq
```

---

### 25. Deactivate a user (admin only)
```bash
curl -s -X DELETE $BASE/users/$ANALYST_ID \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Expected: 204 No Content
```
