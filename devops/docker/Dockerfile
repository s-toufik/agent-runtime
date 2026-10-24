FROM python:3.14-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY Readme.md ./

RUN uv sync --no-dev --no-editable --frozen --extra fastapi --extra litestar

FROM python:3.14-slim

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY config ./config
RUN cp -r config/debug config/deploy

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    CONFIGURATION_DIR="/app/config" \
    GRANIAN_INTERFACE=asgi \
    GRANIAN_FACTORY=true \
    GRANIAN_HOST=0.0.0.0 \
    GRANIAN_PORT=8000 \
    GRANIAN_LOG_ACCESS_ENABLED=true \
    GRANIAN_LOG_ACCESS_FMT="%(addr)s %(method)s %(path)s %(status)d %(dt_ms).1fms"

RUN mkdir -p /data/sqlite && chown -R app:app /data

USER app
EXPOSE 8000

CMD ["granian", "bootstrap.application.agent_application:create_agent_application"]
