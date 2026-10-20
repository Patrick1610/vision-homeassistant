# Architecture

Browser → Ingress → FastAPI → domain services → SQLite. Monitor → closed HA
read gateway → HA Core proxy. Intelligence → minimized evidence → provider
adapters → validated diagnosis → local history. AI never receives a transport.

The root contains `config.yaml`, `repository.yaml` and Dockerfile. Supervisor
builds the app on-device. No host port, hardware mounts, elevated capability,
Supervisor manager role or host networking. `/data` persists SQLite and app
options. Ingress verifies the actual TCP peer (`172.30.32.2`) with uvicorn proxy
header trust disabled. Local mode binds only 127.0.0.1.

`config.py`: private options, constraints, redacted views. `ha.py`: allowlisted
REST/WS, event subscription and reconnect. `monitor.py`: observation semantics.
`store.py`: transactional history, ordered atomic schema migrations, deduplication and retention.
`evidence.py`: bounded safe structural projections, per-step trace evidence and typed dependencies.
`ai.py`: provider interface, budgets, schema validation and evidence minimization.
`app.py`: local API and lifecycle. `static/`: dependency-free responsive UI,
relative links and escaped untrusted text.

History stores only availability transitions, run/trace summaries, issue changes,
analyses and usage. Numeric sensor history and raw traces/config/logs are not
retained. Reconnects create coverage markers; offline periods are not presented
as continuously measured uptime. Future action policy would require separately
authorized capability and audit stages, absent from this version.

## 0.2.0 data foundation

Schema 3 adds deduplicated safe structure snapshots, a current-observation pointer,
observed structural transitions, per-run step projections and a typed inventory
dependency graph. Migration DDL and the schema version advance in one transaction;
failure rolls everything back. Old records and local meta/settings remain intact.
Interrupted provider reservations still become `uncertain` without reducing cost.
Future schemas fail closed rather than opening through an older app.
Migration 1 is frozen literal DDL; an independent frozen 0.1.1 SQL fixture tests
fresh-install/upgrade schema parity. The unpublished schema-2 candidate also has
a preserving migration to schema 3. Schema 4 adds only local attention overlays,
their note history and supporting indexes. Additive schema 5 binds those overlays
and notes to the retained case's first-observation generation and adds run-change
revision triggers. Frozen migrations 1–4 remain unchanged. WAL mode is required
and checked at startup.
Any future migration that rebuilds `runs` must recreate its revision triggers;
otherwise existing-run updates would no longer refresh local mode findings.

Before an existing database is migrated, SQLite's backup API creates the private,
consistent `vision.db.v{source_version}.bak`, including committed WAL content.
If that filename already exists, an exclusive hard link chooses a new
`vision.db.v{source_version}-{snapshot_hash}.bak` (or a unique fallback if that
name also collides); existing snapshots and operator files are never replaced
or chmodded. A retry first creates one consistent temporary SQLite snapshot,
then reuses a private same-version snapshot only after read-only `quick_check`,
`user_version` and complete snapshot-byte SHA-256 equality. The source database
file's hash is never used as a substitute: committed WAL-only changes must be
included. One `BEGIN IMMEDIATE` writer reservation covers the locked source-
version read, size estimation, backup and all migration DDL until commit/rollback.
The backup API reads through a separate normal read-only connection, including
committed WAL; backing up the writer connection itself would deadlock. A second
startup waits within SQLite's bounded busy timeout and re-reads the schema version
after acquiring the reservation. Snapshot candidates and the original must have
different device/inode identities from live main/WAL/SHM files; aliases fail closed
before copy or DDL, regardless of matching bytes or valid SQLite metadata.
The first snapshot is also retained as `vision.db.pre-migration.bak`; that original
generation is never overwritten. A 3→4 migration therefore gets a current
schema-3 rollback point while the original schema-1 backup remains intact.
Older versioned snapshots are kept: a filename matching the backup pattern does
not prove that Vision owns an operator's file. Backup failure stops
startup before migration. No backup is created for an empty database.
Backups contain the full private household history and must remain local. Allow
space for a full current-database copy before migration, plus all retained
generations and temporary comparison space. There are at most three retained
snapshots per source version and one in-flight temporary snapshot. At the
retained limit a retry may prove reuse, but cannot publish another source revision.
Recognized versioned snapshots and the original are counted by unique inode;
the aggregate peak budget including the new temporary copy is 1 GiB. At least
one estimated database copy plus 16 MiB free-space reserve is required before
copying. Capacity failures stop before DDL with an allowlisted operator-facing
reason; an oversized database has a separate size-limit reason. Matching names
are counted conservatively, never treated as permission
to rotate/delete files. A leftover `vision.db.backup-*` from a crash or operator
blocks another allocation until manually reviewed with Vision stopped. The fixed
operator message names `/data`, `vision.db.backup-*` and its `-journal/-wal/-shm`
sidecars without echoing arbitrary filenames. Ordinary exceptions remove only
their invocation's exclusive temporary file and its exact sidecars. Review backups manually
when space is constrained. They are outside the step-detail storage budget.

