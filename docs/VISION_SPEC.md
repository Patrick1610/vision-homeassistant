# Vision specification

## Authorized 0.3.0 scope — 2026-10-22

The owner accepted the complete proposed 0.3.0 plan and instructed execution.
Stage A delivers an installable local experience: Today, Problems, Devices,
History and Settings as primary navigation; legacy automations/intelligence/cases
remain reachable as expert views. Dutch and English cover the new journey and
navigation; historical analyses keep their original text. Within 30 seconds a user
can identify up to three meaningful priorities, inspect proven facts/coverage/
unknowns, choose one manual check and record follow-through in Vision only.

Local importance, preferences, optional rerunnable/prepopulated intake and per-case
feedback are separate from existing known/expected policy and observation facts.
Known issue and usual behaviour are independent nullable choices alongside
importance; selecting both is valid. Untouched fields retain their existing value.
Cancel performs no write. Intake and ordinary preference changes never reset a
policy baseline or acknowledge worsening. User-reported improvement is not observed
recovery; gaps, changed cohorts and removal remain unknown. Grouping needs actual
covered transitions within the existing five-minute bound, not shared integration
or first-observation/bootstrap coincidence. Declared upstream links are stronger
evidence than integration correlation; neither proves a physical cause or impact.
Healthy counterevidence and bounded/omitted evidence stay visible. Friendly entity,
device and room names are local only; the only new HA operation may be the exact
officially verified area-registry list read. No HA write or numeric-state capture.

Stage B follows separate Stage A review: durable one-click orchestration over the
existing research/preview/send hooks and an opt-in v4 typed/localized brief, without
changing old v2/v3 request/result/native bytes, billing or consent ceilings. Names
and rooms never enter AI/public queries. Public/live/release gates and five real
human usability participants belong to the controller; no such pass is preclaimed.
Use additive migrations, preserve all existing history/options/usage, and retain
the existing metric kernels and bounded work. Stage A may package 0.3.0-dev.1 once
coherent. Stage A received source-functional acceptance on abcd98ac; the controller
then explicitly authorized Stage B. Real-human usability remains a separate gate.

### Accepted Stage B contract

One explicit problem action may run one bounded public-source phase and one compact
AI round only after separate versioned, default-off authorization. Context/status
reads are side-effect-free. Durable slot-bound operation admission precedes async
work; repeated clicks/reloads reuse status, and restart never resumes transmission.
The operation binds exact typed scope, episode/revision and closed Dutch/English
answer language. Device groups use an explicit bounded aggregate plus separate
healthy contrary evidence; they never silently substitute their first device.
Source runs bind their complete entity/run pair. Stale/missing scope fails closed.
Active base/final requests remain pinned, with shared manual/daily admission,
per-dispatch revocation and the existing conservative receipts/budget/failover rules.

New human-v4 local/source variants explicitly opt in to short title/explanation/
next-check fields. Existing v2/v3 payloads, native bodies, digests, historical prose
and results remain literal. Keep the local first check ahead of optional AI; show
up to three short proposals, with full plans, validation and evidence expandable.
Exact frozen bodies remain locally inspectable; diagnostic retains fresh per-send
manual consent. No automatic additional rounds, HA actions or new HA reads follow.

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

## Authorized 0.2.1 phase A — device reliability and manual follow-through

The owner authorized work from the published 0.2.0 source on 2026-10-20. Phase A
must work locally without AI and preserve all existing history, options, billing,
privacy consent and the absolute read-only HA boundary. Source-research/AI work
stays behind the separate later phase; no new HA read or write is required here.

- Begin with a concrete manual check beside a compact accessible 24 h / 7 d / 30 d
  trend on desktop, and before the larger chart on mobile, with a real work queue,
  not entity-counter cards. Count unique registry devices. One device with twenty
  unavailable entities is one device observation. Meaningful enabled primary
  evidence, diagnostic/config/update entities, disabled devices, unknown values,
  missing states and unmapped entities must remain distinguishable. Unknown is
  not offline. Explicitly unavailable unclassified members do not veto otherwise
  unanimous primary-unavailable evidence; available/unknown/missing members do.
  With no primary signal the device stays unassessed. A battery/sleep expectation is declared evidence, never a name,
  silence or presumed network cause.
