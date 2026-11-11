# KooLab Elastic & Security Lab — v3 Student Progress Edition

This is a minimal additive update of the uploaded v2 ZIP. It preserves the original pages, endpoints and labs (RDS wizard, RDS messages, ELB, Auto Scaling, bandwidth, security audit, checklist and evidence JSON export).

## Additive files/functions

- `app/tracker.py` HTTPS-only outbound integration to the existing instructor tracker.
- `app/main.py` adds student identity check, started event, and controlled milestone reporting endpoints.
- `app/static/index.html`, `.js` and minimal existing styling provide a Student Progress page with token pairing, status, recent events and evidence notes.
- `.env.example` and bootstrap `.env` include tracker origin and lab code defaults.
- `INSTRUCTOR_TRACKER_SETUP.md` and `STUDENT_QUICK_START.md` explain the classroom workflow.
- `tests/test_tracker.py` includes mocked tracker contract/security tests.

## Security boundaries

- Does not open any new Docker ports; still defaults to host TCP/80 only.
- Rejects student token pairing when browser uses a public plain-HTTP lab address.
- Student tracker tokens are not stored on the ECS; browser sessionStorage only.
- Backend only contacts the configured HTTPS tracker host; no student-controlled arbitrary URLs.
- No Huawei API credentials, private keys, RDS passwords or administrative tracker tokens are requested for reporting.
- Scaling and security cloud milestones remain instructor-reviewed; no false automatic pass.

## Validation scope

- Original API suite + integration suite run in a local Python test environment.
- Syntax checked for backend and browser JS.
- Docker build and Huawei Cloud-to-tracker end-to-end networking cannot be tested in the offline build environment. Test on an instructor ECS first.
