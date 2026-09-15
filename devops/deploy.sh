#!/bin/bash
# Deploy script run on the Oracle VM. Installed at ~/apps/scores/deploy.sh and
# wired as the forced command for the CI deploy key in ~/.ssh/authorized_keys,
# so the key can only ever run this script. CI passes the image tag (git sha)
# as the SSH command; it arrives here in SSH_ORIGINAL_COMMAND.
set -euo pipefail
cd /home/ubuntu/apps/scores

TAG="${SSH_ORIGINAL_COMMAND:-${1:-latest}}"
case "$TAG" in
  *[!A-Za-z0-9._-]*|"") echo "refusing bad tag: $TAG" >&2; exit 1 ;;
esac

if grep -q '^IMAGE_TAG=' .env; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$TAG/" .env
else
  echo "IMAGE_TAG=$TAG" >> .env
fi

echo "Deploying ghcr.io/falldaysoft/scores:$TAG"
docker compose pull --quiet
docker compose up -d --remove-orphans
docker image prune -f >/dev/null
docker compose ps
