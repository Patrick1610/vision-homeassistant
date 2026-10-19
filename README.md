# Vision

**Jarvis controls the house. Vision understands the house.**

Read-only observability for Home Assistant OS, with optional Anthropic and OpenAI
intelligence. Local monitoring works without AI, cloud accounts or API keys.
MIT licensed. Version 0.1.0 release candidate; see [validation](docs/VALIDATION.md)
for what has actually been tested and release status.

## What it does

- Devices and entity inventory; unknown/unavailable observations, duration,
  recurring incidents and time-limited exceptions for expected offline behavior.
- Automation details, observed trigger events, retained trace outcomes,
  execution statistics and structural dependency summaries.
- Repairs and grouped warning/error observations with local incident history.
- Optional daily/manual audits, incident hypotheses and automation analysis,
  using a shared validated diagnosis format with evidence references.
- Primary/backup AI providers, rate-limit backoff, technical failover, primary
  recovery and separately authorized budget failover. Token/cost history persists.
- Responsive Ingress interface: Overview, Devices, Automations, Issues,
  Intelligence, History and Settings.

**No service calls, state changes, configuration edits, repair actions or AI
tools.** Only a closed list of read operations is implemented. The HA token itself
has broader permissions; the boundary is enforced in application code, not by a
server-issued read-only token. See [security](SECURITY.md).

## Install

Requires HA OS with Supervisor, amd64 or aarch64. Add the public repository
[https://github.com/Patrick1610/vision-homeassistant](https://github.com/Patrick1610/vision-homeassistant)
to **Settings → Apps → App store → ⋮ → Repositories**, install Vision, start it,
then open its web UI. The Supervisor builds the pinned image on the device.

On first opening, Vision is locked. Copy the Ingress user ID displayed on the
locked page into `allowed_user_ids` in the app configuration, save, and restart.
Only grant access to people authorized to see sensitive diagnostics. AI defaults
off. Complete instructions: [installation](docs/INSTALLATION.md) and
[configuration](DOCS.md).

## Interpretation and limits

Triggering is **not** successful completion. Traces distinguish success, condition
stop, explicit stop, failure, running and unknown. Traces are limited by HA's own
retention, component availability and admin permissions. A possibly unused
automation is a hypothesis. Vision cannot reconstruct missed events during
downtime. Availability segments are measured observations, not guaranteed physical
outage counts. A disappearing log entry does not prove a repair.

AI receives a bounded typed evidence bundle with anonymous evidence IDs, counts,
availability and execution summaries. Source names, entity IDs, raw logs,
configuration values and credentials stay local. This protects privacy but limits
the specificity of root-cause hypotheses. Preview the exact bundle before running
an audit. Models can be wrong; validate every recommendation manually.

## Development

```sh
python3.14 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-test.txt
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check vision tests
node --check vision/static/app.js
docker build --build-arg BUILD_ARCH=amd64 -t vision:0.1.0 .
```

Run locally (loopback only): `VISION_DATA=./data .venv/bin/python -m vision`.
With no HA token, the UI honestly shows disconnected/empty observations. For
development use private environment variables `HA_URL` and `HA_TOKEN`, and a
private `VISION_OPTIONS` JSON file. Never put credentials in shell history or Git.
The production app gets its HA token automatically from Supervisor.

Architecture/specification: [docs](docs/ARCHITECTURE.md), [requirements](docs/VISION_SPEC.md).
Contributions: [CONTRIBUTING.md](CONTRIBUTING.md). Privacy: [PRIVACY.md](PRIVACY.md).
Vision is independent of Home Assistant, Marvel, Anthropic and OpenAI.
