# KooLab v6 | Instructor & Student Distributed Architecture Practicals

## Mapping to the supplied Huawei distributed-architecture slides

This lab makes visible the Huawei slides' **request distribution**, **loose coupling**, **ELB health checks**, **stateless application servers**, **DMS queues**, **reliability**, **performance**, **security**, **cost-effectiveness** and **maintainability**. Locally we use Nginx as an ELB **analog** and Redis as a DMS **analog**. The analogs do not claim Huawei-managed capabilities.

The five solution-design principles to evaluate are: **Security, Reliability, Performance, Cost-effectiveness, Maintainability**.

### Lab A — Simulated stateless web service / request distribution (15 min)

1. Open `http://ECS_EIP/` and click **Load Balancer**. Run 40 identity samples. Record app1/app2/app3 counts.
2. Open Grafana `http://ECS_EIP/grafana/`, panel **Requests per second by replica**; increase requests and watch the timeseries.
3. Explain why per-replica request counter is independent and why local `data/` or RDS must be shared. Nginx's least-connections algorithm isn't Huawei ELB weighted round robin; compare algorithms from the slides.
4. **Evidence:** screenshot of counts + Grafana requests/s. Do not assert '3 ECS instances'—there are only 3 application containers.

### Lab B — One-backend failure and recovery (15 min)

```bash
sudo docker compose stop app2
sudo docker compose ps
```

Run the request sampling again. Monitor Prometheus `up{job="koolab-replicas"}` and Grafana 'Prometheus scrape up status' (allow 10–20s). Restore using `sudo docker compose start app2`. Verify recovery and 3 backend identities. Expect proxy may briefly return errors while passive health status is being learned. **Evidence:** before/after Prometheus and request counts. If *entire ECS fails*, exercise fails: identify this SPOF.

### Lab C — Asynchronous processing, loose coupling & queue buffering (20 min)

```bash
sudo docker compose stop worker1 worker2
```

Enqueue 5 tasks in **Distributed Systems**. Observe `queued=5` (or another bounded value), completed unchanged; reload page. Open Grafana **Pending async jobs**. Restore workers:

```bash
sudo docker compose start worker1 worker2
```

Wait for processing and `completed` increase. The producers do not need to know which worker processed a job. **Evidence:** queue backlog before and after; explain decoupling and why failure recovery of in-progress messages needs work in production.

### Lab D — Distributed cache (10 min)

Open **Distributed Systems** and fetch key `lesson-1`. First call returns `MISS` and approximate 180ms synthetic computation. Fetch same key immediately; `HIT` should be faster. Try other key; first call MISS. Wait 60sec; first key should MISS again. Observe Grafana cache hits vs misses. **Evidence:** screenshots showing hit/miss and latency; discuss cache stampede and invalidation risks.

### Lab E — Prometheus / Grafana operations (20 min)

- Prometheus targets: `http://ECS_EIP/prometheus/targets`
- Grafana dashboard: `http://ECS_EIP/grafana/d/koolab-distributed/koolab-distributed-architecture-lab`
- Query `up{job="koolab-replicas"}`: three per-replica scrape targets.
- Query `sum by(instance) (rate(koolab_http_requests_total[1m]))`: request rate.
- Query `max(koolab_queue_pending)`: backlog.
- Query `sum by(result)(rate(koolab_cache_requests_total[2m]))`: hits and misses.
- **Evidence:** 4 screenshot panels, one PromQL expression, analysis of fault recovery.

### Lab F — Real Huawei Cloud deployment (advanced; optional)

1. Create independent ECS instances (prefer different AZs where available); deploy app container with distinct `LAB_NODE_ID`, private networking and externally shared RDS.
2. Huawei ELB health checks each ECS `/healthz`. For real ECS architecture, use Huawei managed DNS/ELB rather than local Nginx. The source deck explicitly discusses cross-AZ ELB and automatic backend health checks.
3. Do **not** mount local SQLite between ECS hosts; use Huawei RDS for shared data and managed DCS/DMS where appropriate.
4. Verify backend health and failover in Huawei Console; record differences between software demo and managed Huawei service. Cross-AZ support / cost is region and purchase dependent.

## Student submission criteria (100 points)

| Exercise | Points | Required evidence |
|---|---:|---|
| A. Load balancing | 20 | Three replica IDs and Prometheus rates |
| B. Backend failure | 20 | `up=0` app2, recovery to 1, no sustained outage |
| C. Async queue | 20 | Workers stopped, backlog, worker recovery |
| D. Cache | 15 | MISS and HIT timings/TTL evidence |
| E. Observability | 15 | Four Grafana panels and one PromQL query |
| Design review | 10 | Identify four SPOFs and five design principles |

## Instructor stress tests / known limits

**Security:** app deliberately has no login. **Cloud SG restriction required**; do not place this directly on unrestricted public EIP. Student-tracker relay still requires student-specific credentials. Existing course module credentials must be disposable.

**Availability:** the single ECS, proxy, shared Redis, SQLite, network, persistent volumes and power are SPOFs. Restarting any host may interrupt all lessons. With Redis worker kill mid-job, `processing` may retain a message; the lab does not implement full redelivery/dead letter queue (intentional teaching extension).

**Performance:** Nginx software proxy uses `least_conn`, not the Huawei console's ELB weighted round robin option; no claim of real ELB weights. The app CPU stress is container bounded and may not raise host CPU enough to trigger Huawei AS alarms.

**Maintainability & cost:** nine containers have resource requirements; use at least 4 vCPU/8GB RAM, 12GB disk and cleanup via `sudo docker compose down` at end. For complete deletion of class metrics/data use `sudo docker compose down -v` **only after instructor approval**, because it destroys queue, Grafana and Prometheus volumes; host `data/` survives that command.
