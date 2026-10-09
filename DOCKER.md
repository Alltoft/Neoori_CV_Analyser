# Docker — dev & production runbook

Four containers: **nginx** (only exposed service) → **frontend** (Next.js standalone)
+ **backend** (Flask/gunicorn) → **db** (MySQL 8.4). Everything else stays on the
internal compose network — no published ports, so nothing bypasses ufw.

## Local development

```bash
docker compose up -d                       # first run builds images (a few minutes)
open http://neoori.localhost:8080          # the landing; nginx: / -> Next.js, /api -> Flask
open http://cv.neoori.localhost:8080       # « J'ai une cible »
open http://voyage.neoori.localhost:8080   # le voyage
```

- `backend/.env` must exist (it already does; template: `backend/.env.example`).
- Port 80 is left to the TaifOr dev stack; neoori dev uses **8080**.
- The three dev hosts work in Chrome, which resolves `*.localhost` to the
  loopback by itself (Safari does not). One sign-in covers the three: the
  session cookie is set on `neoori.localhost`. Plain `http://localhost:8080`
  shows the landing too, and its links lead to the three names.
- Direct ports (loopback only): frontend `:3001`, backend `:5001`, MySQL `:3306`.
- Dev MySQL reuses the old `backend_neoori_mysql_data` volume — existing local
  data carries over. Fresh machine? Seed the prompts (see below), prefixed with
  `docker compose exec backend`.
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
# the parcours 1 prompt plus the two voyage slots
for s in seed_prompt_v18.py \
         seed_prompt_v10_voyage_micro.py seed_prompt_v10_voyage_portrait.py; do
  docker compose -f docker-compose.prod.yml exec backend python $s
done
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
Not to a commit below the four-doors migration, though: that takes four commands in a fixed order, see « Rolling back below the four-doors migration » under Purge.

Rolling back below the subdomain split works the same way, with one
condition: if `APP_URL` and `FRONTEND_URL` were already deleted from
`/srv/neoori/.env`, put `FRONTEND_URL=https://neoori.tech` back first — the
earlier image builds Stripe's return URL from it, and its fallback is
`http://localhost:3000`. Everyone signs in once more (the earlier image reads
the old cookie names).

## TLS

**Done 23/08** — `neoori.tech` + `www.neoori.tech`; **expanded 09/10/2026** to
`cv.neoori.tech` and `voyage.neoori.tech` (« Adding cv. and voyage. », below),
cert expires 07/01/2027 and renews itself. The site is live at
https://neoori.tech; www 301s to the apex; plain http 301s to https. Steps
kept for a re-issue or a second domain:

```bash
# 1. DNS A records for the apex, www, cv and voyage -> 186.240.157.26;
#    set DOMAIN=... in /srv/neoori/.env (keep NGINX_MODE=http)
docker compose -f docker-compose.prod.yml up -d nginx

# 2. Issue the certificate over the ACME webroot nginx already serves.
#    --entrypoint certbot is REQUIRED: the service's entrypoint is the renew
#    loop, so without the override `certonly` is swallowed as a positional arg
#    and the container hangs forever instead of issuing anything.
#    Add --dry-run first — Let's Encrypt rate-limits failures.
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  -d neoori.tech -d www.neoori.tech -d cv.neoori.tech -d voyage.neoori.tech \
  --email nneoori@proton.me --agree-tos --no-eff-email

# 3. Switch nginx to the TLS template
sed -i 's/^NGINX_MODE=.*/NGINX_MODE=https/' .env
docker compose -f docker-compose.prod.yml up -d
```

The `certbot` container renews automatically every 12 h, but renewing does not
reach nginx — it holds the old certificate in memory until reloaded. A deploy
restarts nginx and hides this; a quiet month after a renewal would not. So a
second cron job reloads nginx nightly (installed 23/08):

```
0 4 * * * cd /srv/neoori && docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload >> /var/log/neoori-nginx-reload.log 2>&1
```

