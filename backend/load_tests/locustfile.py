"""Locust load test for AegisRAG.

Run with:
    locust -f load_tests/locustfile.py --host http://localhost:8000
    locust -f load_tests/locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 --run-time 5m
"""
from __future__ import annotations

import os
import random

from locust import HttpUser, between, events, task

BASE_EMAIL = os.getenv("LOAD_TEST_EMAIL", "loadtest@example.com")
BASE_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "LoadTest123!")

SAMPLE_QUESTIONS = [
    "What is the data retention policy?",
    "How do I classify a confidential document?",
    "What security controls are in place for restricted data?",
    "Summarize the compliance requirements for internal documents.",
    "What is the process for requesting access to restricted materials?",
    "Describe the audit logging capabilities.",
    "What encryption is used for data at rest?",
    "How are prompt injection attempts handled?",
    "What are the supported document formats for ingestion?",
    "Explain the hybrid retrieval mechanism.",
]

SAMPLE_DOCS = [
    ("test_document.txt", b"This is a test document for load testing. It contains sample text about security policies and data governance procedures in enterprise environments.", "text/plain"),
]


class RAGUser(HttpUser):
    wait_time = between(1, 3)
    token: str = ""

    def on_start(self) -> None:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": BASE_EMAIL, "password": BASE_PASSWORD},
            name="/auth/login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(6)
    def rag_query(self) -> None:
        question = random.choice(SAMPLE_QUESTIONS)
        self.client.post(
            "/api/v1/rag/query",
            json={"question": question, "top_k": 5},
            headers=self._headers(),
            name="/rag/query",
        )

    @task(2)
    def rag_query_stream(self) -> None:
        question = random.choice(SAMPLE_QUESTIONS)
        with self.client.post(
            "/api/v1/rag/query-stream",
            json={"question": question, "top_k": 5},
            headers=self._headers(),
            stream=True,
            name="/rag/query-stream",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                for _ in resp.iter_content(chunk_size=None):
                    pass
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(1)
    def upload_document(self) -> None:
        filename, content, mime = random.choice(SAMPLE_DOCS)
        self.client.post(
            "/api/v1/documents/upload",
            files={"file": (filename, content, mime)},
            data={"classification": "internal"},
            headers=self._headers(),
            name="/documents/upload",
        )

    @task(1)
    def list_documents(self) -> None:
        self.client.get(
            "/api/v1/documents/",
            headers=self._headers(),
            name="/documents/list",
        )


@events.quitting.add_listener
def print_percentile_stats(environment, **kwargs):
    """Print p50/p95/p99 summary on exit."""
    stats = environment.runner.stats
    for name, entry in stats.entries.items():
        if entry.num_requests > 0:
            print(
                f"{name}: "
                f"p50={entry.get_response_time_percentile(0.5):.0f}ms "
                f"p95={entry.get_response_time_percentile(0.95):.0f}ms "
                f"p99={entry.get_response_time_percentile(0.99):.0f}ms "
                f"rps={entry.current_rps:.1f} "
                f"failures={entry.num_failures}"
            )
