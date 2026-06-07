# Phase 40 Plan: Cloudflare Tunnel Deployment

**Goal:** Add a deployment package that lets the app run on a server behind Cloudflare Tunnel with persistent local data, local AI configuration files, backup support, and no public exposure of port 8765.

**Architecture:** Docker runs the FastAPI app inside one container and `cloudflared` inside another container on the same Compose network. The app listens on `0.0.0.0:8765` only inside Docker; Cloudflare Tunnel forwards the public hostname to `http://app:8765`. SQLite data is mounted at `/data`, local config files are mounted at `/config`, and backups are written to a local `backups/` directory.

**Tech Stack:** Docker, Docker Compose, Cloudflare Tunnel, SQLite, FastAPI/Uvicorn, shell backup script.

## Implementation Tasks

1. Add deployment structure tests for Dockerfile, Compose, Cloudflare template, `.env.example`, backup script, docs, and git ignores.
2. Add environment-variable override for the SQLite database path so the container can write to `/data/arxiv-local-daily.sqlite3`.
3. Add `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, and optional named-tunnel `cloudflared` config template.
4. Add a SQLite-safe backup script that snapshots the DB and includes local config files in a timestamped archive.
5. Add Chinese deployment documentation covering domain setup, Cloudflare Access, the no-public-8765 rule, Compose startup, logs, backups, and updates.
6. Update the phase log and README pointer.

## Verification

- Focused deployment/config tests pass.
- Full Python test suite passes.
- `docker compose config` is checked when Docker Compose is available locally.
