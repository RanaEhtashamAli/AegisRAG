"""Unit tests for ModelRouter provider selection logic."""
from unittest.mock import MagicMock, patch

from app.services.inference.base_provider import InferenceRequest
from app.services.model_router import ModelRouter, _estimate_tokens

# ── Token estimation ──────────────────────────────────────────────────────────

def test_estimate_tokens_empty():
    assert _estimate_tokens("") == 1  # max(1, 0)


def test_estimate_tokens_rough_ratio():
    # ~4 chars per token
    text = "a" * 400
    assert _estimate_tokens(text) == 100


def test_estimate_tokens_scales_with_length():
    assert _estimate_tokens("x" * 1000) > _estimate_tokens("x" * 100)


# ── Provider selection ────────────────────────────────────────────────────────

class TestProviderSelection:
    """All provider-selection tests mock out the actual HTTP providers."""

    def _make_router(self, vllm_enabled: bool = False):
        with (
            patch("app.services.model_router.OllamaProvider") as mock_ollama,
            patch("app.services.model_router.VLLMProvider") as mock_vllm,
            patch("app.services.model_router.settings") as mock_settings,
        ):
            mock_settings.VLLM_ENABLED = vllm_enabled
            mock_settings.OLLAMA_MODEL = "llama3.1:8b"
            mock_settings.VLLM_MODEL = "mistral-7b"
            mock_settings.COMPLEX_QUERY_TOKEN_THRESHOLD = 500

            ollama_instance = MagicMock()
            ollama_instance.provider_name = "ollama"
            vllm_instance = MagicMock()
            vllm_instance.provider_name = "vllm"

            mock_ollama.return_value = ollama_instance
            mock_vllm.return_value = vllm_instance

            router = ModelRouter()
            return router, ollama_instance, vllm_instance

    def test_restricted_always_uses_ollama(self):
        router, ollama, vllm = self._make_router(vllm_enabled=True)
        provider, model = router._select_provider("some prompt", classification="restricted")
        assert provider is ollama

    def test_vllm_disabled_always_uses_ollama(self):
        router, ollama, vllm = self._make_router(vllm_enabled=False)
        provider, model = router._select_provider("some prompt", classification="internal")
        assert provider is ollama

    def test_vllm_enabled_non_restricted_uses_vllm(self):
        router, ollama, vllm = self._make_router(vllm_enabled=True)
        provider, model = router._select_provider("short query", classification="public")
        assert provider is vllm

    def test_restricted_overrides_vllm_enabled(self):
        """Even when vLLM is enabled, restricted docs must go to Ollama."""
        router, ollama, vllm = self._make_router(vllm_enabled=True)
        provider, _ = router._select_provider(
            "query about restricted content",
            classification="restricted",
        )
        assert provider is ollama
        assert provider is not vllm

    def test_none_classification_uses_vllm_when_enabled(self):
        router, ollama, vllm = self._make_router(vllm_enabled=True)
        provider, _ = router._select_provider("query", classification=None)
        assert provider is vllm


# ── build_request ─────────────────────────────────────────────────────────────

class TestBuildRequest:
    def _make_router(self):
        with (
            patch("app.services.model_router.OllamaProvider") as mock_ollama,
            patch("app.services.model_router.VLLMProvider"),
            patch("app.services.model_router.settings") as mock_settings,
        ):
            mock_settings.VLLM_ENABLED = False
            mock_settings.OLLAMA_MODEL = "llama3.1:8b"
            mock_settings.VLLM_MODEL = "mistral-7b"
            mock_settings.COMPLEX_QUERY_TOKEN_THRESHOLD = 500

            ollama_instance = MagicMock()
            mock_ollama.return_value = ollama_instance

            return ModelRouter(), ollama_instance

    def test_build_request_returns_provider_and_request(self):
        router, _ = self._make_router()
        provider, req = router.build_request(
            question="What is the policy?",
            context_chunks=["chunk one", "chunk two"],
        )
        assert provider is not None
        assert isinstance(req, InferenceRequest)

    def test_build_request_includes_question_in_prompt(self):
        router, _ = self._make_router()
        _, req = router.build_request(
            question="What is the data retention policy?",
            context_chunks=["Retention is 90 days."],
        )
        assert "data retention policy" in req.prompt

    def test_build_request_includes_context_in_prompt(self):
        router, _ = self._make_router()
        _, req = router.build_request(
            question="What is X?",
            context_chunks=["X is a special concept.", "Related information here."],
        )
        assert "X is a special concept" in req.prompt
        assert "Related information here" in req.prompt

    def test_build_request_includes_history_prefix(self):
        router, _ = self._make_router()
        _, req = router.build_request(
            question="Follow up?",
            context_chunks=["context"],
            history_prefix="User: previous\nAssistant: answer",
        )
        assert "previous" in req.prompt

    def test_build_request_no_history_when_empty(self):
        router, _ = self._make_router()
        _, req = router.build_request(
            question="Simple question?",
            context_chunks=["context"],
            history_prefix="",
        )
        assert "Previous conversation" not in req.prompt

    def test_build_request_numbers_context_chunks(self):
        router, _ = self._make_router()
        _, req = router.build_request(
            question="Q?",
            context_chunks=["first chunk", "second chunk"],
        )
        assert "[1]" in req.prompt
        assert "[2]" in req.prompt

    def test_build_request_sets_model(self):
        router, _ = self._make_router()
        _, req = router.build_request(question="Q?", context_chunks=[])
        assert req.model != ""
