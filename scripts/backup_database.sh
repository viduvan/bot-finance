#!/usr/bin/env bash
# backup_database.sh — Phase 8.8
# PostgreSQL backup script for ACTA trading system.
#
# Usage:
#   ./scripts/backup_database.sh
#   ./scripts/backup_database.sh --rotate-days 7  (default: 30)
#
# Output: backups/acta_YYYYMMDD_HHMMSS.sql.gz
#
# Add to crontab for daily 2am backup:
#   0 2 * * * /home/ubuntu/bot-finance/scripts/backup_database.sh >> /var/log/acta_backup.log 2>&1

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-$(dirname "$(realpath "$0")")/../backups}"
ROTATE_DAYS="${ROTATE_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/acta_${TIMESTAMP}.sql.gz"

# Load DB credentials from .env if present
ENV_FILE="$(dirname "$(realpath "$0")")/../apps/backend/.env"
if [ -f "$ENV_FILE" ]; then
    # Extract only DB_ vars safely
    export "$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1)" 2>/dev/null || true
fi

# Parse args
for arg in "$@"; do
    case $arg in
        --rotate-days=*)
            ROTATE_DAYS="${arg#*=}"
            ;;
        --rotate-days)
            shift
            ROTATE_DAYS="${1:-30}"
            ;;
    esac
done

# ── Validate ─────────────────────────────────────────────────────
if ! command -v pg_dump &>/dev/null; then
    echo "❌ pg_dump not found. Install postgresql-client."
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# ── Backup ───────────────────────────────────────────────────────
echo "🔄 Starting backup at $(date)"
echo "   Output: $BACKUP_FILE"

# Parse DATABASE_URL format: postgresql+asyncpg://user:pass@host:port/dbname
# or standard postgresql://user:pass@host:port/dbname
if [ -n "${DATABASE_URL:-}" ]; then
    # Strip asyncpg driver prefix if present
    URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
    URL="${URL/postgresql+psycopg:\/\//postgresql:\/\/}"
else
    # Fallback defaults
    URL="postgresql://acta:acta@localhost:5432/acta"
fi

pg_dump "$URL" --no-password --format=plain --clean --if-exists | gzip > "$BACKUP_FILE"

SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "✅ Backup complete: $BACKUP_FILE ($SIZE)"

# ── Rotate old backups ───────────────────────────────────────────
echo "🗑️  Removing backups older than ${ROTATE_DAYS} days..."
REMOVED=$(find "$BACKUP_DIR" -name "acta_*.sql.gz" -mtime +"$ROTATE_DAYS" -print -delete | wc -l)
echo "   Removed: $REMOVED file(s)"

# ── Verify integrity ─────────────────────────────────────────────
echo "🔍 Verifying backup integrity..."
if gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "✅ Backup integrity OK"
else
    echo "❌ Backup integrity FAILED — file may be corrupt"
    exit 1
fi

echo "🎉 Backup finished at $(date)"