For downgrade, keep Supervisor's previous-version backup. If restoring manually,
stop only Vision; preserve the entire current `/data` directory separately,
including its current database/WAL/SHM files and private options. Verify the
selected backup with SQLite `quick_check` and `user_version`; a 0.1.1 downgrade
requires schema 1. With Vision stopped, move the current database/WAL/SHM bundle
aside and copy the matching source-version or original backup to `vision.db` with
mode 0600, then run the
matching previous app version. Never copy over an open database. Observations
made after the backup remain in the preserved newer database and are not merged
automatically. A full Supervisor Vision-backup restore is the alternative.

Current configuration reads and retained trace configurations are separate evidence
sources. A historical trace cannot replace an observed current configuration.
The first current configuration after trace-only coverage is a new baseline,
not proof that HA configuration changed. Changes compare only the retained
structural projection: a message, numeric action payload, arbitrary state,
template or alias change may be invisible. Each full run's sanitized configuration
is linked to that run by snapshot/digest when supplied by HA. A shared AST path
across different configuration digests does not prove an unchanged step.
Observed transitions identify when
Vision noticed a structural difference, never its exact HA edit time or author.

The automation projection retains control-flow paths and kinds, declared static
entity/device/area/label references, mode/max concurrency, service identifiers,
literal delays/timeouts, numeric comparison operands, standard non-location state
enums and literal trigger times. Arbitrary source text, action data, variables,
templates and arbitrary person/location state or payload values are excluded.
Retained entity, area, label, device and service identifiers may themselves
encode human-chosen names. They are private local data, not anonymous data;
every identifier kind must be pseudonymized before any future diagnostic AI
projection. Existing outbound compact evidence remains unchanged in this phase.
Omitted predicates, dynamic
references and truncation remain explicit. No template is evaluated. Limits are
1,000 AST nodes/references and depth 20 per automation.

