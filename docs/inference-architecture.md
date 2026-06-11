# Inference Architecture

## Provider Abstraction

AegisRAG uses a provider abstraction layer (`BaseInferenceProvider`) so inference backends are interchangeable. The routing decision happens in `ModelRouter`.

```
User query
    └─► ModelRouter._select_provider(prompt, classification)
            ├─ classification == "restricted" → OllamaProvider (local only)
            ├─ VLLM_ENABLED=false → OllamaProvider
            └─ otherwise → VLLMProvider (fast path)
```

## OllamaProvider

- Endpoint: `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- Model: `OLLAMA_MODEL` (default: `llama3.1:8b`)
- Protocol: POST `/api/generate` (non-streaming) / streaming via `aiter_lines()`
- Retry: 3 attempts with tenacity `@retry`

Ollama is the mandatory local fallback. It is **always** used for restricted-classification content — sensitive data never leaves the local inference node.

## VLLMProvider

- Endpoint: `VLLM_BASE_URL` (default: `http://localhost:8080`)
- Model: `VLLM_MODEL` (default: `mistralai/Mistral-7B-Instruct-v0.3`)
- Protocol: OpenAI-compatible `/v1/chat/completions`
- Enable: set `VLLM_ENABLED=true`
- Retry: 3 attempts with tenacity `@retry`

vLLM serves as the fast-path provider for non-restricted queries. It runs on GPU and delivers significantly higher throughput than CPU-bound Ollama.

## Routing Logic

1. **Restricted content** → always Ollama, regardless of vLLM availability
2. **vLLM disabled** → always Ollama
3. **Complex query** (token count > `COMPLEX_QUERY_TOKEN_THRESHOLD`, default 500) → vLLM strong model
4. **Default** → vLLM fast model

Token count is estimated as `len(text) // 4` (rough 4-chars-per-token heuristic). For production, replace with a proper tokenizer count if accuracy matters.

## Adding a New Provider

1. Create `backend/app/services/inference/your_provider.py`
2. Implement `BaseInferenceProvider`: `generate()`, `generate_stream()`, `health_check()`, `default_model()`
3. Add routing logic in `ModelRouter._select_provider()`
4. Add config vars in `Settings`

## Streaming

The `query_stream` endpoint returns server-sent events:

```
data: {"type": "sources", "sources": [...]}
data: {"type": "token", "content": "Hello"}
data: {"type": "token", "content": " world"}
data: {"type": "done"}
```

The frontend `streamQuery()` in `frontend/services/rag.ts` parses these events using the browser's `ReadableStream` API.

## Kubernetes Deployment

vLLM requires a GPU node. The `infra/k8s/base/vllm.yaml` manifest requests `nvidia.com/gpu: 1`. Set up the NVIDIA device plugin before deploying:

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.16.0/deployments/static/nvidia-device-plugin.yml
```
