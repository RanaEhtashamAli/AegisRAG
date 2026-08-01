#!/usr/bin/env python3
"""
Run RAGAS evaluation against a set of golden questions.

Usage:
    cd backend
    uv run python evals/run_ragas_eval.py \
        --questions evals/golden_questions/sample.json \
        --tenant-token <JWT> \
        --output evals/reports/run_001.json

Scoring uses a self-hosted judge (Ollama via its OpenAI-compatible API, plus the
same local sentence-transformers embedding model the app already uses) — no
OpenAI API key required. Override --judge-base-url / --judge-model if you want
to point at a different Ollama instance or model than the app's own defaults.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx

# Running this script directly (`python evals/run_ragas_eval.py`) puts only
# evals/ on sys.path, not backend/ — insert it so `app.*` imports resolve
# regardless of whether this is run as a script or as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402


def load_questions(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def query_rag(base_url: str, token: str, question: str, top_k: int = 5) -> dict:
    resp = httpx.post(
        f"{base_url}/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": question, "top_k": top_k},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def run_ragas(
    questions: list[dict],
    answers: list[dict],
    judge_base_url: str,
    judge_model: str,
) -> dict:
    try:
        from datasets import Dataset
        from openai import OpenAI
        from ragas import evaluate
        from ragas.embeddings import HuggingFaceEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError:
        print(
            "ragas not installed. Run: uv add --group dev ragas langchain-community datasets",
            file=sys.stderr,
        )
        sys.exit(1)

    # Self-hosted judge: Ollama's OpenAI-compatible endpoint, no OpenAI key needed.
    # api_key is a dummy value — Ollama doesn't check it, but the OpenAI client requires one.
    judge_client = OpenAI(base_url=judge_base_url, api_key="ollama")
    judge_llm = llm_factory(judge_model, client=judge_client)
    judge_embeddings = HuggingFaceEmbeddings(model=settings.EMBEDDING_MODEL)

    data: dict[str, list] = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for q, a in zip(questions, answers):
        data["question"].append(q["question"])
        data["answer"].append(a.get("answer", ""))
        data["contexts"].append(
            [s.get("text_preview", "") for s in a.get("sources", [])]
        )
        data["ground_truth"].append(q.get("ground_truth", ""))

    dataset = Dataset.from_dict(data)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation on AegisRAG")
    parser.add_argument("--questions", required=True, help="Path to golden questions JSON")
    parser.add_argument("--tenant-token", required=True, help="Bearer JWT for an authenticated user")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", required=True, help="Path to write JSON report")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--judge-base-url",
        default=f"{settings.OLLAMA_BASE_URL}/v1",
        help="OpenAI-compatible base URL for the judge LLM (defaults to the app's own Ollama)",
    )
    parser.add_argument(
        "--judge-model",
        default=settings.OLLAMA_MODEL,
        help="Model name for the judge LLM (defaults to the app's own OLLAMA_MODEL)",
    )
    args = parser.parse_args()

    questions = load_questions(args.questions)
    print(f"Loaded {len(questions)} questions from {args.questions}")

    answers = []
    for i, q in enumerate(questions):
        print(f"  [{i + 1}/{len(questions)}] {q['question'][:60]}")
        try:
            result = query_rag(args.base_url, args.tenant_token, q["question"], args.top_k)
            answers.append(result)
        except Exception as e:
            print(f"    ERROR: {e}")
            answers.append({"answer": "", "sources": []})
        time.sleep(0.5)

    print(f"\nRunning RAGAS evaluation (judge: {args.judge_model} @ {args.judge_base_url})…")
    scores = run_ragas(questions, answers, args.judge_base_url, args.judge_model)

    report = {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "total_questions": len(questions),
        "scores": {
            "faithfulness": float(scores.get("faithfulness", 0)),
            "answer_relevancy": float(scores.get("answer_relevancy", 0)),
            "context_recall": float(scores.get("context_recall", 0)),
            "context_precision": float(scores.get("context_precision", 0)),
        },
        "per_question": [
            {
                "question": q["question"],
                "answer": a.get("answer", "")[:500],
                "num_sources": len(a.get("sources", [])),
            }
            for q, a in zip(questions, answers)
        ],
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nResults saved to {args.output}")
    print(f"Faithfulness:      {report['scores']['faithfulness']:.3f}")
    print(f"Answer Relevancy:  {report['scores']['answer_relevancy']:.3f}")
    print(f"Context Recall:    {report['scores']['context_recall']:.3f}")
    print(f"Context Precision: {report['scores']['context_precision']:.3f}")


if __name__ == "__main__":
    main()
