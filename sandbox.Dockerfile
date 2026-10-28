# Minimal image Exhibit A uses to run a target's tests in isolation.
# Build once:  docker build -t exhibit-a-sandbox:latest -f sandbox.Dockerfile .
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest flask fastapi httpx requests
# The agent runs containers with --network none, read-only deps, dropped caps.
WORKDIR /work
