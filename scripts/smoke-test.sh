#!/usr/bin/env bash
set -Eeuo pipefail
PORT="${1:-80}"
BASE="http://127.0.0.1:$PORT"
printf '[1/7] Web health: '; test "$(curl -fsS "$BASE/healthz")" = OK; echo OK
printf '[2/7] App status: ';curl -fsS "$BASE/api/status" | grep -q '"live":true';echo OK
printf '[3/7] Architecture: ';curl -fsS "$BASE/api/architecture" | grep -q '"replicas"';echo OK
printf '[4/7] Metrics endpoint: ';curl -fsS "$BASE/metrics" | grep -q 'koolab_';echo OK
printf '[5/7] Queue API: ';curl -fsS "$BASE/api/architecture/jobs" | grep -q '"jobs"';echo OK
printf '[6/7] Prometheus: ';curl -fsS "$BASE/prometheus/-/healthy" >/dev/null; echo OK
printf '[7/7] Grafana: ';curl -fsS "$BASE/grafana/api/health" >/dev/null; echo OK
echo 'All seven HTTP smoke checks passed.'
