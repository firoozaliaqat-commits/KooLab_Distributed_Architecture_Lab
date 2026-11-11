# KooLab Distributed Architecture Classroom v6

**Updated from the provided KooLab v5 HTTP Classroom source.** It retains the RDS, ELB inspector, CPU stress, EIP bandwidth, Security Center, assessment and optional instructor-tracker relay. It adds a multi-container distributed-systems simulation, metrics monitoring and a Grafana dashboard. **Application login removed as requested.**

Start with [STUDENT_QUICK_START.md](STUDENT_QUICK_START.md); detailed instructor exercises in [docs/DISTRIBUTED_LABS.md](docs/DISTRIBUTED_LABS.md).

## Deployment

On Huawei Ubuntu ECS, unzip archive, `cd KooLab_Distributed_Architecture_Lab_v6` and execute `sudo bash install.sh`. The script bootstraps Docker Engine / Compose, then `docker compose up -d --build` and tests `http://127.0.0.1/healthz`.

Open `http://ECS_EIP/` (no password), `http://ECS_EIP/grafana/` and `http://ECS_EIP/prometheus/targets`. On a custom port set `APP_PORT` in `.env` before installation. If Grafana redirects incorrectly, set `GRAFANA_ROOT_URL=http://ECS_EIP/grafana/` (include custom port if applicable) in `.env`, recreate Grafana, and refresh. Grafana anonymous users are **Viewer only**.

## Architecture

```text
Browser -> ECS EIP :80 -> Nginx software proxy
                               |-- app1:8080 --
                               |-- app2:8080 ----> SQLite bind mount (single ECS only)
                               |-- app3:8080 --/ \
                               |         |-------- Redis cache + persistent job queue
                               |                   |-- worker1
                               |                   |-- worker2
                               |
                    Prometheus (scrapes app1, app2, app3)
                               |
                            Grafana
```

All nine containers run **on one single Huawei ECS**. This simulates request distribution, stateless replicas, simple queue decoupling, caching, fault handling and observability. It **does not** demonstrate cross-ECS placement, cross-AZ resilience or true high availability. In particular, Nginx, Redis and the SQLite bind mount are shared single points of failure. If host stops, all components stop. To test actual HA, deploy multiple ECS hosts behind Huawei ELB with RDS and managed shared cache/queue.

### Services

| Service(s) | Purpose | External exposure |
|---|---|---|
| proxy | Nginx reverse proxy, software ELB analog | **Port 80 only** |
| app1, app2, app3 | FastAPI app replicas; each has own request/latency metrics | Internal only |
| redis | Cache + job queue + counter store (AOF) | Internal only |
| worker1, worker2 | Independent async queue consumers | Internal only |
| prometheus | 10s scrape, 2d retention | via `/prometheus/` reverse proxy |
| grafana | Provisioned dashboards, anonymous view-only | via `/grafana/` reverse proxy |

Local messages remain in a **shared bind-mounted SQLite DB** on this one ECS; for actual multi-ECS labs students must use shared Huawei RDS. The application's CPU stress test is bounded to 2 worker processes and 900s; service-level CPU quotas may prevent reaching Huawei Cloud Eye host-level >70% thresholds. Grafana shows **container application process** metrics, not Huawei ECS host metrics; compare actual host metrics in Cloud Eye for real scaling exercises.

## Security and operational boundaries

- **No lab application password and no Grafana viewer login.** This makes the API unsuitable for Internet-wide access. Limit ECS security-group TCP 80 inbound to approved classroom IP addresses and a disposable network. Nginx applies a bounded rate limit, and FastAPI limits high-impact APIs. Application is non-root, no Docker socket, caps dropped, read-only root filesystem.
- No Huawei APIs/credentials are built in. App cannot change actual ELB, AS, DNS, VPC, RDS or SG policies. The training operator performs cloud changes in the Huawei console and captures evidence.
- Database RDS passwords, if entered, are saved locally in `data/rds.json`, not encrypted at the application layer. Do not enter real credentials over plain HTTP. Prefer lab-only RDS accounts and HTTPS gateway or trusted private access.
- Prometheus UI is exposed through the proxy for training, without authentication. It can reveal operational metrics. Do not enable this arrangement for production.
- Queue demonstrations are intentionally simple: worker sudden death may leave a job in `processing`. This is an *at-least-once demonstration*, not a production-grade reliable message bus with dead-letter queues and poison-message handling.
- To recover from an old v5 project, install v6 in its own new folder. Old v5 `.env` passwords are not used. To migrate valuable data, back up and copy `data/` manually, then chown UID 10001.

## Verify

```bash
sudo docker compose config -q
sudo docker compose ps
curl -fsS http://localhost/healthz
curl -fsS http://localhost/api/architecture
curl -fsS http://localhost/metrics | head
sudo bash scripts/smoke-test.sh
```

**Validation scope:** Python syntax and unit/API tests, JS syntax, YAML/JSON parsing, Nginx syntax and Bash syntax may be run before packaging. Full Docker image pulls/start and Huawei ECS network connectivity must be verified on the target server. This distribution is not represented as already tested on Huawei cloud.
