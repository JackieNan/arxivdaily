FROM python:3.12-slim

ARG DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
ARG DEBIAN_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ARXIV_DAILY_DATABASE=/data/arxiv-local-daily.sqlite3
ENV ARXIV_DAILY_LLM_CONFIG=/config/llm.local.json
ENV ARXIV_DAILY_SUMMARY_TEMPLATE_CONFIG=/config/summary_template.local.json

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i \
            -e "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" \
            -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
            -e "s|http://security.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
            /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i \
            -e "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" \
            -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
            -e "s|http://security.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
            /etc/apt/sources.list; \
    fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" .
RUN mkdir -p /data /config /backups

EXPOSE 8765

CMD ["uvicorn", "arxiv_local_daily.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