- Record new timestamped device/cohort and monitoring-coverage intervals. Existing
  entity history remains searchable; absent historical device mapping is unknown,
  not a fabricated 30-day device series. Deletion, disabling, registry loss and
  changed membership do not count as recovery. Device-hours are clipped interval
  unions per device, never summed entity-hours; observation gaps stay grey.
- Define disjoint persistent/new/expected categories and their selected window.
  A newly imported baseline is not a proven new outage. Compare only the same
  adequately observed cohort when describing improved/worsened/unchanged state.
  Separately compare integrated offline device-hours across equal window halves,
  using a fixed subset known and covered throughout the whole window. Show
  comparable/excluded totals and make no whole-house or frequency claim from it.
  Keep persistent known/expected backlog visible without weekly acknowledgment or
  silently normalizing an unhealthy baseline. Integration/possible Zigbee groups
  show bounded membership/coverage and correlation, not a diagnosed shared cause.
- At most three next cases state problem, affected devices, a concrete manual
  step and a later observational validation. New/worsening device evidence and
  serious health issues take precedence; ordinary condition stops, intended mode
  behavior and old retained run failures do not dominate this action queue.
  Every old case/run remains inspectable. Primary links open the chosen affected
  device, with other cohort members separately linked; they never substitute an
  integration-wide list containing unrelated healthy devices.
- Local persistent device expectations and hand-performed-check markers write
  only Vision. Known worsening remains durable through unknown states and ordinary
  note/power edits; a separate explicit acknowledgment accepts a new known baseline.
  Later observations may show recovery or continuing evidence;
  missing coverage remains unknown and a before/after association is not causal
  proof. No HA action, repair, ping, numeric-state store or Recorder copy is added.
- Use the existing white/mint/dark-wordmark identity, responsive accessible SVG
  charts, clear gaps and expandable proof. Bound query/CPU/response work and
  expose truncation for large inventories/history. Require meaningful synthetic
  interval/coverage/cohort oracles, migrations/restart and DOM workflows, preserve
  the 341 Python / 34 DOM baseline, freeze and critically review the working phase.

## Authorized 0.2.1 phase B — public-source research

After phase-A critical GO on `83355b6`, the owner/controller authorized a working
0.2.1-dev.2. One manually selected problem uses a visible, closed generic query
plan, a bounded public-research job, then a NEW exact AI preview over the SAME
frozen local snapshot plus actual sanitized public excerpts. Sending to a model
remains a separate reviewed action. No research during daily audits, provider
retries/failover or scoped follow-ups. Existing compact privacy, options, billing,
received history and exact v2 request bodies/digests remain preserved.

Public inputs are only a bundled known integration catalog, closed problem class
and strictly validated current authenticated HA version. Never send household
names/IDs, questions, errors, URLs or custom platform names as queries. Current
server version is not a historical run version. Public transport is GET-only,
fixed HTTPS hosts/paths/headers, no redirects, credentials, cookies, Referer or
environment proxy. Official HA documentation and fixed GitHub core/upstream
catalog repositories are supported; Reddit is explicitly unavailable without
OAuth and has no workaround.

Each manual job is bounded to 6 GET attempts, 2 issue searches, 5 sources, 30 s,
512 KiB decoded per response and 12 KiB normalized public context. Durable atomic
quota is claimed before dispatch: 20 GETs/hour, 60/day and 2 searches/minute;
failed dispatch claims perform no network and possible attempts are not refunded.
Cache/plans/jobs are bounded; upstream backoff and quota survive restart. At most
one comment page (`per_page=3`) from one already-found catalog issue uses its
public integer comment count to derive the last page, with at most two cited
comments. Missing/invalid count causes a gap, never a guessed first page/crawl.

Research v3 validates separate current-round local and public-source refs and an
optional source-bound manual plan with prerequisites and 2–4 steps, followed by
validation and explicit uncertainty. Public text remains untrusted; no issue,
closed status or comment establishes local cause/fix/version compatibility.
Source hashes bind exact final sanitized excerpts before either native body is
frozen. Analyses retain cited sources after request expiry. Ordinary v2 results
and provider contracts remain supported.

Availability also accepts an explicitly typed exact registered-device target,
without run/comparison or representative entity: bounded own members, healthy
counterevidence, roles, expected/disabled evidence and coverage; separate bounded
same-integration correlation. Follow-ups reuse that frozen group. The UI centers
the selected/latest solution and keeps older investigations compact. No new HA
operation, action executor, paid credential or richer privacy opt-in is added.
