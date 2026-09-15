# Self-Hosting Scores

This guide covers deploying Scores to your own infrastructure.

## Requirements

- Docker
- Docker Compose (or any container host)
- PostgreSQL database
- SMTP server for email verification

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key (generate a random string) |
| `DB_NAME` | Yes | PostgreSQL database name |
| `DB_USER` | Yes | PostgreSQL username |
| `DB_PASSWORD` | Yes | PostgreSQL password |
| `DB_HOST` | Yes | PostgreSQL host |
| `DB_PORT` | No | PostgreSQL port (default: 5432) |
| `DEBUG` | No | Set to `False` in production |
| `ALLOWED_HOSTS` | Yes | Comma-separated list of allowed hostnames |
| `SITE_URL` | Yes | Public URL (e.g., `https://scores.example.com`) |
| `EMAIL_BACKEND` | No | Default: console backend |
| `EMAIL_HOST` | No | SMTP server hostname |
| `EMAIL_PORT` | No | SMTP port (default: 587) |
| `EMAIL_USE_TLS` | No | Enable TLS (default: true) |
| `EMAIL_HOST_USER` | No | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | SMTP password |
| `DEFAULT_FROM_EMAIL` | No | From address for emails |
| `SCORE_EXPIRATION_DAYS` | No | Days before scores expire (default: 7) |

## Docker

Build the image:

```bash
docker build -f devops/Dockerfile -t scores:latest .
```

Run with Docker:

```bash
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret-key \
  -e DB_NAME=scores \
  -e DB_USER=scores \
  -e DB_PASSWORD=yourpassword \
  -e DB_HOST=your-postgres-host \
  -e SITE_URL=https://scores.example.com \
  -e ALLOWED_HOSTS=scores.example.com \
  -e DEBUG=False \
  scores:latest
```
For local testing, the email backend prints emails to the console so you can verify
your email address by copying the link from there.

Run migrations before first use:

```bash
docker run --rm \
  -e DB_NAME=scores \
  -e DB_USER=scores \
  -e DB_PASSWORD=yourpassword \
  -e DB_HOST=your-postgres-host \
  scores:latest python manage.py migrate
```

## Docker Compose behind Traefik

`docker-compose.yml` is how scores.fallday.ca runs: one `web` service on a
shared `infra-network` behind a Traefik container that terminates TLS, using a
shared `postgres` container for the database. The compose file carries every
non-secret setting inline; the secrets come from a `.env` next to it:

```
SECRET_KEY='...'          # single-quoted: compose interpolates $ in .env values
DB_PASSWORD=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
IMAGE_TAG=latest
```

The container's start command runs `migrate --noinput` and `setup_demo_games`
before starting gunicorn, so migrations run on every deploy.

```bash
cd ~/apps/scores
docker compose pull && docker compose up -d   # deploy IMAGE_TAG
docker compose logs -f web
docker compose run --rm cleanup               # expire old scores
```

To adapt it to another host, change the `Host()` rule and `SITE_URL`, and
create the `scores` role and database in your Postgres first.

### Deploying from CI

`deploy.sh` is installed at `~/apps/scores/deploy.sh` on the host and set as a
forced command for a dedicated SSH key in `~/.ssh/authorized_keys`:

```
command="/home/ubuntu/apps/scores/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty,restrict ssh-ed25519 AAAA... scores-ci-deploy
```

The GitHub Actions workflow (`.github/workflows/build-deploy.yml`) builds a
multi-arch image (amd64 and arm64), pushes it to `ghcr.io/falldaysoft/scores`,
then SSHes in with the `OVM_DEPLOY_KEY` repo secret, passing the commit sha as
the command. The script validates the tag, writes it to `.env` as `IMAGE_TAG`,
and runs `docker compose pull && up -d`.

### Restoring a database dump

`restore-from-dump.sh <file.dump>` stops the app, `pg_restore`s a custom-format
dump into the `scores` database, and starts the app again.

## Maintenance

### Expired Score Cleanup

Scores expire after 7 days by default. On the VM a host cron entry runs
`docker compose run --rm cleanup` daily at 02:00 UTC. For other deployments, schedule this command:

```bash
python manage.py cleanup_expired_scores
```

### Creating an Admin User

```bash
python manage.py createsuperuser
```

Access the Django admin panel at `/backroom/`.