Per-run evidence retains up to 500 step observations and 100 redacted error
messages of at most 800 characters, safe timestamps/offsets, condition booleans,
wait completion/timeout flags and explicit-stop presence. Raw variables, action
results, full configurations and raw traces are excluded. Error counts become
lower bounds when trace steps are unavailable, malformed, unrecognized or truncated.
Saturation of HA's own 20-element action-path deque also means unknown historical
coverage, even when Vision received every returned element. Missing error text
is never evidence of an error-free run in those cases. Per-step observed and
retained error counts are separate. A finished
run with a continued error remains `succeeded` with `completed_with_errors`; a
normal false branch does not prove failure. A timeout that aborts is distinguished
from a wait timeout that continues. A cancellation alone cannot establish a
restart-mode conflict. Historical runs cannot clear a newer failed-run incident.
HA's last-inserted path is not a chronological stop reason inside loops;
step timestamps record starts, not completions. Retained parallel paths or step
errors/timeouts veto an inferred condition stop: a later-started false branch
cannot establish why an aborted run ended. The generic `stopped` outcome keeps
the abort reason unknown; coverage records this and the timestamp meaning. A
timestamped standalone false condition remains `condition_stopped` when no such
ambiguity is present.
Unknown run start times remain NULL, with separate observation/source provenance;
recovered real timestamps correct them. Legacy timestamps are retained but
explicitly marked `legacy_unverified`. Only `ha_trace`/`event` timestamp provenance
is authoritative for latest-run ordering and automatic incident closure. Unknown
or legacy failed observations keep a conservative unresolved state; incident
detail exposes `blocked_by_unknown_time_run`, its run ID and timing source without
changing the incident's first-seen time, last-seen time or recurrence count.
Trigger-event runs and timing are saved atomically. NULL-start records missing
timing after an older interrupted writer receive only a recovered observation
time, so observation-based retention can expire them without inventing a start.
A degraded list stub cannot overwrite
richer step/error evidence. Logging redaction also has a 16 KiB internal ceiling,
including calls requesting an unlimited display; split tokens are discarded and
the truncation marker remains intact.

Trace detail reads have a 12-request/5-second cycle budget and 2-second per-read
timeout. Separate persisted round-robin cursors serve newest listed runs and
historical backfill. When both lanes have eligible work, eleven count slots serve
newest runs and one serves backfill; unused slots move to the other lane. Lane
order alternates so the time deadline cannot always cut off trailing backfill.
The actual newest listed head is selected before full-evidence skipping, so an
already inspected newest run cannot promote old failures into the newest lane.
Failures/blocked starts retain priority within the backfill lane. A static
165-automation inventory with available fast detail reads reaches all newest
heads in at most fifteen cycles; timeouts, backoff and source changes can extend
that duration. This is a synthetic count bound, not a live latency guarantee.
Each unavailable run backs off from 60 seconds to one hour. Only recognized
capability/transport failures open a global circuit with one bounded recovery
probe; an expired individual trace or incomplete result cannot poison other reads.
Pending detail counts, limits, observation time and next probe are exposed.
Large inventories therefore acquire complete detail progressively, while small
trace-list observations and known failures are retained immediately. Identical
list stubs do not rewrite run/timing rows during retry backoff. Configuration
projection is reused within each trace, and unchanged registry entries reuse
their cleaned projection.

The `run_evidence` table is capped at 256 KiB/eight detailed runs per automation
and 8 MiB across that table. Older added details are compacted to observed counts,
configuration provenance and explicit `details_compacted` coverage. If compact
metadata itself reaches the global detail budget, it moves to the corresponding
run's reserved `_vision_evidence` summary. These small per-run summaries remain
outside the 8 MiB table budget and grow with retained run count; the budget is
not a whole-database/disk cap. A returning full trace removes stale moved metadata
when its richer evidence row is saved. Compact summaries still advance their
whole-run completion flags when later observations arrive.
Existing runs, incidents, first-seen
times, analyses, settings and the usage ledger are never evicted to satisfy this
new detail budget. Time retention still applies as configured. This is not a
global cap on all pre-existing history or SQLite file/WAL overhead.

The typed graph uses only the existing registry/state/configuration reads:
integration domains from entity-registry `platform`, device membership, entities,
automations and declared targets. Opaque config-entry IDs are never interpreted
as integration domains. Template references and area/label membership are not
expanded. The graph is an atomic snapshot with an observation timestamp;
missing capabilities and stale observations limit its coverage.
An unchanged graph fingerprint refreshes only its observation metadata, avoiding
full-table rewrites and WAL churn on every poll.

