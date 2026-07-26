FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN useradd --create-home --shell /usr/sbin/nologin bot

WORKDIR /app

# Install dependencies first for layer caching: only pyproject.toml + uv.lock
# invalidate this layer, not application code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY bot/ ./bot/

ENV PATH="/app/.venv/bin:$PATH"

USER bot
CMD ["python", "-m", "bot.main"]
