#!/bin/sh
set -eu
if [ "${1:-}" = serve ]; then
    python3 /app/provision.py render
    exec nginx -g 'daemon off;'
fi
exec python3 /app/provision.py "$@"
