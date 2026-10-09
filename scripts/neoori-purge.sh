#!/bin/sh
# Daily purge of the rows that live on a clock (four-doors spec, decision 46):
# held drafts after 48 h, unclaimed no-login reports after 30 days, advisor
# reports after 12 months, run_log after 2 days.
# Installed at /usr/local/bin/neoori-purge.sh, cron `30 3 * * *` (after the
# 03:00 backup), log /var/log/neoori-purge.log. See DOCKER.md, « Purge ».
set -euo pipefail
cd /srv/neoori
{
  echo "[$(date -u +%FT%TZ)] flask purge-expired"
  docker compose -f docker-compose.prod.yml exec -T backend flask purge-expired
} >> /var/log/neoori-purge.log 2>&1