A reload is graceful — in-flight requests finish on the old workers.

### Adding cv. and voyage. (the subdomain split)

Done once, **before** the deploy that ships the split: without it `cv.` and
`voyage.` show a certificate warning.

```bash
# 1. DNS: A records cv and voyage -> 186.240.157.26. No AAAA (below). Wait
#    until both resolve: dig +short cv.neoori.tech voyage.neoori.tech
# 2. Expand the certificate. It keeps its name (--cert-name), so the
#    template's paths and the renew loop do not change. Today's port-80
#    server is the only one, so it answers the challenge for the new names.
#    --dry-run first: Let's Encrypt rate-limits failures.
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot --cert-name neoori.tech --expand \
  -d neoori.tech -d www.neoori.tech -d cv.neoori.tech -d voyage.neoori.tech \
  --email nneoori@proton.me --agree-tos --no-eff-email --dry-run
# then the same command without --dry-run, and:
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

**Until the deploy has reloaded nginx, check the new names with `curl -sI`
or `openssl s_client` only, never a browser.** The live nginx answers `cv.`
and `voyage.` with a permanent redirect (301) to the apex. A browser keeps
it, and after the deploy, when the apex sends the path back to `cv.` or
`voyage.`, it loops between the two (`ERR_TOO_MANY_REDIRECTS`). The deploy
has a few seconds of the same window, between `up -d` and the nginx reload,
so push at a quiet hour. Anyone caught clears the browser's cache and site
data for neoori.tech.

After the deploy, delete `APP_URL` and `FRONTEND_URL` from
`/srv/neoori/.env` and the GitHub repo variable `SITE_URL` — but only once
no rollback below the split is expected (« CI/CD », rollback).

### Do not publish an AAAA record (rate limits)

The per-IP limits on the auth endpoints (`limit_req` in the nginx templates)
key on the client address. Docker publishes 80/443 on `[::]` too, but the
compose network is IPv4-only, so docker-proxy relays an IPv6 connection to
nginx from the bridge gateway: every IPv6 visitor would appear as one client
and share the same buckets (5/min for register, resend-verification,
forgot-password, the email sign-in link request and the conseiller demande;
10/min for login, verify-email, reset-password, the email link's check and
consume, and the signup finalise step; 30/min for the Google / Microsoft
start and callback), which locks everyone out at
once. Verified 2026-10-01 on the VPS: a forced IPv6 request was logged by
nginx as client `172.18.0.1`. `neoori.tech` has no AAAA record today, so all
traffic arrives over IPv4 and the limits see real clients. Keep it that way
until the compose network has IPv6 enabled (`enable_ipv6` + a subnet) and the
templates `listen [::]:80` / `[::]:443`.

The open analysis form adds two more per-address limits, in the same templates.
The `analyses` zone (10 r/min, burst 40) and the `codes` zone (10 r/min, burst
20) limit the open form's POSTs per address; the polling GETs are not limited.
The `analyses` zone covers `POST /api/analyses/`, `/api/analyses/draft` and the
two PDF upload endpoints; the `codes` zone covers `POST /api/codes/check`, an
analysis unlock and the voyage unlock. The numbers are sized for a workshop
room behind one address: fifteen people, about four requests each, within
minutes. Both zones key on the client address like the auth ones, so the
warning above applies to them too: behind a shared IPv6 address every visitor
would draw on one 10 r/min bucket.

### No subdomain may point anywhere else

The session cookies carry `Domain=neoori.tech`: one sign-in for the landing,
`cv.` and `voyage.`, so every host under the domain receives them. A
subdomain served by anything but this stack — a blog, a status page, a Resend
click-tracking domain, any CNAME to an outside service, a staging copy of the
app — would receive every visitor's session. And because `cv.` and `voyage.`
count as one site to a browser, `SameSite=Lax` would not stop such a host from
sending signed-in requests either (CSRF protection is off). The zone holds the
apex, `www`, `cv`, `voyage` and the mail records Resend needs, and nothing else
that serves HTTP. A staging stack gets a domain of its own.

### Access logs record the path only

nginx and gunicorn log the path only (`log_format neoori_paths` in the nginx
templates, `--access-logformat` in `backend/entrypoint.sh`): sign-in links,
`next` paths and Stripe session ids travel in query strings, and the Referer
repeats them. An nginx access line carries the address, the time, the host,
the method, the path, the status, the size and the duration; gunicorn's
carries the same without the host, nothing more. To check on the VPS after a
deploy and a few requests:

```bash
cd /srv/neoori
docker compose -f docker-compose.prod.yml logs --since 10m nginx backend | grep -E 'token=|session_id=|redirect=|next='
```

No output means the access logs are clean. Two limits: nginx's *error* log
still prints the request line of a failed request, query string included
(`limit_req_log_level info` keeps the rate-limit refusals out of it), and the
gunicorn format belongs to the production image only — the local backend runs
Flask's own server, which logs query strings. An upstream failure is such a
request, so for the few seconds of every deploy in which the backend is
recreated the error log can hold a request line with its query string, though
the Referer it records beside it now carries only the origin
(`Referrer-Policy "strict-origin"` in the https template): a token page's own
requests no longer repeat its token there.

## Swapping the domain later

The domain is written in one place: `DOMAIN` in `/srv/neoori/.env` (nginx,
the backend and the frontend read it when their containers start). Each time
it changes:

1. DNS for the new domain: A records for the apex, `www`, `cv` and `voyage`
   → 186.240.157.26. No AAAA.
2. A certificate for the new domain's four names: the command in « TLS »
   with the new names and `--cert-name <new domain>`. nginx's port-80 default
   server answers the challenge for names it does not serve yet.
3. `DOMAIN=<new domain>` in `/srv/neoori/.env`, then
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate backend frontend nginx
   ```
   nginx re-renders its template; nothing is rebuilt.
