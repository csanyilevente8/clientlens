# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install uv (matches local tooling; reproducible installs from uv.lock)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependency layer: copy manifests first for better build caching
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

# Generate throwaway DEV JWT keys inside the image (real keys are injected via secrets in
# production — see keys/README.md / ADR-009). openssl ships in the slim image's base.
RUN mkdir -p keys \
    && openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out keys/jwt_private_dev.pem \
    && openssl rsa -pubout -in keys/jwt_private_dev.pem -out keys/jwt_public_dev.pem

# Application code
COPY app ./app

EXPOSE 8000

# uv run ensures the project venv is used
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
