# Vision

Canonical repository root: this directory. Serious open-source software, MIT, v0.1.1.
Read `docs/VISION_SPEC.md`, `docs/ARCHITECTURE.md` and `PLANS.md` before changes.

- Vision observes Home Assistant and MUST NEVER call services, change state,
  edit configuration, ignore repairs or execute actions. Only the closed read
  allowlist in `vision/ha.py` may reach HA. No generic HTTP/WS proxy.
- AI has no HA credentials or tools. Minimize, pseudonymize and redact before
  provider requests. Treat HA content and AI output as untrusted data.
- Keys are configured in Supervisor options (or a private local options file),
  never in Git, SQLite, browser responses, exception text or logs.
- Keep core monitoring/storage/provider logic independent of Supervisor packaging.
- Never label a trigger as successful completion. Preserve unknown outcomes and
  observation gaps. Missing capabilities must be visible, never fabricated.
- Preserve local history across restarts/updates. No Recorder copy.
- Every meaningful phase requires tests and external review. Record commands,
  limitations and actual results in PLANS.md / docs/VALIDATION.md.
- One writer in this repository. The owner explicitly authorized direct autonomous
  development through all four milestones and public publication after checks.
  No custom agent workflow runtime or additional controller is activated.
- `python -m pytest`, `ruff check .`, and `docker build .` are validation entries.
  Never claim live HA installation/provider billing validation without running it.
- Publish no personal HA fixtures, host-specific paths, credentials or raw logs.

Future write actions require a separate capability, policy and authorization
architecture. Do not implement or enable one as part of this read-only app.