These projections use official Core 2026.10.2, commit
`8d7fd8b68677c2585be36ec86043308f403875b8`:
[trace element serialization](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/helpers/trace.py),
[script wait, condition, stop and continued-error semantics](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/helpers/script.py),
[entity registry fields](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/helpers/entity_registry.py),
[device registry fields](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/helpers/device_registry.py).
No HA read operation was added for this foundation.

## 0.2.0 local investigations

`insights.py` reads Vision's retained SQLite evidence and current sanitized
inventory. It has no network client or AI dependency. Source issues remain
separate from local attention annotations: known, expected and snoozed states
do not change active source facts, dates or recurrence. Snoozes expire against
wall time across restarts; an expected-offline exception likewise suppresses
attention while preserving the offline source observation. Annotation notes and
their local history are stored separately. Resolved sources retain annotations
while their source case is retained. The overlay applies only to its matching
case key and original `first_seen`; a newly inserted generation after retention
pruning starts in review. Orphan annotations/notes are removed at startup and
prune, and notes are limited to the newest 50 per retained case generation and
the configured retention interval. Source issues, real exceptions and recurrence
are unaffected by annotation cleanup.

Finding refresh belongs to monitor startup and completed sync cycles, never to
GET routes. The static-rule gate reads only configuration identities/digests and
inventory coverage; unchanged inputs do not load or decode AST projections.
Transactional run revision triggers detect inserts, deletes and updates to an
existing run, so unchanged cycles skip the all-run finding scan. Inventory reads
load expected exceptions/overlays once as a set. Public case/overview/detail GETs
do not open write transactions or refresh findings; newly ingested static/mode
findings appear after the next completed monitor cycle.

Current configuration projections support explicit missing entity/device
references only when the corresponding registry read succeeded. Disabled registry
entities are present references; templates and area/label expansion remain unknown.
Lost permissions/truncated projections cannot establish resolution of a previous
missing-reference finding. Waits without declared timeouts and continue-on-error
steps produce manual review checks. A mode finding requires an actual HA refused
start; cancellation alone proves no mode conflict. Case observation time is never
backdated to an old HA run's start. A refused start without authoritative timing
remains a visible unordered observation until time recovery permits resolution.
Repeated polls do not invent recurrence. Static case identity includes its
configuration digest rather than assuming an AST path identifies the same step
across revisions.

One refresh selects at most 20 static findings per automation and 500 globally,
prioritizing concrete absent references before informational logic checks. One
batched lookup supplies existing source records. Observed/selected/omitted counts
and per-automation limits are explicit coverage metadata. Existing history is
preserved: a previously active finding omitted under the selection budget remains
an unresolved source observation with local status `limited`, rather than being
silently declared resolved. Informational static findings rank below availability.
Case/overview responses carry aggregate rule-coverage counters only. Per-automation
counts are fetched by the requested automation detail, rather than including an
entity-keyed map on every page. A case page batches all requested run/evidence
pairs into one indexed read; missing runs stay cached as unknown without a
per-card fallback lookup. No AST is loaded for these cards.
Per-automation coverage writes use one batch and stale keys in that ephemeral
namespace are removed when their automation leaves `automation_current`. The
retained structural snapshots, source issues and unrelated metadata remain intact.

Overview priorities place critical issues and failed executions ahead of bulk
availability cases. Cards show retained outcome, step/error evidence and a manual
check. Multiple source records for the same run share an overview card; each
original issue remains accessible. Dossiers show bounded timelines, gaps,
unverified run-time blockers, redacted messages and manual checks. Error counts
are observations: parent/leaf trace errors can describe the same execution error.
The overview groups availability attention into one card with its server count
and a filtered-queue link; shared membership does not establish a shared cause.
At most three prioritized groups and one primary investigation CTA precede compact
supporting counts. Availability-only installations show that concrete group.
The availability count and recent-change reads degrade independently of primary
priorities. A failed count remains unknown; retained availability in the primary
sample stays represented with a filtered-queue link. Conflicting read snapshots
are labelled, never treated as proof of zero problems. The heading reports the
full attention total as of the primary read, not the bounded card sample.
Availability failure can leave priority coverage incomplete; a changes-only
failure leaves a known empty attention queue intact and separately labels history
unknown. Malformed/legacy step summaries degrade
to explicit unknown evidence and limited comparison coverage; they do not turn
into clean traces or a failed landing page.

