#!/bin/sh
set -eu

# GCD publishes a new dump roughly every 2 weeks -- run on the 1st and 15th
# of each month (close enough to "every 2 weeks" using a schedule cron can
# express natively, avoids day-count drift from `*/14`).
CRON_SCHEDULE="${CRON_SCHEDULE:-0 3 1,15 * *}"

printenv | grep -E '^(GCD_|POSTGRES_)' > /etc/environment

echo "$CRON_SCHEDULE cd /app && . /etc/environment && gcd-modifier run >> /proc/1/fd/1 2>> /proc/1/fd/2" > /etc/cron.d/gcd-modifier
chmod 0644 /etc/cron.d/gcd-modifier
crontab /etc/cron.d/gcd-modifier

echo "gcd-modifier cron sidecar started, schedule: $CRON_SCHEDULE"
cron -f
