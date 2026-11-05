#!/usr/bin/env bash
# Lance l'API Trophy (lecture seule) sur la boucle locale.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source env.sh
: "${TROPHY_UID:?exporter TROPHY_UID}"; : "${TROPHY_PWD:?exporter TROPHY_PWD}"
: "${TROPHY_API_KEY:?exporter TROPHY_API_KEY}"
exec uvicorn api.app:app --host "${API_HOST:-127.0.0.1}" --port "${API_PORT:-8081}"
