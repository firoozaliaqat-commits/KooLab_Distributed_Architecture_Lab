# KooLab v6.1 — ECS proxy startup repair

## Fixed
- Corrected Nginx proxy startup by restoring the minimal Linux capabilities needed for the default master/worker image (`NET_BIND_SERVICE`, `SETUID`, `SETGID`) while still dropping all others. In v6, `cap_drop: [ALL]` could cause Nginx to exit/restart and the host HTTP port to refuse connections.
- Installer now suppresses repeated `curl` connection errors, detects repeated Nginx restarts early, and prints proxy logs.
- Included `scripts/REPAIR_EXISTING_V6.sh` for in-place repair without removing database or named volumes.

## No changes
- No application login or password. Grafana remains anonymous read-only.
- Three application replicas, two queue workers, Redis, Prometheus and Grafana remain configured.
- The deployment remains single-ECS, not true cross-AZ.

## Verification
- Static YAML, Nginx syntax (using locally substituted addresses), Python AST, and installer shell syntax can be checked without a Docker daemon.
- Full Docker end-to-end execution must be checked on the destination Huawei ECS.