Dossiers follow problem → evidence → manual plan → validation, with visible source
status and unknown coverage. Longer facts, source detail, relations and local
attention controls are disclosures. Run views use bounded step-start timelines;
they never derive durations or parallel completion order from the distance between
starts. Unknown/unverified starts remain labelled; whole-run success with continued
step errors stays distinct from failed execution. The manual task and its step
path come from one relevant typed observation; a generic first error is never
substituted. Additional server checks, related source cases and all retained
references remain reachable behind concise disclosures. The concrete last gap
timestamp remains visible when retained.

Intelligence shows up to three short manual proposals initially, with full text,
references and additional proposals behind disclosures. The selected result is
not duplicated in the retained list. Older conversation rounds and full legacy
mapping remain available; withdrawn results remain labelled and cannot continue.
Exact request bodies/consent remain accessible. A single terminal-state handler
serves initial request loading and polling. Only an explicit send/watch session
auto-opens its completed result. Replacement navigation consumes only an actual
`watch=1` route so Back cannot replay the redirect. If a lost POST response is
resolved as completed while still on the original audit/preparation page, normal
push navigation preserves that original entry. A plain retained-request link always keeps the exact sent
body, digest, envelope and consent accessible, including after a running audit
finishes polling. Completed audits show an Open received analysis link;
failed/uncertain/withdrawn requests show state, safe errors and any retained result
link. Withdrawal never restores continuation rights. After a send error, one lightweight status read may restore
an unused preview only when the server confirms `preview` and not in flight.
Unknown status stays conservative; a running job remains observed to completion.

Background overview refresh checks focus, open disclosures, text selection and
page visibility before reading and again before replacing content. Work started
before user engagement cannot then discard focused controls or an open panel.
Any background read failure keeps the last-loaded DOM, focus and selection and
shows a refresh-failed notice when the notice channel is free or already contains
that refresh warning. Repeated identical failures do not rewrite it or overwrite
unrelated user feedback. A failed initial primary read is an explicit error.
Long text in small/span/strong/time receives the same wrapping as body text;
affected identifiers shrink and wrap within their card without clipping content
or focus outlines. CSSOM contracts verify styling and route preservation; actual
settled WebKit viewport measurements remain a separate layout acceptance gate.

Automation detail labels current observed logic separately from each run's own
safe structural snapshot. Equal nonempty structure digests permit path/iteration comparison;
different/missing digests leave runs separate. Missing/compacted evidence stays
explicit and differences never prove cause. Structural history shows bounded
safe projection differences; its baseline/observation time is no HA edit time.
Typed entity/device/integration links show direct relations and up to 100 declared
automation relations through at most 200 observed members, with truncation flags.
Both `entity:automation.*` and `automation:automation.*` identities are consulted.
Relations and shared membership do not establish causation.

Case lists use server filtering and bounded pages. History uses a closed table/
field map, parameter binding and at most 100 rows per keyset page, ordered by
retained time then stable row identity; NULL run starts sort last and legacy time
provenance remains visible. UTC-day filters are explicit. The list of automations
uses one bulk aggregate query and excludes AST/run history; deep evidence is
loaded only for the requested automation. Legacy API/history/storage remain
available and AI requests remain subject to the existing opt-in.

## Source validation (2026-10-19)

Official HA docs now redirect from developers.home-assistant.io to contributors:

