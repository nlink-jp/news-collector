#!/bin/bash
# entrypoint.sh — Cloud Run Job entrypoint for news-collector
#
# Required environment variables:
#   GOOGLE_CLOUD_PROJECT   — GCP project ID (for Vertex AI)
#   GCS_BUCKET             — GCS bucket for SQLite DB persistence
#   SWRITE_MODE=server     — swrite server mode
#   SWRITE_TOKEN           — Slack bot token
#   SWRITE_CHANNEL         — Slack channel for posting
#
# Optional:
#   GOOGLE_CLOUD_LOCATION  — Vertex AI region (default: us-central1)
#   TOPICS_FILE            — Path to topics.toml (default: /app/topics.toml)
#   DB_FILENAME            — DB filename in GCS (default: news.db)
#   NEWS_LANG              — Translation/posting language (default: ja)
#   POST_MODE              — "curate" or "notify" (default: curate)
#   SKIP_POST              — Set to "true" to skip Slack posting

set -euo pipefail

# uv tool install puts binaries in ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"

DB="/tmp/${DB_FILENAME:-news.db}"
BUCKET="${GCS_BUCKET}"
TOPICS="${TOPICS_FILE:-/app/topics.toml}"
LANG="${NEWS_LANG:-ja}"
MODE="${POST_MODE:-curate}"

echo "[$(date -Iseconds)] Starting news-collector job"
echo "  Project:  ${GOOGLE_CLOUD_PROJECT}"
echo "  Bucket:   gs://${BUCKET}"
echo "  Topics:   ${TOPICS}"
echo "  Language: ${LANG}"
echo "  Mode:     ${MODE}"

# ── Step 1: Download DB from GCS (if exists) ──
echo ""
echo "[Step 1] Downloading database from GCS..."
if gsutil -q cp "gs://${BUCKET}/${DB_FILENAME:-news.db}" "$DB" 2>/dev/null; then
  echo "  Downloaded existing database."
else
  echo "  No existing database found. Starting fresh."
fi

# ── Step 2: Collect articles ──
echo ""
echo "[Step 2] Collecting articles..."
news-collector collect --topics "$TOPICS" --db "$DB" --verbose

# ── Step 3: Process (tag + summarize + translate) ──
echo ""
echo "[Step 3] Processing articles..."
news-collector process --topics "$TOPICS" --db "$DB" --verbose

# ── Step 4: Post to Slack ──
if [ "${SKIP_POST:-false}" = "true" ]; then
  echo ""
  echo "[Step 4] Skipping Slack post (SKIP_POST=true)"
else
  echo ""
  echo "[Step 4] Posting to Slack (${MODE})..."
  news-collector "$MODE" --db "$DB" --lang "$LANG" \
    | while IFS= read -r line; do
        printf '%s' "$line" | swrite post --format blocks --no-unfurl
        sleep 1
      done
fi

# ── Step 5: Upload DB to GCS ──
echo ""
echo "[Step 5] Uploading database to GCS..."
gsutil -q cp "$DB" "gs://${BUCKET}/${DB_FILENAME:-news.db}"
echo "  Done."

echo ""
echo "[$(date -Iseconds)] Job completed successfully."
