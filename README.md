# Vision

**Jarvis controls the house. Vision understands the house.**

Read-only observability for Home Assistant OS, with optional Anthropic and OpenAI
intelligence. Local monitoring works without AI, cloud accounts or API keys.
MIT licensed. **0.3.0-dev.1 — local daily-experience development preview**; see [validation](docs/VALIDATION.md) for version-bound
qualification evidence and [releases](https://github.com/Patrick1610/vision-homeassistant/releases)
for publication status.

Today shows up to three meaningful priorities with friendly local names and one
first manual check. Follow a problem's facts, declared dependencies, uncertainty
and later observations. Optional Dutch/English intake and gradual per-problem
choices keep importance, known issues and usual behaviour independent. Cancel
saves nothing; preferences never implicitly acknowledge worsening or reset an
existing device-policy baseline. All these workflows work without AI.

This Stage A preview keeps the existing device charts, history and expert
investigation/exact-preview routes. One-click orchestration and v4 findings belong
to the separately reviewed Stage B and are not part of this preview. AI remains off
by default; existing privacy, provider options and budgets are retained. Device
measurement starts at the first device-reliability upgrade and survives later
updates; older entity history cannot establish historical device membership.
Qualification and scoped limitations are recorded in validation.

## What it does

- Unique registered-device trends, clipped device-hours, coverage gaps and a
  fully covered stable-subset burden comparison. Partial and unknown evidence
  stay separate; diagnostic/update/disabled entities do not prove device failure.
- Persistent local device expectations and performed-check markers, with later
  observational validation; no automatic repair, ping or network diagnosis.

- Devices and entity inventory; unknown/unavailable observations, duration,
  recurring incidents and time-limited exceptions for expected offline behavior.
- Automation details, observed trigger events, retained trace outcomes,
  execution statistics and structural dependency summaries.
- Repairs and grouped warning/error observations with local incident history.
- Prioritized local cases with evidence, manual checks and timelines; local
  known/expected/snoozed attention states preserve the underlying observations.
- Sanitized automation steps, run-bound configuration comparisons, structural
  changes and typed dependency links, with explicit gaps and uncertain outcomes.
- Filtered, paginated history without copying Home Assistant Recorder data.
- Optional focused audits, incident/automation investigations and problem-specific
  template, availability, reference, mode, condition, wait and communication tasks,
  with concrete manual checks, validation, counterevidence and unknowns.
- Exact registered-device availability investigations include own healthy members,
  missing coverage and separately labeled integration correlation. No representative
  entity, device-control command or invented network cause.
- Human-started public research from official HA docs and a closed GitHub catalog,
  with source/version limits, referenced manual steps and observational validation.
  Reddit is unavailable without authentication; research never runs automatically.
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
Incident and history tables show bounded recent subsets; the Overview inventory
counts and per-automation statistics cover their underlying observed data.

AI defaults to compact typed summaries without local HA source identifiers or source free text.
Scoped follow-ups can include sanitized earlier provider conclusions in their preview.
Local-only never sends; diagnostic requires explicit richer consent and uses
bounded redacted/pseudonymous evidence. Inspect each exact provider request before
sending; redaction cannot guarantee removal of all personal data. Scoped follow-ups
keep the original frozen evidence and require their own preview. Models can be
wrong; validate every recommendation manually. See [privacy](PRIVACY.md).

## Development

```sh
python3.14 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-test.txt
.venv/bin/python -m pytest
npm ci --ignore-scripts --no-fund --no-audit # test-only; Node.js 22+
npm test
.venv/bin/ruff check .
.venv/bin/ruff format --check vision tests
node --check vision/static/app.js
docker build --build-arg BUILD_ARCH=amd64 -t vision:0.3.0-dev.1 .
```

Run locally (loopback only): `VISION_DATA=./data .venv/bin/python -m vision`.
With no HA token, the UI honestly shows disconnected/empty observations. For
development use private environment variables `HA_URL` and `HA_TOKEN`, and a
private `VISION_OPTIONS` JSON file. Never put credentials in shell history or Git.
The production app gets its HA token automatically from Supervisor.

Architecture/specification: [docs](docs/ARCHITECTURE.md), [requirements](docs/VISION_SPEC.md).
Contributions: [CONTRIBUTING.md](CONTRIBUTING.md). Privacy: [PRIVACY.md](PRIVACY.md).
Vision is independent of Home Assistant, Marvel, Anthropic and OpenAI.
