#!/usr/bin/env bash
# World backup for the Salesian Minecraft server.
# Schedule via cron — see CLAUDE.md for the recommended entry.

set -euo pipefail

CONTAINER="minecraft-server"
SERVER_DIR="/home/pedro/Documents/minecraft-server"
BACKUP_DIR="/home/pedro/backups"
RETENTION_DAYS=14
TIMESTAMP="$(date +%Y%m%d-%H%M)"
ARCHIVE="${BACKUP_DIR}/world-${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

rcon() {
  docker exec -i "${CONTAINER}" rcon-cli "$@"
}

# Re-enable saves on any exit path so the server doesn't stay frozen.
restore_saves() {
  rcon save-on >/dev/null 2>&1 || true
}
trap restore_saves EXIT

echo "[$(date '+%F %T')] Starting backup → ${ARCHIVE}"

# Flush chunks and freeze writes while we copy.
rcon save-off
rcon save-all flush

tar -czf "${ARCHIVE}" \
  -C "${SERVER_DIR}/data" \
  world world_nether world_the_end

rcon save-on

echo "[$(date '+%F %T')] Backup complete: $(du -h "${ARCHIVE}" | cut -f1)"

# Prune old archives.
find "${BACKUP_DIR}" -name 'world-*.tar.gz' -mtime "+${RETENTION_DAYS}" -delete

echo "[$(date '+%F %T')] Pruned archives older than ${RETENTION_DAYS} days."
