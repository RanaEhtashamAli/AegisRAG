FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install runtime dependencies into a virtual environment using the lockfile
RUN uv sync --frozen --no-dev

# Copy application source (subdirectories only so volume mounts don't overwrite .venv)
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini
COPY evals/ ./evals/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
