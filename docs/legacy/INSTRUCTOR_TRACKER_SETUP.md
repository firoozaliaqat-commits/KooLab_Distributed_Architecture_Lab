# Instructor Setup — connect KooLab Elastic & Security v3 to existing KICS Tracker v1

The new student ZIP **does not replace or modify the instructor tracker** on `192.168.100.146:8787`. It uses the tracker v1 APIs already shipped in `KICS_Cloud_Lab_Tracker_Proxmox_v1.zip`.

## One-time tracker setup

1. Open `https://huawei.stackcrm.online/admin` (or the secure LAN address).
2. Import or register your students in the **central tracker**, then distribute each **personal token** privately.
3. Create lab using the exact code `KOOLAB_ELASTIC_SEC`; title: **Huawei Elastic Computing & Cloud Security Practical**.
4. Create these **exact** milestone keys on that lab, in any order:

| Key (must match exactly) | Instructor milestone title | Meaning / grading |
|---|---|---|
| `ecs_app_ready` | ECS Docker application running | Application verification responded |
| `rds_connected` | Authenticated RDS connection | Connection saved, RDS ping succeeded |
| `rds_write_read` | Database read/write test | SQL write and refreshed list |
| `elb_distribution` | ELB backend distribution | Node sampling only; check ELB console health |
| `scaling_test` | Auto Scaling observed | CPU stress alone is insufficient; require AS action record |
| `bandwidth_test` | EIP bandwidth probe | Probe alone is insufficient; require Cloud Eye EIP metrics |
| `security_checks` | Local container security | Inspect security audit and any warnings |
| `cloud_security` | Security Groups, IAM & exposure | Check actual Huawei console permissions and port rules |
| `lab_report` | Evidence report | Review screenshots, timestamps and JSON export |

The student app reports `passed` only for `ecs_app_ready` and `rds_connected` (and only if live local checks succeed). All other milestones are marked `evidence`, not independently certified. The central tracker keeps instructor-approved and student-reported progress **separate**.

## Student deployment

Send `KooLab_Elastic_Security_Lab_Student_Ready_v3.zip` directly to students. Instruct them to run `sudo bash install.sh` inside the project directory. Each ECS produces its own local lab password and `APP_SIGNING_SECRET`.

V5 classroom mode permits student linking on the ECS HTTP EIP with a temporary, restricted classroom token. This is not encrypted on the browser-to-ECS hop. The ECS relays outbound to the central tracker using HTTPS. Rotate student tokens after the class.

## How auto reporting works

- Student authenticates to the existing app UI with the local lab password.
- Through trusted HTTPS or local SSH tunneling, they enter their tracker student token in the Student Progress tab.
- Token stays in **browser sessionStorage only**, not in the project ZIP, ECS environment, RDS, SQLite, Docker volumes, screenshots or exported JSON.
- Application relays requests server-to-server to the configured `TRACKER_URL` via HTTPS and standard TLS certificate verification, without forwarding token in URL query strings or logs.
- `/api/tracker/me` verifies student identity and lab code.
- `/api/tracker/start` records a started event.
- `/api/tracker/event` records an allowlisted milestone event with an idempotency ID.
- Tracker v1 always treats these lab-agent events as evidence pending instructor verification.

The live app's base reporter URL is controlled by ECS `.env` and defaults to `https://huawei.stackcrm.online`. Students cannot point it at arbitrary addresses using the UI.

## Suggested instructor scoring (100 marks)

- ECS app running: 10
- RDS connection: 15
- SQL read/write: 10
- ELB distribution: 15
- Auto Scaling action: 15
- Bandwidth measurement: 10
- Local security: 10
- Cloud security / SG/IAM: 10
- Final report: 5

For full credit on ELB, scaling, bandwidth and cloud security, open the actual Huawei KooLabs console evidence. The application does not have delegated Huawei API access and cannot authoritatively verify Security Group rules, Internet exposure, ELB health or actual Auto Scaling events.

## Important operating limitations

- Tracker v1 does NOT accept uploaded screenshots/JSON evidence in its API; students submit references and share actual files using your usual class submission workflow.
- An auto-report request may fail if KooLabs ECS cannot make outbound HTTPS requests to the tracker. App functionality continues and local JSON evidence still works.
- Never share a single student tracker token among students. Tokens are not part of the ZIP.
- Do not share Huawei RDS/MySQL passwords, IAM secrets or tracker admin credentials with the student application.
- Test one student token and one clean ECS before sharing the assignment.