4. Google and Microsoft: add `https://cv.<new>/api/auth/<provider>/callback`
   and `https://voyage.<new>/api/auth/<provider>/callback`.
5. Stripe: the webhook URL, `https://<new>/api/payments/webhook`.
6. Resend: verify the new domain, then change `MAIL_FROM`. Until then mails
   leave from the old address and link to the new domain — never the other
   way round: an unverified sender is refused, silently.

Links to the old domain (mails already sent, bookmarks) stop working once its
DNS moves away.

## Google / Microsoft sign-in keys

Four keys in `/srv/neoori/.env` (and `backend/.env` locally) configure the
two providers: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET`. Creating the two apps,
click by click, is in
`docs/superpowers/specs/2026-10-03-social-login-design.md`, appendices A and
B. A provider's button appears only once both its keys are set. After
editing `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

Each provider registers two redirect URIs, one per subdomain, because a
sign-in ends on the host it started on:
`https://cv.neoori.tech/api/auth/<provider>/callback` and
`https://voyage.neoori.tech/api/auth/<provider>/callback`. The spec's
appendices A and B predate the split and name the root's; use these two.

### Microsoft secret renewal

A Microsoft client secret lives 24 months at most. The day it expires,
« Continuer avec Microsoft » answers « La connexion n'a pas abouti ». Its
expiry date is the comment beside `MICROSOFT_CLIENT_SECRET` in
`/srv/neoori/.env`. A month before it:

1. In Entra, open the `neoori` app → Certificates & secrets → New client
   secret (24 months). The old one keeps working meanwhile.
2. Paste the new **Value** into `/srv/neoori/.env` and update the expiry
   comment.
3. Recreate the backend (command above), then sign in once with Microsoft.
4. Delete the old secret in Entra.

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

Last verified 23/08: 9/9 tables restored, `prompt_versions` = v1.7 (now v1.8).

## Purge

