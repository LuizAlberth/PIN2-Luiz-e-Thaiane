#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p backups
compose=(docker compose --env-file .env.production -f compose.free.yaml)

"${compose[@]}" exec -T api python -c 'import sqlite3; source=sqlite3.connect("/data/pin2.db"); target=sqlite3.connect("/data/backup-current.db"); source.backup(target); target.close(); source.close()'
"${compose[@]}" exec -T api mkdir -p /data/storage
"${compose[@]}" cp api:/data/backup-current.db "backups/pin2-${stamp}.db"
"${compose[@]}" cp api:/data/storage "backups/storage-${stamp}"
"${compose[@]}" exec -T api rm -f /data/backup-current.db
echo "Backup salvo em backups/ com data ${stamp}"
