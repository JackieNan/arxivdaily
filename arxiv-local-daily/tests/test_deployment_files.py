from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]


def read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text()


def test_dockerfile_runs_uvicorn_with_internal_bind_and_mounted_config_defaults() -> None:
    dockerfile = read_project_file("Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "ENV ARXIV_DAILY_DATABASE=/data/arxiv-local-daily.sqlite3" in dockerfile
    assert "ARXIV_DAILY_LLM_CONFIG=/config/llm.local.json" in dockerfile
    assert "ARXIV_DAILY_SUMMARY_TEMPLATE_CONFIG=/config/summary_template.local.json" in dockerfile
    assert "COPY pyproject.toml README.md ./" in dockerfile
    assert "COPY src ./src" in dockerfile
    assert "EXPOSE 8765" in dockerfile
    assert 'CMD ["uvicorn", "arxiv_local_daily.api:create_app", "--factory"' in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert '"--port", "8765"' in dockerfile


def test_dockerfile_supports_domestic_debian_apt_mirrors() -> None:
    dockerfile = read_project_file("Dockerfile")

    assert "ARG DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian" in dockerfile
    assert "ARG DEBIAN_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security" in dockerfile
    assert "deb.debian.org/debian" in dockerfile
    assert "${DEBIAN_MIRROR}" in dockerfile
    assert "${DEBIAN_SECURITY_MIRROR}" in dockerfile
    assert "/etc/apt/sources.list.d/debian.sources" in dockerfile


def test_dockerfile_supports_domestic_pip_index() -> None:
    dockerfile = read_project_file("Dockerfile")

    assert "ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple" in dockerfile
    assert 'python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" .' in dockerfile


def test_compose_uses_cloudflare_tunnel_without_publishing_app_port() -> None:
    compose = read_project_file("docker-compose.yml")
    app_section = compose.split("\n  cloudflared:", 1)[0]

    assert "services:" in compose
    assert "\n  app:" in compose
    assert "\n  cloudflared:" in compose
    assert "DEBIAN_MIRROR: ${DEBIAN_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/debian}" in app_section
    assert (
        "DEBIAN_SECURITY_MIRROR: ${DEBIAN_SECURITY_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/debian-security}"
        in app_section
    )
    assert "PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" in app_section
    assert "\n    ports:" not in app_section
    assert "ARXIV_DAILY_DATABASE: /data/arxiv-local-daily.sqlite3" in app_section
    assert "ARXIV_DAILY_LLM_CONFIG: /config/llm.local.json" in app_section
    assert "ARXIV_DAILY_SUMMARY_TEMPLATE_CONFIG: /config/summary_template.local.json" in app_section
    assert "./data:/data" in app_section
    assert "./config:/config:ro" in app_section
    assert "cloudflare/cloudflared" in compose
    assert 'tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}' in compose
    assert "depends_on:" in compose
    assert "- app" in compose


def test_cloudflared_named_tunnel_template_routes_to_app_service() -> None:
    config_template = read_project_file("deploy/cloudflared/config.example.yml")

    assert "tunnel:" in config_template
    assert "credentials-file:" in config_template
    assert "ingress:" in config_template
    assert "hostname: papers.example.com" in config_template
    assert "service: http://app:8765" in config_template
    assert "service: http_status:404" in config_template


def test_env_example_and_deployment_docs_cover_required_cloudflare_steps() -> None:
    env_example = read_project_file(".env.example")
    docs = read_project_file("docs/deployment.md")

    assert "CLOUDFLARE_TUNNEL_TOKEN=" in env_example
    assert "DEBIAN_MIRROR=" in env_example
    assert "DEBIAN_SECURITY_MIRROR=" in env_example
    assert "PIP_INDEX_URL=" in env_example
    assert "Cloudflare Tunnel" in docs
    assert "Cloudflare Access" in docs
    assert "CLOUDFLARE_TUNNEL_TOKEN" in docs
    assert "http://app:8765" in docs
    assert "docker compose up -d --build" in docs
    assert "DEBIAN_MIRROR" in docs
    assert "PIP_INDEX_URL" in docs
    assert "不要暴露 8765" in docs
    assert "./scripts/backup_sqlite.sh" in docs


def test_backup_script_snapshots_sqlite_and_config_to_timestamped_archive() -> None:
    script = read_project_file("scripts/backup_sqlite.sh")

    assert "#!/usr/bin/env bash" in script
    assert "set -euo pipefail" in script
    assert 'DB_PATH="${ARXIV_DAILY_DATABASE:-./data/arxiv-local-daily.sqlite3}"' in script
    assert 'CONFIG_DIR="${ARXIV_DAILY_CONFIG_DIR:-./config}"' in script
    assert 'BACKUP_DIR="${ARXIV_DAILY_BACKUP_DIR:-./backups}"' in script
    assert 'TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"' in script
    assert 'sqlite3 "$DB_PATH" ".backup \'$TMP_DB\'"' in script
    assert 'tar -czf "$TAR_PATH"' in script


def test_git_and_docker_ignore_local_runtime_and_secret_files() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    dockerignore = read_project_file(".dockerignore")

    for ignored in [
        ".env",
        "arxiv-local-daily/data/",
        "arxiv-local-daily/backups/",
        "arxiv-local-daily/config/llm.local.json",
        "arxiv-local-daily/config/summary_template.local.json",
        "*.sqlite3",
    ]:
        assert ignored in gitignore

    for ignored in [
        ".env",
        "data/",
        "backups/",
        "config/llm.local.json",
        "config/summary_template.local.json",
        ".venv/",
    ]:
        assert ignored in dockerignore
