#!/usr/bin/env bash
# Ubuntu ECS: passwordless training stack. Does not change SSH, firewall or Huawei cloud settings.
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$0")")"
trap 'echo "[ERROR] Installation failed at line $LINENO. Run: sudo docker compose logs --tail 80 proxy app1 grafana prometheus" >&2' ERR
say(){ printf '\n[KooLab v6.1] %s\n' "$*"; }
die(){ echo "[ERROR] $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die 'Run: sudo bash install.sh'
[[ -f /etc/os-release ]] || die 'Unsupported operating system'
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu ]] || die 'Ubuntu 22.04/24.04+ ECS required'
command -v apt-get >/dev/null || die 'APT not found'
export DEBIAN_FRONTEND=noninteractive
apt_retry(){ for i in 1 2 3; do if apt-get update -qq; then return 0; fi; sleep 3; done; return 1; }
if ! command -v curl >/dev/null || ! command -v ss >/dev/null || ! command -v unzip >/dev/null; then
  say 'Installing basic Ubuntu utilities'
  apt_retry || die 'APT unreachable; check ECS outbound network'
  apt-get install -y ca-certificates curl iproute2 unzip
fi
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  say 'Installing official Docker Engine + Compose plugin'
  apt_retry || die 'APT unreachable'
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl --retry 3 --retry-delay 2 -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc || die 'Cannot access official Docker GPG key'
  chmod a+r /etc/apt/keyrings/docker.asc
  code="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
  [[ -n "$code" ]] || die 'Ubuntu codename missing'
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $code
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt_retry || die 'Docker repository is not reachable'
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || die 'Docker installation failed; remove conflicting docker.io packages if present'
fi
systemctl enable --now docker >/dev/null || die 'Docker daemon unavailable'
docker info >/dev/null || die 'Docker not ready'
# Keep local fallback database writable by non-root application containers.
mkdir -p data
chown -R 10001:10001 data
chmod 0700 data
if [[ ! -f .env ]]; then
  cat > .env <<'EOF'
APP_PORT=80
# Optional: set GRAFANA_ROOT_URL=http://YOUR_ECS_EIP/grafana/ to make Grafana canonical redirects match the EIP.
# GRAFANA_ROOT_URL=http://YOUR_ECS_EIP/grafana/
TRACKER_URL=https://huawei.stackcrm.online
TRACKER_LAB_CODE=KOOLAB_ELASTIC_SEC
EOF
  chmod 600 .env
fi
port="$(sed -n 's/^APP_PORT=//p' .env | tail -1)";port="${port:-80}"
[[ "$port" =~ ^[0-9]+$ ]] && ((port>=1 && port<=65535)) || die 'APP_PORT invalid in .env'
# Huawei Cloud documents a link-local metadata endpoint for primary-interface EIP.
# Set a canonical Grafana URL automatically when available; optional for local/private IP runs.
if ! grep -q '^GRAFANA_ROOT_URL=' .env; then
  public_ip="$(curl --noproxy '*' -fsS --connect-timeout 1 --max-time 2 \
    http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
  if [[ "$public_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    suffix=''; [[ "$port" == 80 ]] || suffix=":$port"
    echo "GRAFANA_ROOT_URL=http://${public_ip}${suffix}/grafana/" >> .env
    say "Detected Huawei ECS EIP and configured Grafana root URL: http://${public_ip}${suffix}/grafana/"
  else
    say 'No ECS EIP found in metadata. Grafana falls back to localhost canonical URL; set GRAFANA_ROOT_URL in .env if redirects are wrong.'
  fi
fi
if ss -Hltna "sport = :$port" | grep -q LISTEN; then
  existing="$(docker compose ps -q proxy 2>/dev/null || true)"
  [[ -n "$existing" ]] || die "Port $port in use by another service. Change APP_PORT in .env, or stop that service."
fi
say 'Validating Docker Compose and downloading/building stack images'
docker compose config -q || die 'Compose file invalid'
docker compose up -d --build --remove-orphans || die 'Containers could not start; verify ECS internet, disk space and Docker Hub / PyPI reachability'
ready=0
say "Checking web proxy health on port $port"
for i in $(seq 1 60); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$port/healthz" 2>/dev/null | grep -qx OK; then
    ready=1
    break
  fi
  # Fail early if the proxy is repeatedly crashing; show actionable logs.
  proxy_id="$(docker compose ps -aq proxy 2>/dev/null || true)"
  if [[ -n "$proxy_id" ]]; then
    restarts="$(docker inspect --format '{{.RestartCount}}' "$proxy_id" 2>/dev/null || echo 0)"
    if [[ "$restarts" =~ ^[0-9]+$ ]] && ((restarts >= 3)); then
      say "Nginx proxy restarted ${restarts} times; displaying startup failure"
      docker compose logs --tail 70 proxy || true
      die 'Nginx proxy repeatedly crashed; inspect the proxy error above'
    fi
  fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  docker compose ps
  docker compose logs --tail 60 proxy app1 app2 app3 redis || true
  die 'KooLab web app did not become healthy; check port bindings, firewall, and Nginx startup logs'
fi
say 'Validating distributed app endpoints'
curl -fsS --max-time 5 "http://127.0.0.1:$port/api/architecture" >/dev/null || die 'Architecture API unavailable'
curl -fsS --max-time 5 "http://127.0.0.1:$port/api/identity" >/dev/null || die 'Replica identity API unavailable'
# Monitoring may take slightly longer than the web app.
for i in $(seq 1 30); do
  prom=0;graf=0
  curl -fsS --max-time 3 "http://127.0.0.1:$port/prometheus/-/healthy" >/dev/null 2>&1 && prom=1 || true
  curl -fsS --max-time 3 "http://127.0.0.1:$port/grafana/api/health" >/dev/null 2>&1 && graf=1 || true
  if [[ "$prom" == 1 && "$graf" == 1 ]];then break;fi
  sleep 2
done
printf '\n==============================================================\n'
echo ' KooLab DISTRIBUTED ARCHITECTURE v6.1 | NO APP PASSWORD'
echo '=============================================================='
echo " Web Dashboard: http://ECS_PUBLIC_EIP:$port/"
echo " Grafana:       http://ECS_PUBLIC_EIP:$port/grafana/"
echo " Prometheus:    http://ECS_PUBLIC_EIP:$port/prometheus/targets"
echo ' 3 app replicas | 2 queue workers | Redis | Prometheus | Grafana'
echo ' Login: NONE (Grafana is anonymous READ-ONLY)'
echo " Local health: http://127.0.0.1:$port/healthz"
echo " Prometheus healthy: $prom | Grafana healthy: $graf"
echo ' IMPORTANT: Permit TCP 80 only from approved classroom public IPs'
echo ' Do NOT expose this passwordless lab to an unrestricted Internet'
echo ' This is ONE ECS container simulation, not multiple ECS or AZs'
echo ' All student tracker tokens still require instructor-issued tokens'
echo '=============================================================='
docker compose ps
say 'Review STUDENT_QUICK_START.md and docs/DISTRIBUTED_LABS.md'
