# layer-mcp-github-v1: MCP streamable-http on port 8000.
FROM public.ecr.aws/docker/library/python:3.11-slim

ARG APP_VERSION=dev
ARG GIT_SHA=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_TIME=unknown
ARG BUILD_IMAGE=unknown
ARG IMAGE_DIGEST=unknown

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA} \
    GIT_BRANCH=${GIT_BRANCH} \
    BUILD_TIME=${BUILD_TIME} \
    BUILD_IMAGE=${BUILD_IMAGE} \
    IMAGE_DIGEST=${IMAGE_DIGEST} \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8000

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir ".[cursor]"

RUN useradd --create-home --shell /usr/sbin/nologin --uid 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-m", "app.main", "--http"]
