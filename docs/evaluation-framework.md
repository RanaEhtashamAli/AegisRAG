# Evaluation Framework

## Overview

AegisRAG Phase 3 includes a RAGAS-based offline evaluation pipeline for measuring RAG answer quality against a golden question set.

---

## Metrics

| Metric | Description | Range |
|---|---|---|
| **Faithfulness** | Does the answer stay within the retrieved context? | 0–1 |
| **Answer Relevancy** | Is the answer relevant to the question? | 0–1 |
| **Context Recall** | Does the retrieved context cover the ground truth? | 0–1 |
| **Context Precision** | Is the retrieved context precise (low noise)? | 0–1 |

---

## Running an Evaluation

### 1. Prepare golden questions

Edit `backend/evals/golden_questions/sample.json`:

```json
[
  {
    "question": "What is the quarterly revenue?",
    "ground_truth": "Q3 revenue was $4.2M, up 12% YoY.",
    "contexts": []
  }
]
```

`contexts` is optional — RAGAS can derive context coverage from retrieved chunks.

### 2. Get a user token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@acme.com","password":"adminpass123"}' \
  | jq -r '.access_token')
```

### 3. Run the script

```bash
cd backend
uv run python evals/run_ragas_eval.py \
  --questions evals/golden_questions/sample.json \
  --tenant-token "$TOKEN" \
  --output evals/reports/run_001.json
```

### 4. View results

Results are written to `evals/reports/run_001.json` and printed to stdout:

```
Faithfulness:      0.891
Answer Relevancy:  0.934
Context Recall:    0.762
Context Precision: 0.811
```

---

## EvaluationRun Model

The `evaluation_runs` table stores run metadata and scores for display in the Evals dashboard (`/dashboard/evals`). To populate it, insert records after running the script — or integrate the script to POST to a future `/api/v1/evals/runs` write endpoint.

---

## Dependencies

RAGAS and its dependencies are in the `dev` dependency group (not installed in production):

```bash
uv sync --group dev
```

Required: `ragas`, `langchain-community`, `datasets`, plus an OpenAI key (RAGAS uses an LLM judge internally for some metrics). Set `OPENAI_API_KEY` in your shell before running.

---

## Known Limitations

- RAGAS metrics that use an LLM judge (faithfulness, answer relevancy) require an OpenAI API key unless a custom LLM judge is configured
- The golden question file must be maintained manually
- Cross-document evaluation (comparing retrieval across classification levels) requires separate runs per user role
