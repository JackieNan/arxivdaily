FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ARXIV_DAILY_DATABASE=/data/arxiv-local-daily.sqlite3
ENV ARXIV_DAILY_LLM_CONFIG=/config/llm.local.json
ENV ARXIV_DAILY_SUMMARY_TEMPLATE_CONFIG=/config/summary_template.local.json

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .
RUN mkdir -p /data /config /backups

EXPOSE 8765

CMD ["uvicorn", "arxiv_local_daily.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