- https://contributors.home-assistant.io/apps/reference/configuration/
- https://contributors.home-assistant.io/apps/guides/communication/
- https://contributors.home-assistant.io/apps/guides/ingress/
- https://contributors.home-assistant.io/core/internals/websocket-api/
- https://contributors.home-assistant.io/core/internals/rest-api/

Component-specific reads are checked against official Core source (2026.10.2):
`components/trace/{websocket_api,util}.py`, `repairs/websocket_api.py`,
`system_log/__init__.py`, `automation/config.py`. These are internal frontend
protocols and may be unavailable or change; failures must show degraded coverage.

HA's token scope is broader than Vision's application policy. The transport
allowlist enforces read-only behavior in this code; a compromised process holding
the token could bypass application policy. No claim of server-enforced read scope.

Supervisor root discovery was checked against current official `supervisor/store/data.py`
(source sha256 `3714417b3505d7308b6c1b46d6717d4d163042a5ca6f83c5a62ef1e9ea3b22ce`):
`path.glob("**/config.*")` includes the root; suffixes are JSON/YAML and hidden/rootfs
directories are excluded. This is source-level discovery evidence, not live install evidence.

The image is the official multiarchitecture Python image pinned by index digest.
Supervisor/Docker selects the target architecture; BUILD_ARCH supplies HA labels.
BUILD_FROM is deliberately not consumed because the application needs this pinned
Python runtime rather than an S6 image. init:true delegates signal reaping to Docker.
Dependencies are resolved with uv 0.13.1, pinned including transitive packages and
PyPI hashes. The app executes copied Python sources directly, without a second
build-isolation network resolution.

Supervisor REST uses `http://supervisor/core/api/`, but its WebSocket endpoint
is `http://supervisor/core/websocket` (HTTP Upgrade). A direct Core connection
uses `/api/websocket`. These are separate runtime URLs and both routing shapes
are exercised by the full local connection/reconnect integration test.

Logs use the native `system_log/list` aggregate on each poll. Group identity is
the logger, source location and final traceback frame (hashed, not retained raw),
matching HA's grouping rather than its changing five-message deque. Persisted
counter markers distinguish re-polling from new occurrences and buffer resets.
Vision does not subscribe to `system_log_event`: HA emits a fresh count-one entry
there, so combining it with aggregate counts would double-count occurrences.

## Targeted AI investigations — C implementation candidate

Schema 6 additively stores prepared requests and their attempt-to-usage links.
Schema 7 adds minimal billing receipts, backfilled from existing schema-6 attempts:
usage ID/time, request/conversation IDs, round, digest, provider, attempt and a
revocation flag. Receipts reference usage, not the heavy request, and survive its
ordinary retention until the corresponding 400-day ledger entry is pruned.
Reservation, attempt link and receipt commit atomically. Legacy analyses and
usage retain their original tables and records; provenance absent from historical
legacy calls is not invented.
`ai_contract.py` defines eleven tasks, their instructions, section allowlists and
strict local diagnosis schema. `ai_evidence.py` captures bounded local projections
and selects relevant paths before privacy projection. `ai_privacy.py` handles
identifier aliases; `ai_provider.py` serializes and sends fixed provider protocols.
`ai.py` owns immutable previews, scope, consent, conversations and accounting.
No provider request includes an HA token or exposes HA transport methods/tools.
The local evidence selector reads retained Monitor/Store projections only.

