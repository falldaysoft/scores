# Self-Hosting Scores

This guide covers deploying Scores to your own infrastructure.

## Requirements

- Docker
- Kubernetes cluster (or Docker Compose for simpler setups)
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

## Kubernetes with Helm

The included Helm chart deploys the application with:

- Deployment with 2 replicas
- ClusterIP service on port 8000
- Ingress (configure your hostname)
- Migration job (runs on deploy)
- CronJob for expired score cleanup (daily at 2 AM)

### Setup

1. Copy `secrets-placeholders.yaml` to `secrets.yaml`
2. Fill in your base64-encoded secrets
3. Apply secrets to your cluster:

```bash
kubectl apply -f devops/secrets.yaml
```

4. Install the Helm chart:

```bash
helm install scores devops/helm/scores \
  --set tag=latest \
  --set hostname=scores.example.com
```

### Updating

```bash
helm upgrade scores devops/helm/scores --set tag=v1.2.3
```

## Maintenance

### Expired Score Cleanup

Scores expire after 7 days by default. The Kubernetes deployment includes a CronJob that runs daily. For other deployments, schedule this command:

```bash
python manage.py cleanup_expired_scores
```

### Creating an Admin User

```bash
python manage.py createsuperuser
```

Access the Django admin panel at `/backroom/`.