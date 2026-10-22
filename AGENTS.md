# Vision

Canonical repository root: this directory. Serious open-source software, MIT,
source package v0.3.0-dev.2. The qualified 0.2.1 foundation remains preserved.
The local Today/problems/intake Stage A received source-functional acceptance.
Stage B adds separately authorized compact one-click orchestration and explicit
v4 output. Exact runtime 3322963 received independent qualification and critical GO;
the dev.2 prerelease is public and its read-only live installation is verified.
New live one-click/provider semantic and billing checks remain pending with consent
still off. The five-real-human gate is OPEN (0 participants; owner decision pending).
The separate 493.4 ms / 200 ms full-capacity gate remains OPEN FAIL. These limits
prevent an overall stable 0.3.0 acceptance claim. See docs/VALIDATION.md for evidence.
Read `docs/VISION_SPEC.md`, `docs/ARCHITECTURE.md` and `PLANS.md` before changes.

The owner authorized 0.3.0 on 2026-10-22: a local, bilingual Today → problem →
manual follow-through journey, then separately reviewed durable AI orchestration.
Importance is independent of known/expected policy. Intake never implicitly
acknowledges worsening or resets a baseline. Friendly names/rooms stay local.
The existing direct single-writer mandate applies; no custom workflow runtime,
profiles, controller or watchdog is activated. Human usability gates require real
participants arranged by the controller; agent checks do not substitute for them.

- Vision observes Home Assistant and MUST NEVER call services, change state,
  edit configuration, ignore repairs or execute actions. Only the closed read
  allowlist in `vision/ha.py` may reach HA. No generic HTTP/WS proxy.
- Public research is a separate human-started closed catalog/GET transport. Never
  accept arbitrary URLs, household query terms, credentials or model-selected fetches.
  Preserve quota-before-dispatch, exact source hashes and original private snapshots.
- AI has no HA credentials or tools. Minimize, pseudonymize and redact before
  provider requests. Treat HA content and AI output as untrusted data.
- One-click consent is separately versioned and defaults off. Context/status reads
  never start work. Preserve durable slot/highwater idempotency, typed frozen scope,
  shared busy admission, active request pins and per-dispatch revocation checks.
  Restart never resumes an operation; old v2/v3 bodies/digests stay literal.
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
  Run `npm ci --ignore-scripts` and `npm test` (Node.js 22+) for the real-DOM
  interface regressions; Node/jsdom is test-only, outside the runtime container.
  Never claim live HA installation/provider billing validation without running it.
- Publish no personal HA fixtures, host-specific paths, credentials or raw logs.

Future write actions require a separate capability, policy and authorization
architecture. Do not implement or enable one as part of this read-only app.