| Task | Investigation evidence and boundary |
| --- | --- |
| Audit | Prioritized retained cases, aggregate inventory/outcomes and coverage. |
| Incident | One dossier, recurrence, linked execution errors and observation gaps. |
| Automation logic | Current observed structure separately from each selected run revision; steps and a configuration-bound comparison. |
| Optimization | Retained waits/delays plus an explicitly selected comparable run; no improvement finding without this prerequisite. |
| Availability | Offline segments, gaps, expected status and healthy/unhealthy device/integration siblings. |
| Template error | Actual template-error paths, selected configuration metadata and matched successful counterexamples; no raw expression reconstruction. |
| Missing target | Current explicit references versus registry presence/disabled status; dynamic/area/label expansion remains unknown. |
| Refused start | Actual blocked outcome and mode evidence; cancellation does not establish restart causation. |
| Condition stop | A retained condition-stop outcome and false observations; ordinary false branches alone do not qualify. |
| Wait timeout | Actual wait paths/flags, continuation semantics and selected comparison; a service TimeoutError alone is insufficient. |
| Device communication | Actual communication messages and failing action's declared physical targets, with healthy contrary sibling observations. |

The dossier preselects a supported task from retained evidence. Automation links
carry the exact selected `run_id` and comparison; the preview shows their local
selection basis. Static current-reference cases do not silently substitute an old
run's structure. Every preview includes prerequisite/coverage indicators. If a
specialized prerequisite is absent, the local preview explains the missing
observation and disables sending. The server rejects it before claim, reservation
or provider access. A response-level prerequisite guard remains defense in depth.

A manual preview freezes the task, privacy profile, sanitized question, scoped
prior context, evidence/provenance, schema/prompt versions, provider model/token
limits and all configured primary/backup request bodies. SHA-256 binds the whole
credential-free envelope. Outgoing IDs are fresh opaque round-scoped references,
not raw configuration digests or hashes of HA identifiers. Local evidence and
identifier mappings remain private. The send endpoint accepts only request ID
and digest, atomically claims it once, and returns HTTP 202 with a retained request
ID. A server-owned job sends the frozen UTF-8 bytes, independent of the initiating
HTTP client. A lightweight status endpoint returns state/error/analysis ID without
reading full bodies; reopening the request can resume status observation. One job
runs at a time with a 900-second absolute deadline and 480-second provider read
limit (connect 10/write 30/pool 10 seconds). This allows bounded schema-compilation
and large-output work without promising completion at every model/token limit.
Shutdown/deadline cancellation preserves possible transmitted costs as uncertain.
Provider credentials are added only as headers at the transport boundary.
Editing the investigation form automatically revokes only an unused `preview`
that is not in flight. A displayed running request is withdrawn only through its
explicit Revoke button. The client marks a send as in flight before awaiting its
202 response; a transport error leaves that conservative state until server status
is checked. Failed automatic withdrawal is visible and disables the old Send.

A private process binding includes current configuration and consent generation.
AI/profile revocation invalidates pending requests even after off→on. Restart also
invalidates old prepared requests. Each retry/failover checks binding and request
revocation again before reserving usage or calling a provider. An already sent
request cannot be recalled; its possible cost remains recorded. Primary recovery,
rate-limit backoff, separately consented budget failover and uncertain reservations
remain enforced. Refusal, incomplete output, invalid schema/citations and missing
usage have distinct outcomes; received billed usage is recorded before validation.
There is no free retry of a billed invalid diagnosis.

Conversations stay bound to the original task/target/profile/selected runs and
frozen evidence snapshot. At most four completed rounds and eight serialized
messages/24 KiB UTF-8 of prior context are permitted. Omitted context is explicit.
Earlier reference fields and round IDs are stripped from outbound historical
context. Both providers' native schemas enumerate only this round's references;
the local validator still rejects every stale/unknown support or counterreference.
Compact follow-ups use an enum focus and may include bounded sanitized prior
provider conclusions, uncertainty, unknowns and manual/validation proposals. Raw
HA/source text and free-form user questions remain excluded from compact.
Diagnostic questions and all historical provider text pass aliases/redaction
again before preview. Typed compact dependencies retain relation/node kinds and
presence flags, changes retain closed kind/source values, and siblings retain
availability enums; these sections do not become constant placeholders. One
manually reviewed enum-section expansion can use
only initially captured sections of this target; no automatic evidence tool,
HA read, arbitrary query, shell command or path is exposed. Each follow-up needs
its own preview/send; the first preview makes no promise about a future body.
A revoked round with a received analysis remains in the conversation audit view,
labelled withdrawn. Its result and billed usage are retained, while continuation
of that conversation is blocked, including previously prepared follow-ups.
Existing explicitly enabled daily audits remain once-daily compact system audits,
with their exact scheduled requests retained; they cannot inherit diagnostic consent.

