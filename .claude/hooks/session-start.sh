#!/bin/bash
# SessionStart-Hook: stellt sicher, dass die Python-Engine in einer frischen
# (Web-)Session lauffaehig ist. Bewusst tolerant — darf die Session nie killen.
set -uo pipefail

# Nur in der Remote-Umgebung (Claude Code on the web) noetig.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  echo '{}'
  exit 0
fi

# Async: blockiert den Session-Start nicht.
echo '{"async": true, "asyncTimeout": 300000}'

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Engine-Abhaengigkeiten (idempotent). Fehler (offline/langsam) ignorieren,
# damit die Session trotzdem startet.
pip3 install --quiet --disable-pip-version-check -r requirements.txt 2>/dev/null || true