Rows that live on a clock, not an account (four-doors spec, decision 46):
held drafts after 48 h, unclaimed no-login reports after 30 days, advisor-door
reports after 12 months, `run_log` after 2 days. Script in the repo:
`scripts/neoori-purge.sh`, installed like the backup. From the laptop, in this
order:

```bash
# 1. Look at the crontab first (see the note below the block).
ssh neoori 'crontab -l'

# 2. Put the script on the VPS and make it executable. Do this step again after
#    any edit to the script; nothing else needs redoing.
scp scripts/neoori-purge.sh neoori:/usr/local/bin/neoori-purge.sh
ssh neoori 'chmod +x /usr/local/bin/neoori-purge.sh'

# 3. Add the job, once only (a second run adds a duplicate), then look again.
ssh neoori '(crontab -l; echo "30 3 * * * /usr/local/bin/neoori-purge.sh") | crontab -'
ssh neoori 'crontab -l'

# 4. First run, by hand, counting only; then read the log.
ssh neoori '/usr/local/bin/neoori-purge.sh --dry-run'
ssh neoori 'tail -n 6 /var/log/neoori-purge.log'
```

Log: `/var/log/neoori-purge.log`. Before adding the cron line, `crontab -l`
must already show the backup's `0 3 * * *` line — add beside it, never replace.
Writing a crontab replaces the whole table, which is why step 1 looks first:
every line you see there (the backup, the nginx reload `0 4 * * *`) must still
be there after step 3, with the purge line added (03:30, half an hour after the
03:00 backup).

What step 4 should show: the script passes its arguments to
`flask purge-expired` (it runs `cd /srv/neoori && docker compose -f
docker-compose.prod.yml exec -T backend flask purge-expired --dry-run` and logs
the command), and `--dry-run` deletes nothing. The last six log lines are the
command, four counts (`held_drafts`, `anonymous`, `advisor`, `run_log`) and
`dry run — nothing deleted`. Anything else means the script did not run: the
error is in the log, or printed by `ssh` if the script never started.

What the job selects, and nothing else: a held draft (a form saved before
signing in, with no owner) older than 48 h; a no-login report (`door` =
`anonymous`) that no account has claimed, older than 30 days; any `advisor`
report older than 365 days; `run_log` rows older than 2 days. Ages count from
`created_at`, which a submit sets to the time of the run. The first three
ages are the env settings `HELD_DRAFT_RETENTION_HOURS`,
`ANONYMOUS_RETENTION_DAYS` and `ADVISOR_RETENTION_DAYS`; the 2 days of
`run_log` is fixed in `backend/app/services/purge.py`. Owned, claimed and
`legacy` rows are never selected. Counselor notes and price feedback go with
their report. The cron run, with no argument, really deletes: the next
morning's log shows the same four counts and `deleted`.

### Rolling back below the four-doors migration

Rollback past this revision is not the plain `IMAGE_TAG=<sha> … up -d` of the
CI/CD section. The four-doors migration is `c1d2e3f4a5b6`, on top of
`b0c1d2e3f4a5`. Two things get in the way:

- The previous image cannot start against a database at this revision: its
  entrypoint runs `flask db upgrade` under `set -e`
  (`backend/entrypoint.sh:24`) and does not know `c1d2e3f4a5b6`.
- A downgrade alone drops the columns that keep some rows private. Advisor-door
  reports, unclaimed no-login reports and held drafts would become plain
  ownerless rows — reports and drafts that belong to no account — and the
  previous image serves an ownerless row to anyone holding its id.

So those rows go first, after a backup. Every command below runs on the VPS,
in `/srv/neoori`: the first two lines take you there, as in the restore test
under « Backups ». In order, with the new image still running:

