# Build context: repository root (needs backend/, connectors/ and workflow-engine/)
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY backend/ /app/
COPY connectors/ /opt/middly/connectors/
COPY workflow-engine/ /opt/middly/workflow-engine/

ENV CONNECTORS_PATH=/opt/middly/connectors \
    WORKFLOW_CONFIG_PATH=/opt/middly/workflow-engine \
    PYTHONPATH=/app

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && chmod +x /app/entrypoint.sh
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["api"]