Bounds: 120 evidence records and 48,000 UTF-8 bytes including bundle provenance;
32 selected steps/20 errors and 40 structure nodes per revision; provider body
128 KiB; local frozen evidence 192 KiB; combined stored preview/evidence 512 KiB.
At most 32 disposable requests without provider attempts remain (16 MiB worst-case
payload bound). Attempted/completed requests follow analysis retention, preserving
exact bodies. Expired unused previews are removed. Admission rejects a new preview
before payment if it would exceed 512 retained requests or 64 MiB of UTF-8
request/local-evidence plus analysis-result/evidence payloads. Each unused/sending
request reserves another 1 MiB for its potential stored result, including revoked
requests with an already transmitted reserved attempt. Actual encoded stored
result+evidence must fit that bound; otherwise billed usage remains recorded and
no oversized analysis is stored. The cap preserves existing history and exact
completed bodies, even if restored data already exceeds it; it is not a whole-DB,
WAL, metadata, ledger or backup disk cap. Migration 8 backfills per-row UTF-8
payload sizes into `ai_storage_sizes` without changing old body columns/content.
Insert, body/id-update and delete triggers maintain those small integer records
transactionally, including rollback and retention pruning. Status-only changes do
not remeasure bodies. Admission and displayed headroom sum integer sizes and
small request/attempt metadata; they do not rescan retained payloads inside the
writer transaction. A future migration rebuilding `analyses` or `ai_requests`
must preserve/recreate these triggers and accounting rows. Future source-table
upsert support and recovery from externally removed triggers are deferred contract
work: current application writes use ordinary insert/update/delete with triggers
present. Do not assume that external trigger-less imports are a supported restore.
The UI shows remaining
payload bytes/request slots; it offers no selective history deletion or eviction.
Billing receipts follow usage for 400
days. Ordinary body/analysis retention still applies. Request state left `sending`
after restart becomes `uncertain`, alongside reserved usage.


The compatibility `GET /api/intelligence/preview` remains a bounded, read-only
compact projection for exactly `audit`, `incident` and `automation` (optional local
`target`). It returns `transmitted` and `local_mapping` only: no prepared request
ID, send consent, reservation or provider call. It uses the same 120-record/
48,000-byte bundle and bounded local selector limits above; unknown targets fail
locally. Exact sendable previews for all eleven tasks use POST on that route.
A projected empty evidence set fails clearly before request storage or payment.

Provider contracts were checked against official documentation on 2026-10-20:
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
and [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
OpenAI Responses uses `store:false` and strict `text.format`; every object is
closed and every property required. Anthropic Messages uses native
`output_config.format` (generally available without a beta header), without tools.
Its provider schema removes unsupported
string/numeric/array bounds and describes them; the full original Pydantic schema
still validates locally. No model is silently selected, and protocol mocks do not
prove a configured model's compatibility, availability or actual billing.

HTTP failures retain only numeric status, a closed reason and fixed manual guidance;
remote messages, codes, headers and account identifiers are never echoed. Refusal,
output/context-window truncation and local schema/reference/section failures retain
received usage. Successful envelopes are bounded at 4 MiB, error envelopes at
8 KiB, with the bound checked before adding a chunk. Configurable output limits
span 512–65,536; default 2,048 and saved older limits remain unchanged. A larger
limit reserves its full configured output cost at the original USD/million rates.
Recent analysis lists contain metadata/summary only; full findings and legacy
mapping are loaded by one explicit detail route. History result search remains.