```bash
ssh neoori
cd /srv/neoori
/usr/local/bin/neoori-backup.sh                   # 0. a fresh dump, before anything else
ls -lh /backups/neoori-$(date +%F).sql.gz
gzip -dc /backups/neoori-$(date +%F).sql.gz | head -c 200 | wc -c     # 100 or more
C="docker compose -f docker-compose.prod.yml exec -T backend"
$C flask purge-expired --before-rollback          # 1. counts only
$C flask purge-expired --before-rollback --apply  # 2. deletes
$C flask db downgrade b0c1d2e3f4a5                # 3. the revision before c1d2e3f4a5b6
IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml up -d   # 4. FORCE_ANALYSIS_TIER and FRONTEND_URL first
```

(`<sha>` is the commit of the image you are going back to.)

0. The backup comes first because command 2 cannot be undone: it deletes
   every advisor report (the counselors' only copy: the candidate never
   received one), every unclaimed no-login report and every held draft, and
   this dump is the only way back. The script checks its own dump, as every
   night: its last line is `backup: wrote /backups/neoori-<date>.sql.gz
   (<size>)`, followed by the off-box warning while no rclone remote is set
   (« Backups »). If it says `backup: dump looks empty` instead, or `ls` finds
   no file for today, stop here: nothing has been touched yet. The `gzip` line
   repeats the script's own test, the first 200 bytes of the dump: 100 or more
   means it holds SQL.
1. `--before-rollback` alone deletes nothing. It prints three counts —
   `held_drafts`, `anonymous`, `advisor` — and `dry run — nothing deleted`.
   Read them: they are the rows the next command destroys. Every `advisor`
   report counts, whatever its age, and so does every unclaimed `anonymous`
   report and every held draft. A no-login report that an account has kept
   is owned, so it stays.
2. `--before-rollback --apply` deletes them, with their counselor notes and
   price feedback. It cannot be undone, and the advisor reports are the
   counselors' only copy: the candidate never received one. Check: command 1
   again now prints zeros.
3. `flask db downgrade b0c1d2e3f4a5` removes the four-doors columns, keys and
   the `run_log` table. Check: `$C flask db current` names `b0c1d2e3f4a5`.
   `b0c1d2e3f4a5` is the head of the image that was live just before the
   four-doors deploy. Going back further, to an older image, needs that
   image's own head instead. Read it from the image itself, before command 3:
   `IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml run --rm
   --no-deps -e DATABASE_URL=sqlite:// backend flask db heads` prints it (an
   in-memory SQLite: the command only reads the image's migration files and
   never touches the database).
4. Before `up -d`, look at `FORCE_ANALYSIS_TIER` in `/srv/neoori/.env`. The
   four-doors image ignores it, but every image from `46f7380` (2026-07-30) to
   the one before four-doors reads it with `paid` as its default —
   `os.getenv("FORCE_ANALYSIS_TIER", "paid")`, `backend/app/routes/analyses.py:30`
   at `fd2f47f`. With no line in `.env`, every new analysis runs on the paid
   tier again after the rollback. Write `FORCE_ANALYSIS_TIER=paid` only if
   that is what you want back; `FORCE_ANALYSIS_TIER=` (empty) gives the
   normal tiers. Look at `FRONTEND_URL` too: this rollback also goes below
   the subdomain split, so if `APP_URL` and `FRONTEND_URL` were deleted from
   `.env` after it, write `FRONTEND_URL=https://neoori.tech` back first
   (« CI/CD »). `up -d` then starts the previous image with those settings,
   and its `flask db upgrade` finds nothing to do. Check:
   `curl -s https://neoori.tech/api/health` prints `{"status":"ok"}` (plain
   `http://` only redirects while `NGINX_MODE=https`).

Run commands 3 and 4 back to back: between them the running (new) code expects
columns the downgrade has just removed, so its requests fail. Keep the gap
between commands 2 and 3 short too: a row a visitor submits in it survives as
an ownerless row. For a rollback that must leave none, stop nginx before
command 0 (`docker compose -f docker-compose.prod.yml stop nginx`), so the
dump also holds every row command 2 deletes; the `up -d` of command 4 starts
it again.
