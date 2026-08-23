#!/bin/sh
# neoori nightly MySQL backup. Installed on the VPS at /usr/local/bin/neoori-backup.sh
# and run from cron (see DOCKER.md). Keeps 7 days locally; copies off-box when an
# rclone remote is configured.
set -eu

STACK=/srv/neoori
COMPOSE="docker compose -f $STACK/docker-compose.prod.yml"
DEST=/backups
KEEP_DAYS=7
# Off-box target, e.g. "r2:neoori-backups". Empty = local-only (a disk failure
# then takes the backups with the database — configure this before launch).
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
RCLONE_KEEP=30d

STAMP=$(date +%F)
FILE="$DEST/neoori-$STAMP.sql.gz"

mkdir -p "$DEST"
cd "$STACK"

# --single-transaction keeps InnoDB consistent without locking writes.
# The password is read inside the container so it never lands in the host's
# process list.
# No --databases on purpose: the dump then carries no USE statement, so it can
# be restored into a scratch database for testing. compose already creates the
# real `neoori` database (MYSQL_DATABASE), so nothing is lost.
$COMPOSE exec -T db sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines \
     --no-tablespaces neoori' | gzip > "$FILE.part"

# gzip of an empty/failed dump still exits 0 — check the payload before promoting.
if [ "$(gzip -dc "$FILE.part" | head -c 200 | wc -c)" -lt 100 ]; then
  echo "backup: dump looks empty, keeping $FILE.part for inspection" >&2
  exit 1
fi
mv "$FILE.part" "$FILE"
echo "backup: wrote $FILE ($(du -h "$FILE" | cut -f1))"

if [ -n "$RCLONE_REMOTE" ] && command -v rclone >/dev/null 2>&1; then
  rclone copy "$FILE" "$RCLONE_REMOTE/"
  rclone delete "$RCLONE_REMOTE/" --min-age "$RCLONE_KEEP"
  echo "backup: copied to $RCLONE_REMOTE"
else
  echo "backup: WARNING off-box copy skipped (RCLONE_REMOTE unset or rclone missing)" >&2
fi

find "$DEST" -name 'neoori-*.sql.gz' -mtime "+$KEEP_DAYS" -delete
