# Vision specification

The initial functional baseline was delivered as v0.1.0. Presentation amendments
are recorded below; patch releases retain the same read-only functional scope.

Repository: `vision-homeassistant`. License: MIT. Public custom Home Assistant
app repository. Philosophy: **Jarvis controls the house. Vision understands the
house.** Vision's name refers to the fictional successor of J.A.R.V.I.S.; this is
an independent community project with no Marvel affiliation.

Vision must be useful locally without AI, and offer optional intelligence using
direct Anthropic and OpenAI connections. Generic HA OS / Supervisor support;
amd64 (including Odroid H3+) and aarch64. No entity names, hardware, ZHA, FRITZ!,
Enphase, NUT or third-party integration is required.

The initial reference environment is HA OS with Supervisor on an Odroid H3+ with
16 GB RAM, integrations such as ZHA, FRITZ!, Enphase and NUT, and extensive
heating/energy/appliance automations. The reference HA installation is called
Jarvis. The scope and results of live validation are recorded in VALIDATION.md.
No real entity names, addresses or installation credentials belong in this repo.

## Foundation and delivery

Python + FastAPI, SQLite in persistent `/data`, responsive web UI through HA
Ingress. HA WebSocket and REST transports use only predefined read operations.
The repository itself is the app build context; no second project root.
Include app metadata, reproducible dependencies, CI, tests, README, installation,
configuration, privacy/security documentation, MIT license, changelog and versioned
tag/release. Validate current official HA documentation before implementing APIs.

## Local monitoring

- Device and entity inventory, unknown/unavailable episodes, observed durations,
  recurrence and exceptions for expected offline behavior.
- Automation inventory, trigger observations and historical run statistics;
  retained HA trace summaries distinguish successful completion, condition stop,
  explicit stop, failure, running and unknown. Triggering alone proves no outcome.
  Expose observation coverage and possibly unused automations as hypotheses.
- Per-automation detail, trace evidence, incident history, analyses and structural
  configuration/dependency summaries. No action execution or config editing.
- Repairs and warning/error summaries, grouped recurrences, newly observed issues,
  severity and incident history. Spook/Watchman information may be observed as
  ordinary entities/issues but are never required dependencies.
- Preserve incidents, availability, execution summaries, exceptions, analyses,
  proposed improvements, model/token usage. Do not duplicate Recorder states.

## Intelligence

Both providers can be configured simultaneously, each with own key and model.
One provider-independent validated diagnosis schema: finding, evidence references,
severity, confidence/uncertainty, next step and validation method. Unsupported
causes are hypotheses. Reject unknown evidence references. No HA tools/tokens.

Daily audits (explicitly enabled), manual audits, incident/root-cause and
automation analysis, supported optimization proposals. Use a bounded, minimized
evidence bundle and consistent schema for both providers. Local monitoring never
requires AI. All transmissions require AI opt-in.

Primary/backup priorities, technical failover, rate-limit retries/backoff and
primary recovery probing on subsequent analyses. Budget exhaustion cannot cause
failover without separate permission. Persist per-provider/model token usage,
estimated USD costs and conservative reservations for uncertain billing.
User-configured rates and daily/provider + monthly/global ceilings; reject
unpriced requests. These are application estimates, not a provider billing cap.

## Interface

Overview, Devices, Automations, Issues, Intelligence, History, Settings. Current
health reflects connection/capability coverage; recent incidents, latest audit
and recommendations. Searchable inventories, automation detail, mobile layout.
Settings display masked configuration; credentials are entered via Supervisor.
Expected-offline exceptions change only Vision's own database.

The interface uses a light white/warm-white base. Vision's visual identity is
deep red for navigation and primary actions, gold for brand accents and green
for positive statuses. Keep text contrast and keyboard focus visible. Statuses
always include text; never convey an execution outcome through color alone.
Use original interface styling rather than embedding third-party character art.
The owner-approved 0.1.1 identity uses a dark Vision wordmark with a subtle green
dot, replacing the red/gold V shield. The surrounding light palette is retained.

## Absolute security boundary

Read-only refers to Home Assistant: local database writes, exceptions and AI
requests are allowed. No HA service calls, state writes, repairs, or configuration
changes. No arbitrary API paths/commands or AI actions. Secrets excluded from
AI, logs, SQLite and publication. Ingress only accepts the Supervisor peer;
local development binds loopback. Future actions need a separate denied-by-default
permission/policy/audit design; no write executor is included.

## Acceptance and limitations

Four sequential milestones: foundation, monitoring, intelligence, release.
Automated simulation, container startup and live HA installation are separate
claims. A release must report exactly which have been verified. HA traces are
bounded by HA retention and permissions. Missing events during downtime cannot
be reconstructed as known outcomes. Providers need live credentials for a real
billable test; transport simulations do not prove live provider access.
