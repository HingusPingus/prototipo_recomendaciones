#!/usr/bin/env bash
# Envoltorio: la lógica vive en publish_issues.py, que sí es idempotente (actualiza los issues
# existentes en lugar de recrearlos). Sin argumentos simula; con --apply ejecuta.
set -euo pipefail
exec python "$(cd "$(dirname "$0")" && pwd)/publish_issues.py" "$@"
