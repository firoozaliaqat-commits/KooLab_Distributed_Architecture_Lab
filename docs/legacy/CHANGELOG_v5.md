# V5 — Classroom HTTP reporting, without extra Quick Tunnel

- Removes the Cloudflare Quick Tunnel service dependency causing confusing independent 502s.
- Allows the Student Progress token form on the direct ECS HTTP URL for authorized disposable classroom instances.
- Preserves the independent Proxmox instructor tracker (no server change), all RDS/ELB/Auto Scaling/Bandwidth/Security functions and student evidence workflow.
- Fixes event identifier generation on insecure HTTP origins where `crypto.randomUUID()` is unavailable.
- Adds authenticated `/api/tracker/diagnostics` + web UI action to test HTTPS connection to instructor `/healthz` without revealing a token.
- Preserves HTTPS verification between ECS reporting relay and instructor tracker.
- Adds specific errors when the central tracker API fails even though its health endpoint may work.
- **Caveat:** direct HTTP is unencrypted for browser-to-ECS passwords/tokens. Use limited, temporary classroom tokens only and revoke them after class.
- For existing v4 deployments, `install.sh` rebuilds only this Compose project web service; it never prunes data or deletes volumes.
