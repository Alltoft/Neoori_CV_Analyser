# Docker — dev & production runbook

Four containers: **nginx** (only exposed service) → **frontend** (Next.js standalone)
+ **backend** (Flask/gunicorn) → **db** (MySQL 8.4). Everything else stays on the
internal compose network — no published ports, so nothing bypasses ufw.

## Local development

```bash
docker compose up -d          # first run builds images (a few minutes)
open http://localhost:8080    # nginx: / -> Next.js, /api -> Flask
```

- `backend/.env` must exist (it already does; template: `backend/.env.example`).
- Port 80 is left to the TaifOr dev stack; neoori dev uses **8080**.
- Direct ports (loopback only): frontend `:3001`, backend `:5001`, MySQL `:3306`.
- Dev MySQL reuses the old `backend_neoori_mysql_data` volume — existing local
  data carries over. Fresh machine? Seed: `docker compose exec backend python seed_prompt_v17.py`.
- Hot reload works through bind mounts. After changing `requirements.txt` or
  `package-lock.json`: `docker compose build backend|frontend && docker compose up -d`.

## VPS bootstrap (once)

```bash
ssh neoori   # root@186.240.157.26 (see ~/.ssh/config)

curl -fsSL https://get.docker.com | sh

# Log rotation — docker logs are unbounded by default and will fill the disk
cat >/etc/docker/daemon.json <<'EOF'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
EOF
systemctl restart docker

ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

mkdir -p /srv/neoori
```

From the laptop, first sync + secrets:

```bash
scp -r docker-compose.prod.yml nginx neoori:/srv/neoori/
scp .env.example neoori:/srv/neoori/.env    # then ssh in and FILL IN real values
```

On the VPS (GHCR images are private — create a GitHub PAT with `read:packages`):

```bash
docker login ghcr.io -u alltoft
cd /srv/neoori
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend python seed_prompt_v17.py
curl -s http://localhost/api/health        # {"status":"ok"}
```

Note: in `NGINX_MODE=http` (pre-TLS) **login does not work** — JWT cookies are
`Secure`-only in production. Expected; full flows come after TLS.

## CI/CD (git push = deploy)

`.github/workflows/deploy.yml` builds both images, pushes to GHCR, syncs
compose+nginx to `/srv/neoori`, then `pull` + `up -d` over SSH.

One-time setup — dedicated deploy keypair (never a personal key):

```bash
ssh-keygen -t ed25519 -f /tmp/neoori_deploy -N "" -C "gh-actions-deploy"
ssh neoori "cat >> ~/.ssh/authorized_keys" < /tmp/neoori_deploy.pub
```

GitHub repo → Settings → Secrets → Actions:
`VPS_HOST` = `186.240.157.26` · `VPS_USER` = `root` · `VPS_SSH_KEY` = contents of `/tmp/neoori_deploy` (then delete the local copy).

Rollback to any commit: `IMAGE_TAG=<commit-sha> docker compose -f docker-compose.prod.yml up -d` on the VPS.

## TLS (once a domain exists)

```bash
# 1. DNS A record -> 186.240.157.26; set DOMAIN=... in /srv/neoori/.env (keep NGINX_MODE=http)
docker compose -f docker-compose.prod.yml up -d nginx

# 2. Issue the certificate over the ACME webroot nginx already serves
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot -d "$DOMAIN" --email you@example.com --agree-tos --no-eff-email

# 3. Switch nginx to the TLS template
sed -i 's/^NGINX_MODE=.*/NGINX_MODE=https/' .env
docker compose -f docker-compose.prod.yml up -d nginx
```

Also set the GitHub repo **variable** `SITE_URL=https://<domain>` (Settings →
Secrets and variables → Actions → Variables) and re-run the deploy workflow —
it's baked into the frontend image as `NEXT_PUBLIC_SITE_URL` (metadata/OG URLs).

The `certbot` container renews automatically every 12 h; nginx picks up renewed
certs on reload (`docker compose -f docker-compose.prod.yml exec nginx nginx -s reload` if needed).

## Data migration (TiDB Cloud → VPS MySQL, at cutover)

```bash
mysqldump -h <tidb-host> -P 4000 -u <tidb-user> -p --ssl-mode=REQUIRED \
  --single-transaction --no-tablespaces --set-gtid-purged=OFF neoori > dump.sql
scp dump.sql neoori:/srv/neoori/
ssh neoori 'cd /srv/neoori && docker compose -f docker-compose.prod.yml exec -T db \
  mysql -uneoori -p"$MYSQL_PASSWORD" neoori < dump.sql'
```

The alembic version table travels with the dump, so `flask db upgrade` stays consistent.

## Backups

Script lives in the repo: `scripts/neoori-backup.sh`. Installed on the VPS
(23/08) at `/usr/local/bin/neoori-backup.sh`, cron `0 3 * * *`, log
`/var/log/neoori-backup.log`. Dumps to `/backups/neoori-<date>.sql.gz`,
keeps 7 days.

Re-install after editing the script:

```bash
scp scripts/neoori-backup.sh neoori:/usr/local/bin/neoori-backup.sh
ssh neoori 'chmod +x /usr/local/bin/neoori-backup.sh && /usr/local/bin/neoori-backup.sh'
```

**Still local-only** — a disk failure takes the backups with the database.
Set an off-box target before real users: install rclone, configure an R2/B2
remote, then add `RCLONE_REMOTE=r2:neoori-backups` to the cron line. The script
warns on stderr (and the log) every night until this is done.

The dump deliberately omits `--databases`, so it carries no `USE` statement and
can be restored into a scratch database. Restore test (run before launch and
after any schema change — an untested backup is not a backup):

```bash
ssh neoori
cd /srv/neoori && C="docker compose -f docker-compose.prod.yml exec -T db"
$C sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "create database neoori_restore_test"'
gzip -dc /backups/neoori-<date>.sql.gz | $C sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" neoori_restore_test'
# compare table count + spot-check rows against neoori, then:
$C sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "drop database neoori_restore_test"'
```

Last verified 23/08: 9/9 tables restored, `prompt_versions` = v1.7.
