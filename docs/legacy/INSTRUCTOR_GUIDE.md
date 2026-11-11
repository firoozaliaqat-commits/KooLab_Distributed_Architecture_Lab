# Instructor Guide — Huawei Highly Elastic Service System + Cloud Security (v2)

## Learning objectives

Students use a preinstalled Ubuntu ECS named **ecs-web**. The app replaces Discuz! with a modern containerized test portal; it is **not an acceptable substitute if the formal lab assessment requires Discuz! specifically**. All application operations can be performed from the browser UI. Changing Huawei-managed infrastructure (VPC, RDS instance creation, ELB, AS group/policies, IAM, security groups) still requires the Huawei Console or an independently authorized cloud API. This app deliberately cannot and does not claim to create those resources on your behalf.

## Deployment prerequisites

* Ubuntu ECS x86_64/arm64 (Ubuntu 22.04/24.04/26.04 where official Docker packages are available)
* An EIP bound to the ECS (until moved to ELB), outbound internet and DNS for Ubuntu APT, Docker Hub and PyPI
* Security group allows TCP :80 from authorized classroom clients; this is configured **in Huawei Console**
* Sufficient disk space (suggest ≥6 GB free) and CPU/RAM for Docker build
* Docker's own published-port iptables handling can bypass some UFW expectations; verify public attack surface using Huawei SG evidence
* SSH/console access to recover from installer or connectivity errors

## Day sequence with proof requirements

### Phase 1 — ECS, subnets and RDS

1. Confirm `vpc-primary` and `subnet-web` are available. Create `subnet-db`, CIDR `192.168.2.0/24`.
2. Set up `sg-db`: MySQL inbound 3306 **only** from approved ECS security group(s), if supported by your RDS service, or scoped private subnet sources. The original guide's restriction to the original single ECS IP can fail after Auto Scaling creates additional IPs.
3. Purchase a supported MySQL RDS (the original exercise used MySQL 5.7 primary/standby and port 3306; follow currently available product options). Attach to subnet-db.
4. Open `http://ECS_EIP:80`. Sign in with the one-time lab access password printed by installer.
5. Use **RDS Connection → Test → Save & connect**. When initializing database use a user permitted to create database/tables, then rotate to a least-privilege app user before taking an IMS image.
6. Insert a message in the browser. Confirm stored MySQL row and TLS indication. Note the app uses SQLite fallback before RDS connection: this is **not shared** across ECS replicas.

### Phase 2 — Elastic Load Balance

1. Unbind EIP from ECS. Create ELB `elb-web` and bind the same EIP. Use listener `listener-web`, TCP/80, backend group `server_group-web`, TCP/80 and weighted round robin.
2. Add `ecs-web` and later scaled ECS replicas on private IP port 80; confirm **actual backend health** in Huawei.
3. Open the app through the ELB EIP and run **Load Balancer → Run ELB sample**. Multiple node names provide evidence of distribution, but browser TCP keepalive and an ELB routing policy may cause one backend to dominate; one node observed does **not** prove a fault.
4. For failover, remove or stop one authorized backend under instructor supervision and show that the other backend still serves HTTP. Restore it. Do not stop the only backend.

### Phase 3 — Elastic Compute and Cloud Eye

1. After setting up RDS, create IMS `image-web`. The local `.env`, local app access secret and `/data/rds.json` are included in disk images and should be used **only in an isolated classroom**, not distributed broadly.
2. Create AS configuration `as-config-web`: use the image, security group `sg-web`, no separate EIP. Each replicated ECS must boot Docker (`systemctl enable docker`) and load the service with Docker `restart: unless-stopped`.
3. Create AS group `as-group-web`: min=1, expected=2, max=5. Link to ELB backend TCP/80. Choose eligible VPC/subnet/AZ.
4. Create alarm-based scaling policies: CPU >70% in two consecutive 5-minute periods → add 1 instance; CPU <30% → remove 1 instance; cooldown 300 seconds.
5. **Important:** run the CPU workload from the browser UI served by an ECS that is actually **inside the AS group**. A test on the original standalone ECS does not prove AS CPU policy behavior. When the page is served through a load balancer, the exact node targeted by a control request may vary; instructor should use a private-IP management path or verify the returned `node` each time.
6. Use **Auto Scaling → Start controlled CPU load**. Two workers for up to 900 seconds. Monitor the actual ECS CPU metric and AS scaling action on Huawei Console. CPU limits/capacities can cause different results.
7. Verify new ECS starts the application and connects to shared RDS. Verify **actual group instance count**, not just UI identity sampling.

### Phase 4 — Bandwidth scaling

1. Under Auto Scaling → Bandwidth Scaling, select the **ELB-bound EIP**, not the original standalone ECS.
2. The source exercise sets three consecutive 5-minute inbound bandwidth measurements above `18 bit/s` with set-to `30 Mbit/s`; check whether the live console unit and monitoring metric match because the original value is extremely low.
3. Run **Bandwidth Lab → Inbound upload** from a browser outside the ECS to create inbound EIP traffic. Download produces **outbound** EIP traffic. This UI intentionally caps requests and payloads, so an alarm requiring three 5-minute periods is unlikely to be reproducible solely by one short browser probe. Capture actual Cloud Eye observations and bandwidth policy effect separately.

### Phase 5 — Operations

Use Huawei Console to manually add instances into the AS group, turn on instance protection, modify an AS configuration, configure SMN notifications and capture success/failure events. Use the browser **Student Lab Assessment** checklist to note the evidence file names and export a JSON report.

### Security extension (same week)

* Threat model: ECS/public EIP/ELB/RDS, credentials, cloud configuration, and outbound API access.
* RDS TCP 3306 limited to authorized private sources, never `0.0.0.0/0`.
* ECS HTTP/80 allowed from authorized clients; SSH management limited to trusted IPs or a safer remote-console path. Do not assume UFW overrides Docker published ports.
* Web management APIs require a one-hour signed token and have bounded stress/network operations; login rate limited. Students should test unauthorized writes (`401`), session expiry, and security headers.
* Container runs UID 10001, dropped capabilities, `NoNewPrivs`, read-only root filesystem and bounded CPU/memory. App has no Docker daemon socket and no cloud API credentials.
* TLS: app serves **plaintext HTTP** on port 80 for source lab compatibility. Login and RDS password could be intercepted on public networks. For any real deployment, terminate HTTPS with a certificate and restrict management access, or run inside an isolated lab environment. Use a dedicated database account. Never share real `.env`, passwords or DB credentials in student images, screenshots or submitted ZIPs.
* The in-app **Security Center** verifies local process properties and actual RDS transport, but cloud SG/IAM policies require independent Huawei Console evidence.

## External validation after Docker starts

From another authorized computer on a different network:

```
curl -i http://ECS_EIP/healthz
curl -i http://ECS_EIP/api/status
curl -i -X POST -H 'Content-Type: application/json' -d '{"body":"test"}' http://ECS_EIP/api/messages
```

Expected: `200 OK` for health, JSON status, and `401` for unauthenticated message posting. Never conduct unsolicited scans against other users or networks.

## Instructor limitation and score guidance

The browser portal tests **actual RDS connectivity, SQL CRUD, web node identities, bounded CPU load, bounded traffic and local security controls**. It cannot verify Huawei billing, real AS group actions, ELB backend health, security-group rules, Cloud Eye metrics or IAM privileges without access to relevant cloud APIs. Require screenshots/metrics from the actual Huawei Console. Suggested grading: ECS+RDS 20%, ELB 15%, Auto Scaling 25%, EIP bandwidth 10%, security 20%, documentation 10%.
