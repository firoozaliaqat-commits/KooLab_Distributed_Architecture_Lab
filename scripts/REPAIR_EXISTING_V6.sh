#!/usr/bin/env bash
# Repair existing v6 installation IN PLACE without deleting volumes or SQLite data.
set -Eeuo pipefail
PROJECT_DIR="${1:-.}"
cd "$PROJECT_DIR"
[[ -f docker-compose.yml ]] || { echo 'ERROR: run in the existing v6 project folder, or provide its path'; exit 1; }
command -v python3 >/dev/null || { echo 'ERROR: Python 3 is required'; exit 1; }
python3 - <<'PYREPAIR'
from pathlib import Path
p=Path('docker-compose.yml')
s=p.read_text()
a=s.index('  proxy:\n'); b=s.index('\n  redis:\n', a)
section=s[a:b]
if 'cap_add:' not in section:
    assert '    cap_drop: [ALL]' in section, 'Expected v6 proxy configuration not found; no changes made'
    section=section.replace('    cap_drop: [ALL]', '    cap_drop: [ALL]\n    cap_add: [NET_BIND_SERVICE, SETUID, SETGID]')
    s=s[:a]+section+s[b:]
    p.write_text(s)
    print('Updated Nginx capabilities in docker-compose.yml')
else:
    print('Nginx capabilities already configured; no changes needed')
PYREPAIR
sudo docker compose config -q
sudo docker compose up -d --no-deps --force-recreate proxy
sudo docker compose ps proxy
printf '\nHealth check: '
for i in $(seq 1 15); do
  if curl -fsS --max-time 2 http://127.0.0.1:${APP_PORT:-80}/healthz 2>/dev/null | grep -qx OK; then
    echo OK
    exit 0
  fi
  sleep 2
done
sudo docker compose logs --tail=80 proxy
echo 'FAILED: Nginx still unhealthy. Provide proxy logs to the instructor.' >&2
exit 1
