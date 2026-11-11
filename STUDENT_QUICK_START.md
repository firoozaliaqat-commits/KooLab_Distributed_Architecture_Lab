# Student quick start — KooLab Distributed Architecture Lab v6.1

## Prerequisites

- Huawei ECS with **Ubuntu 22.04 or 24.04**; **4 vCPU / 8 GB RAM recommended**; at least **12 GB free disk** and reliable outbound HTTPS for Docker image pulls and Python packages.
- ECS with public EIP; security group allow **TCP 80 from authorized classroom source IPs ONLY**. SSH (22) remains under instructor control; **do not expose 3306, 6379, 9090 or 3000 to the Internet**.
- Download this ZIP to your student ECS, for example `~/KooLab_Distributed_Architecture_Lab_v6_1.zip`.
- The user interface **has no application password**. This is not a production deployment.

## Install (two commands after unzip)

```bash
sudo apt-get update && sudo apt-get install -y unzip
unzip -o KooLab_Distributed_Architecture_Lab_v6_1.zip
cd KooLab_Distributed_Architecture_Lab_v6_1
sudo bash install.sh
```

The installer installs Docker Compose if necessary, builds the application, starts 9 containers and checks web health. **No `.env` or passwords need to be created manually.** Internet is required for first-time downloads.

## Open in any browser (no application password)

- Web lab: `http://YOUR_ECS_EIP/`
- Grafana (anonymous read-only): `http://YOUR_ECS_EIP/grafana/`
- Prometheus: `http://YOUR_ECS_EIP/prometheus/targets`

If Grafana redirects to localhost, set `GRAFANA_ROOT_URL=http://YOUR_ECS_EIP/grafana/` in `.env`, then `sudo docker compose up -d --force-recreate grafana`. The host/port must match the actual browser URL.

## Six practical modules

1. **Reverse-proxy distribution:** Distributed Systems → Load Balancer → sample 40 requests. Check app1/app2/app3 identities, Nginx distribution, and Grafana traffic graphs.
2. **Backend fault/recovery:** `sudo docker compose stop app2`, repeat sampling, inspect Prometheus `up`, restart `sudo docker compose start app2`.
3. **Distributed async queue:** Stop workers using `sudo docker compose stop worker1 worker2`, enqueue 5 tasks, watch Redis backlog then `sudo docker compose start worker1 worker2`. Confirm completed count increases.
4. **Shared Redis cache:** Request `lesson-1` twice. Compare MISS (~180 ms) then HIT (fast). Wait 60 seconds for TTL expiry and try again.
5. **Observability:** Grafana panels for requests/s, p95 latency, scrape availability, HTTP 5xx, queue length, completed jobs, cache hit/miss, memory. Open Prometheus targets to see per-replica scrape results.
6. **Huawei extension:** Use optional RDS, real ELB, AS and Cloud Eye modules from the original project. **Three local Docker replicas do NOT equal three Huawei ECSs**. A standalone ECS failure still takes down this stack.

Full exercises and instructor marking: `docs/DISTRIBUTED_LABS.md`.

## Troubleshooting

```bash
sudo docker compose ps
sudo docker compose logs --tail 80 proxy app1 app2 app3 redis worker1 worker2 grafana prometheus
curl -i http://127.0.0.1/healthz
curl -s http://127.0.0.1/api/architecture
sudo docker compose up -d --build
```

**Security:** passwordless app allows message writes, bounded CPU tests and RDS configuration. Isolate the ECS with cloud security groups. Do not upload personal data, production credentials or real company secrets. The student instructor **tracker token is still required**, and is sent over insecure HTTP if the EIP URL is HTTP; only use disposable classroom tokens, or configure HTTPS before using tracker reporting.

## Repair an installed v6 project without losing data

If you installed the previous v6 ZIP and its web proxy failed, run the bundled repair from inside that original v6 folder (copy the repair script from v6.1 first), or edit the existing `docker-compose.yml` proxy service by adding:

```yaml
cap_add: [NET_BIND_SERVICE, SETUID, SETGID]
```

Keep its existing `cap_drop: [ALL]`. Then run:

```bash
sudo docker compose up -d --no-deps --force-recreate proxy
sudo docker compose logs --tail=50 proxy
curl -i http://127.0.0.1/healthz
```

Do not use `docker compose down -v`: this deletes named data volumes.
