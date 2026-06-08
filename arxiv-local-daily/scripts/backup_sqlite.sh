#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${ARXIV_DAILY_DATABASE:-./data/arxiv-local-daily.sqlite3}"
CONFIG_DIR="${ARXIV_DAILY_CONFIG_DIR:-./config}"
BACKUP_DIR="${ARXIV_DAILY_BACKUP_DIR:-./backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 is required for a safe SQLite backup." >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TMP_DB="$TMP_DIR/arxiv-local-daily.sqlite3"
sqlite3 "$DB_PATH" ".backup '$TMP_DB'"

TAR_PATH="$BACKUP_DIR/arxiv-local-daily-$TIMESTAMP.tar.gz"
TAR_ARGS=(-C "$TMP_DIR" arxiv-local-daily.sqlite3)

if [[ -d "$CONFIG_DIR" ]]; then
  CONFIG_PARENT="$(cd "$(dirname "$CONFIG_DIR")" && pwd)"
  CONFIG_NAME="$(basename "$CONFIG_DIR")"
  TAR_ARGS+=(-C "$CONFIG_PARENT" "$CONFIG_NAME")
fi

tar -czf "$TAR_PATH" "${TAR_ARGS[@]}"
echo "Backup written to $TAR_PATH"
