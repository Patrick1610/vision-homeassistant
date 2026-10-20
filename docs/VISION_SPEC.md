# Vision specification

The initial functional baseline was delivered as v0.1.0. Presentation amendments
are recorded below; patch releases retain the same read-only functional scope.

## Authorized 0.2.0 scope

The owner authorized an autonomous 0.2.0 implementation, tests, public release
and live verification on 2026-10-20. Preserve all existing Git history and the
immutable 0.1.0/0.1.1 release tags. This section defines the accepted scope;
phase completion and actual evidence belong in PLANS.md and VALIDATION.md.

- **Data foundation:** transactional, versioned SQLite migrations retaining all
  historical records, private settings and conservative billing reservations.
  Bounded sanitized automation control flow, typed static references, selected
  literal operands, trace step summaries and structural configuration history.
  Separate whole-run completion from continued step errors and missing coverage.
- **Local insight:** prioritized concrete cases, incident dossiers with timelines,
  recurrence, evidence links and local known/expected/snoozed status. Deep
  automation comparison, static rules, typed dependency impact and searchable,
  paginated history and observed changes. Facts, hypotheses, missing evidence
  and manual checks remain visibly distinct. Core utility must not require AI.
- **Targeted intelligence:** separate bounded investigations for audit, incident,
  automation logic, optimization, availability, template errors, missing targets,
  mode conflicts, condition stops and timeouts where evidence supports them.
  Every task uses a relevant evidence selection, validated citations, supporting
  and contrary evidence and explicit unknowns. No universal prompt masquerading
  as multiple tasks. Scoped dossier follow-ups have bounded conversation history.
  Any extra evidence request is limited to enumerated local evidence sections;
  it cannot contain HA operations, SQL, shell or arbitrary tools.
- **Privacy and delivery:** local-only, compact and explicitly opted-in diagnostic
  profiles; existing configurations remain compact or disabled. Show the exact
  outgoing prompt/task/schema versions and evidence provenance. Keep credentials
  and real HA observations out of public fixtures and external reviews. Preserve
  retry/failover, budgets and uncertain billing. Test synthetic incidents, upgrade
  persistence, large inventories, read-policy security and actual UI workflows.

The existing FastAPI/SQLite/vanilla JavaScript stack and light interface with a
dark Vision wordmark, small green dot and burgundy/gold accents remain. No new
HA write, service, configuration, repair, template execution or generic transport
capability is authorized. AI has no HA credentials or tools. No paid provider
request is required by release checks; any actual provider qualification needs
separate owner opt-in and its results must be recorded independently.

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
dark neutral navigation and one dark-green primary investigation action.
Burgundy emphasizes actual errors, gold marks limited/unknown evidence and green
can also mark positive observed statuses. Keep text contrast and keyboard focus
visible. Statuses
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

## Owner-directed 0.2.0 presentation acceptance

Show at most three compact prioritized problem cards and one primary investigation
step before supporting counts. Each card states the short observed conclusion,
affected components and one concrete manual next check. Dossiers lead through
problem, retained evidence, manual solution/check and validation; longer context
belongs behind details. Distinguish source facts, local attention and AI hypotheses.
Use a visual step/observation timeline tied to the selected run/configuration;
step-start timestamps never become invented execution durations. Intelligence
findings follow the same concise problem→manual plan→validation structure.
Preserve selected runs/comparisons, mobile text wrapping, focus/open panels during
refresh and accessible exact bodies/consent. No automatic repair/HA-action buttons.
The RC implementation is subject to D browser/review and public/live acceptance;
the earlier prototype is not evidence of delivered behavior.

## Deferred 0.2.1 public-source research

Separate tested feature, not part of 0.2.0: research a grouped problem using official
HA/integration documentation and relevant GitHub sources first, with Reddit only
as supplementary evidence. Bind proposals to versions and cited sources, list
prerequisites, manual steps and validation, cache results and use a separate research
budget. Minimize public queries; HA credentials never enter research tools. No web
research executor, scheduled work or new HA capability is authorized by this backlog.
