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
timeout. A persisted round-robin cursor prevents busy early automations from
starving later ones; failures/blocked starts are prioritized within each automation.
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
When availability is the only concrete attention source, the overview shows up
to three concrete availability dossiers. Malformed/legacy step summaries degrade
to explicit unknown evidence and limited comparison coverage; they do not turn
into clean traces or a failed landing page.

Automation detail labels current observed logic separately from each run's own
configuration snapshot. Equal nonempty digests permit path/iteration comparison;
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
