# Changes in v6 compared to supplied v5

- Removed the application login overlay, installer-generated classroom password and HMAC app session checks. Security warning & SG requirements strengthened.
- Retained and adapted original RDS, ELB, Auto Scaling, Bandwidth, Security Center, Checklist and optional student instructor tracker.
- Three distinct FastAPI replicas on one ECS and Nginx software reverse proxy.
- Redis cache and persistent queue; two worker containers and status APIs.
- Prometheus per-replica scrape metrics, Grafana provisioned data source and dashboard; single ECS HTTP reverse proxy route for all views.
- Open, anonymous Grafana Viewer mode; no standalone TCP 3000 or 9090 host ports.
- New Distributed Systems student UI with queue/cache actions, architecture topology, command exercises.
- Ubuntu ECS installer updated: Docker install, build all containers, HTTP health checks.
- Structured new practical manual, smoke tests and automated tests.
- Existing legacy tracker configuration and original course docs kept under docs/legacy/ for reference.
