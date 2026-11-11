# KooLab v6 Validation Report

## Completed in the packaging environment (2026-11-10)

- Python API/regression suite: `python -m pytest -q` — **5 tests passed**.
- Python static compilation: `python -m compileall -q app` — **passed**.
- Browser JS syntax: `node --check app/static/app.js` — **passed**.
- Ubuntu shell syntax: `bash -n install.sh scripts/smoke-test.sh` — **passed**.
- Compose/Prometheus/Grafana YAML and Grafana dashboard JSON parsing — **passed**.
- Nginx configuration syntax (hostnames substituted for local loopback) — **passed** using `nginx -t`.
- Live local HTTP integration: 3 independent Uvicorn processes behind a running Nginx process; 60 identity calls produced exactly 20 requests at each of app1/app2/app3 — **passed**.
- Live local HTTP failover: after app2 was stopped, 40 identity calls continued on app1/app3 — **passed**.
- Live concurrent writes: 30 concurrent SQL message writes to shared local SQLite through Nginx — **passed**.
- Redis queue and cache routes tested using a fake in-memory Redis substitute, including MISS/HIT and enqueued job API — **passed**.
- Instructor tracker: same-origin request and valid student-token requirement preserved, with upstream tracker stubbed — **passed**.

## Not verified here

- **Docker daemon/Compose runtime** (not installed or accessible in this environment), image tag download/pull and full nine-service startup.
- Live Redis server persistence and queue worker processes against actual Redis.
- Grafana dashboard rendering and Prometheus scraping inside their official containers (configuration syntax verified but actual images not started).
- Actual Huawei Ubuntu ECS deployment, EIP/firewall security groups, RDS/ELB/AS/Cloud Eye controls and external instructor tracker.

These are target-ECS acceptance criteria, not completed validations. After `sudo bash install.sh` run `sudo bash scripts/smoke-test.sh`. Test Grafana `http://ECS_EIP/grafana/` and the HTTP settings in your actual browser. The first deployment requires outbound internet; if official Docker tags or Python package versions are unavailable in the region, use instructor-approved mirrors and retry after updating those explicit image references.
