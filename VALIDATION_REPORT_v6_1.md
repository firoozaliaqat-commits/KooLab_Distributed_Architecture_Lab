# KooLab v6.1 — validation and deployment notes

Date: 2026-11-11

## Confirmed in packaging workspace

- The original v6 ZIP was inspected; original Compose proxy service dropped all Linux capabilities while running the standard root-master Nginx Alpine image.
- v6.1 now explicitly adds `NET_BIND_SERVICE`, `SETUID`, and `SETGID` on the **proxy service only**, retaining `cap_drop: [ALL]`.
- `docker-compose.yml` parsed successfully as YAML, with all nine expected services.
- Static syntax of Nginx configuration validated successfully using installed `nginx -t` with loopback replacements for container DNS names.
- Shell syntax (`bash -n`) passed for `install.sh`, repair script, and smoke-test script.
- All application Python source files passed AST parsing.
- ZIP integrity verified by Python `zipfile.testzip()`.

## Not possible to verify in packaging workspace

- Full Compose image builds, container startup, Redis integration, and Grafana and Prometheus readiness (no Docker daemon in the workspace).
- Exact historical cause of ECS proxy crash without its `docker compose logs proxy` output. The capability drop is a concrete misconfiguration and a likely explanation.
- Huawei Cloud security group rules and ECS network access.

## Required ECS acceptance

```bash
sudo docker compose config -q
sudo docker compose up -d --build
sudo docker compose ps
sudo bash scripts/smoke-test.sh
sudo docker compose logs --tail=60 proxy
```

Expected: `proxy` remains Up/healthy, `curl -i http://127.0.0.1/healthz` returns HTTP 200 and `OK`, Grafana and Prometheus endpoints respond through the proxy. If these checks fail, collect logs before making further changes.

## Security

The user interface is intentionally passwordless for isolated classrooms. Restrict EIP inbound TCP 80 to the instructor or authorized classroom egress IPs. Restrict SSH. Do not expose internal monitoring or database ports.
