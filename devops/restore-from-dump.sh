#!/bin/bash
# Restore a pg_dump custom-format file into the VM's shared postgres container
# as the `scores` role. Stops the app during the restore so nothing writes mid-way.
# Usage (on the VM): ~/apps/scores/restore-from-dump.sh ~/backups/scores/<file>.dump
set -euo pipefail
DUMP="${1:?usage: restore-from-dump.sh <dump file>}"
cd /home/ubuntu/apps/scores
docker compose stop
docker exec -i postgres pg_restore -U scores -d scores --clean --if-exists --no-owner --no-acl < "$DUMP"
docker compose start
echo "restored $DUMP"
