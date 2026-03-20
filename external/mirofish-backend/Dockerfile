FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY app/ app/
COPY run.py .
COPY scripts/ scripts/

EXPOSE 5001

CMD ["uv", "run", "python", "run.py"]
