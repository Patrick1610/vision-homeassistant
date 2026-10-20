# Validation and release status — 2026-10-20

**Current source package: 0.2.0-rc.1.** A/B/C are accepted on their immutable
candidates. D UI, RC publication/live native-provider checks and the final stable
0.2.0 release remain separate gates. The published/live development preview is
0.2.0-dev.1; its legacy provider calls do not qualify the new native C pipeline.
Historical evidence below remains bound to the version named in each section.

**0.1.1 wordmark update:** [published](https://github.com/Patrick1610/vision-homeassistant/releases/tag/v0.1.1),
CI verified and live Supervisor update verified. The v0.1.0 evidence below
remains historical; the current patch results are in the final section.

Status: **v0.1.0 qualified on the live Supervisor test installation**.
Public [Vision v0.1.0 release](https://github.com/Patrick1610/vision-homeassistant/releases/tag/v0.1.0) is published and independently verified.
Component, container and live results remain distinct evidence below.

| Evidence | Result |
| --- | --- |
| Python component and local WS/REST integration suite (Mac and Linux container) | 76 passed; includes authentication, read policy, state inventory, Repairs/logs, trigger/trace deduplication, reconnect, fragmented/invalid/oversized HTTP responses and bounded container readiness. |
| Ruff lint / format | Passed. |
| JavaScript syntax | `node --check vision/static/app.js` passed. |
| Dependencies | Exact transitive versions and SHA256 hashes; clean ARM64 and AMD64 image installs succeeded. `pip check` passed. |
| Container startup and restart history before the light UI | HTTP health before and after restart, exceptions loaded by the restarted app, and independent SQLite volume persistence passed on ARM64 and emulated AMD64 images. These pre-theme images are historical; their exact source binding is recorded in BUILD_EVIDENCE.json. |
| Browser | Synthetic inventory/detail rendering and saving an exception verified through real browser interaction. 390 px and 1280 px viewports: document widths match, no page overflow or browser console errors. |
| Upstream trace semantics | Six normalized cases from HA 2026.10.2 official fixtures/assertions, plus mode-block tests. Source downloaded and independently compared byte-for-byte with Git objects at `8d7fd8b68677c2585be36ec86043308f403875b8`. |
| External review | The four milestone streams and subsequent stream-reader/restart correction ended GO with no open critical/high/medium findings. See REVIEWS.md. Jev unavailable because its API key is not configured; no score claimed. |
| Live HA OS / Supervisor installation | Passed: owner authorized the current user; Ingress unlocked, repository refreshed and only Vision rebuilt. The light UI loaded, live inventories and all nine read capabilities worked, structural summaries completed, and native HA traces corroborated successful and failed outcomes. A separate Vision restart reconnected and retained all ten sampled incident records with their original first-seen timestamps. |
| Live billable Anthropic/OpenAI request | Not performed: no provider credentials supplied. Both adapters tested through deterministic HTTP simulations. |
| GitHub source publication | All 50 tracked files uploaded through GitHub's web interface. Anonymous readback confirms identical content and Git trees. No CLI authentication was used for publication. |
| GitHub CI | [Run 39294357509](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39294357509) passed in 1m 57s: tests/lint/format/JS/publication scan plus build/start/restart-persistence on amd64 and arm64. First run exposed a test-only absolute-path exclusion bug; a repository-relative exclusion fixes it. |
| Final tag/release | Published through the browser. Anonymous public release-page readback and Git fetch confirm v0.1.0 at `321337f2307db19455917bcb9dd9018b469a88da`. |

## Reproduction

Use the README commands. Container smoke: `python scripts/container_smoke.py IMAGE`.
With a nondefault Docker context, set `DOCKER_CONTEXT` for the command. It creates
and removes only its uniquely named test container and volume.

The pytest suite currently emits one Starlette test-client deprecation warning
about its HTTPX transport. Runtime API behavior and test assertions pass. This
does not assert compatibility with an untested future dependency upgrade.

## Source verification

All four downloaded source files were independently fetched as Git objects at
`8d7fd8b68677c2585be36ec86043308f403875b8` and compared byte-for-byte. Fixture source
hashes, normalization and upstream Apache license are in `tests/fixtures/`.
The full upstream test file parses with the selected Python 3.14 runtime.
This source-level verification does not replace a live installation test.

## Stream regression and current candidate

An actual chunked HTTP server exposed a single-read bug in automation configuration
retrieval: a valid JSON response could arrive in fragments. Four regression cases
failed before the correction. The reader now accumulates bounded chunks through
EOF, retains the 2 MiB maximum and accepts only a JSON object. These four cases
and two container-readiness cases pass in the 76-test Mac and Linux suites.
`BUILD_EVIDENCE.json` binds the rebuilt images to implementation commit
`898ebb7cff1fbb9c1c134ed67979e6b8545cfd10`, superseding the earlier candidate.

## Public source and publication

The source, builds, tests, reviews and local Git-history secret scan are complete.
The audited source is public at [Patrick1610/vision-homeassistant](https://github.com/Patrick1610/vision-homeassistant).
Initial public commit `18eef515b85d1f195664aa46bfadf3be0c689b00` exactly matched
local `889ac87505965d1cdc0518ab97a766189f205805` (50 files; tree
`46a30cd223178f04c1b0c6800560216585300d49`). The test-only CI correction is public
at `dc8603ce9eab412cdefd0530622f1d80cd590d1f`, matching local `fd201aa` at tree
`bb71a410b82b4129081b51c95ec7de9451ec2149`. Its actual workflow is
[CI run 39294357509](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39294357509).
CI reported non-failing runner notices for Node 20 actions forced to Node 24 and
the ubuntu-latest image migration. The live installation checks described below
have now passed. Final publication follows those checks; it must not be inferred
from the earlier component/container results alone.

## Light UI verification

The white/light Vision interface uses deep red and gold branding with green
positive statuses, original CSS branding and local system fonts. All seven
routes and an automation detail rendered in a real local browser with synthetic
data. Layouts at 1280, 801, 800, 390 and 320 px showed no page overflow. A local
exception was saved through the form; keyboard focus/skip-to-content preserved
the route. No browser errors or warnings were observed. Measured text contrasts
exceed 4.5:1, including muted on canvas 4.98:1 and red on rose 7.19:1; the input
border on white is 3.17:1. This is targeted verification, not a full accessibility
audit. The 76-test suite, Ruff, JS syntax, diff check and publication scan pass.
External review `50f1f5ef-998d-40fe-aad5-91f89a742eba` ended GO with no findings.

Public light-UI candidate `5ddf6fb12d64bf63dc4f97d323a20d4d5c89e5ba` matches
local `3e2ca610c9a11f5796026685d8dd1a7b511a761d` at tree
`75b3c9c43ce61c91661a32241b41b9901faf5809`: all 50 file contents were independently
checked. [Light UI CI run 39297543930](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39297543930)
passed in 1m 53s, including the test/check job and both amd64/arm64 container
build/start/restart-persistence jobs. BUILD_EVIDENCE.json records the current
runtime manifest separately from the historical pre-theme local images. Later
evidence-only documentation changes do not alter this tested runtime. Live
Supervisor/Ingress checks described below have also passed. No HA identifiers,
credentials or raw live observations are published.

## Live qualification

The owner configured the current HA user's authorization and restarted Vision.
The app connected and populated the device/entity and automation inventories.
All nine displayed read capabilities were available: connection, state and
automation-trigger subscriptions, both registries, Repairs, system logs and trace
list/get. All observed automations received structural summaries.

The installed app initially had the older dark frontend. After refreshing the
Supervisor repository data and rebuilding only Vision, the light frontend loaded.
All seven navigation pages and an automation detail rendered with live data.
One successful retained run and one failed run were compared with the native HA
trace timeline; timestamps and completion/error classification agreed. No
automation was triggered, device controlled or HA configuration edited for this
comparison. Unobserved historical trigger events remained explicitly unobserved.

AI remained disabled and the audit button was disabled. The local evidence
preview opened without source entity IDs or credential fields. No provider request
was made. The history view contained availability and automation observations.

The rebuild retained the sampled original incident first-seen timestamps. A
separate Supervisor restart of only Vision then changed the monitoring session,
reconnected and completed a fresh inventory sync. All ten sampled incident
title/first-seen pairs survived that restart, including duplicate-pair counts.
These original Vision observation times cannot be regenerated by a fresh HA log
poll: new incident records use the current observation time.

Installed-source provenance is procedural: a refreshed repository, observed
Supervisor rebuild and the new frontend, plus a Git comparison proving Dockerfile,
locked runtime dependencies and all backend Python files are unchanged from the
first public backend commit to the tested candidate. The live container was not
exported for an independent byte-level image comparison. BUILD_EVIDENCE.json
separately binds the public source manifests and CI container checks.

Known limits: retained HA traces and permissions limit retrospective coverage;
history shows up to 300 recent observations per section, Issues up to 500 rows and
the Overview up to ten recent prioritized incidents. These bounded views do not
copy Recorder or imply an exhaustive historical table. Internal HA frontend reads
can change or become unavailable; coverage then degrades visibly. Live billable
provider behavior and a full accessibility audit remain unverified.

## Published release

The stable [v0.1.0 release](https://github.com/Patrick1610/vision-homeassistant/releases/tag/v0.1.0) is public and marked Latest. Its tag points to
`321337f2307db19455917bcb9dd9018b469a88da`, tree
`7f02fccdd10ba1921cf78a30c386abaa8559e8bb`; anonymous Git fetch and all 50
file comparisons match local `909df1a8c831c6aa4e7cd693ff8a60161ef8376e`.
[Release CI](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39317640835) passed in 2m 16s: tests and both amd64/arm64 container jobs.
The live-qualification documentation review `e9072db7-fc88-4108-9bd1-8035f6f957d6`
ended GO with no open findings after pending-publication wording corrections.
This post-publication checkpoint updates status only and does not move the tag
or change the tested runtime. Pre-publication status text in the immutable tag's
execution record describes that earlier snapshot; the actual release page and
this checkpoint establish completed publication.

## Wordmark update — 0.1.1

The owner approved a dark text wordmark with a small green decorative dot.
Only brand HTML/CSS and coordinated app/package/runtime/image version literals
change; monitoring/provider/HA behavior and dependencies remain unchanged.
All 76 tests pass; Ruff lint/format, JavaScript syntax, publication scanning and
diff checks pass. Targeted real-browser checks use synthetic data at 1280, 390
and 320 px: no document overflow or wordmark/badge overlap, expected dark/green
colors, working brand navigation and visible keyboard focus. No console warnings
or errors. External review `18dac065-b5be-4e2b-8329-3eb263ccfca4` ended GO with no
findings. No new live provider call or full accessibility audit is claimed.
[Main CI](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39320978798) passed in 1m 24s, including both architecture container checks.
PR #1 merged the complete update atomically. Anonymous source readback confirms
all 50 files match local `88b088fc8a30d13f5704d2076c6eceaf4ce99fe8`, tree
`384e08ae162bdcaab0ecaec0667d4249158781b6`.

Supervisor offered and installed 0.1.1; its default previous-version backup option
was retained. The dark wordmark/green dot and 0.1.1 badge rendered in Ingress.
Monitoring reconnected and completed a fresh sync; all ten sampled incident
title/first-seen pairs were retained. No HA device/automation actions or option
edits were performed. Installed-source provenance remains procedural (repository
update, Supervisor install, observed UI/version), without independent live-image
export/hash comparison. The stable [v0.1.1 release](https://github.com/Patrick1610/vision-homeassistant/releases/tag/v0.1.1)
is public and Latest, with tag `a76cdd916963cd832782e350eb97af74fc42d16c`
confirmed by anonymous browser and Git readback. The earlier v0.1.0 tag is unchanged.
This status checkpoint does not modify the released runtime.

## 0.2.0 phase A — data foundation, local evidence

The 0.2.0 implementation is in progress; the published 0.1.1 results above remain
historical. Phase A adds no HA read/write capability and changes no AI opt-in.
The existing 76 tests remain passing. New synthetic tests exercise preservation
of all seven legacy tables, private meta/settings and conservative reservations;
failed-migration rollback; stable cross-process hashes; persisted structural
reversions and historical/current source separation; bounded AST/trace evidence;
continued step errors with successful whole-run outcome; wait timeout semantics;
and typed graph persistence. The final local run passed **91 tests in 3.29 s**,
with the existing Starlette test-client deprecation warning. Ruff lint/format and
diff checking pass. An oversized error-text stress case exposed regex processing
before input truncation; bounding regex input and suppressing split-token
fragments resolves the issue and retains a per-run projection below 150 kB in
the synthetic maximum-step test. External review remains pending. Container upgrade and live HA
qualification are pending final release qualification.

### Corrective A review

Critical external review `70057443-b25f-46e4-852f-a9df98071c8b` rejected the first
A candidate. The corrected candidate adds bounded fair reads and recovery,
unknown-time handling, richer-evidence preservation, original-generation migration
backup/restore, frozen-v1 schema parity, upstream trace-cap coverage, bounded
logging, run/config binding and aggregate detail budgets. The final corrected
full suite passed **110 tests in 29.92 s** with the existing Starlette warning;
Ruff lint/format and diff checks passed.
The synthetic aggregate test creates 2,000 runs across 200 automations with more
than 32 MiB of candidate step detail: every run remains present, retained detail
stays within 8 MiB for `run_evidence`/256 KiB per automation, compacted records retain their
observed error counts and explicit coverage flag, and the closed database is
under 16 MiB. These are local synthetic limits, not a measured live household
storage rate. Actual probe: 8,383,060 retained detail bytes; 43,260 maximum per
automation; 1,614 compacted summaries; 13,537,280-byte closed database. An extra
small-budget test covers compact metadata overflow into the original run and
preserves its counts when a later stub is incomplete. A separate 5,000-entity graph test verifies stable rows and at most
two metadata changes for an unchanged snapshot. Follow-up external review remains
pending; no container/live/provider result is asserted here.

### A follow-up candidate

After the second review's standalone-condition finding and two independent
semantic regressions, **129 tests passed in 29.79 s** with the existing Starlette
warning. The new cases cover timestamp provenance despite legacy non-NULL values,
compacted completion-state updates, `action/N` false conditions, malformed-result
error vetoes, unchanged-stub write counts, registry/AST reuse, cleanup of stale
compact metadata, explicit unknown-time blockers, atomic event writes, NULL-start
orphan retention/cascades and a synthetic future 3→4 backup retaining original v1.
The 8 MiB bound applies to `run_evidence`; moved compact metadata, other history,
indexes, WAL and private migration backups remain outside that bound.

The controller separately qualified the exact previous candidate `92301fd` in an
actual ARM64 image built from its Git archive: a stopped 0.1.1 binary with a
synthetic persistent schema-1 fixture upgraded to schema 3, retained all seven
legacy tables and byte-identical options, preserved costs with reserved→uncertain,
kept private files at 0600, passed SQLite quick/foreign-key checks and survived a
restart with the original backup SHA unchanged. The actual old 0.1.1 binary
opened a restored copy of the schema-1 backup. In that exact base image SQLite
3.40.1 JSON1 worked and foreign-key enforcement rejected an invalid child.
No HA connection/token/provider was used. These previous-candidate results do not
replace the final image/live gates; the corrected candidate awaits fresh review.

### Parallel start-time ambiguity

Two synthetic regressions reproduce an older-started parallel wait timeout and
an aborted parallel wait without an error, each alongside a later-started false
branch. Both failed on `bc200e0` with an incorrect `condition_stopped` outcome.
Both now retain `stopped` and explicit unknown abort-reason coverage; timeout
evidence remains separate. Existing standalone false conditions and loop-timeout
guards still pass. Per-step timestamps/offsets are explicitly documented as step
starts, which cannot establish parallel completion order.

Commands: `.venv/bin/python -m pytest -q tests/test_phasea_p2.py
tests/test_evidence_regressions.py` passed 40 tests in 32.93 s;
`.venv/bin/python -m pytest -q` passed **131 tests in 38.42 s** with the existing
Starlette deprecation warning. `.venv/bin/ruff check .`,
`.venv/bin/ruff format --check .` and `git diff --check` passed. This is local
synthetic evidence; semantic/external re-review and the final image/live gates
remain pending.

## 0.2.0 A acceptance and B local investigations

Critical follow-up review accepted exact `7034e22` with no critical/high/medium
findings. The controller independently passed its 131 tests in 34.76 s. Its exact
ARM64 container upgraded a stopped synthetic 0.1.1/schema-1 fixture to schema 3,
preserved all seven legacy tables and unchanged options, retained conservative
usage costs, passed SQLite/file-permission checks and survived restart. A copy
of its original backup also booted in the actual old 0.1.1 image with schema 1,
version 0.1.1 and unchanged legacy rows/costs; the newer volume's main-file hash
remained unchanged. This evidence is separate from the final schema-4/image/live
gates. Jev remained unavailable without its configured key; no score is claimed.

The controller additionally parsed one native HA trace using the exact archived
A parser: failed outcome, 12.97 s duration, ten retained step observations and
two error observations matched the source. Parent/leaf observations can describe
one execution error. Only aggregate results are recorded here; this was before
the new live-app update and does not prove post-update acceptance.

B synthetic tests cover priority with 1,200 offline source cases; all three
local attention states without changing source rows; restart/snooze expiry;
legacy expected-offline exceptions; disabled/dynamic/area/label/trace-only
reference coverage; lost registry permissions; stable rule observation counts;
run comparison with matching, changed and missing configuration digests; unknown
run starts/gaps/redacted messages/log counters; tied/NULL history pagination and
filter injection; observed structural deltas; typed device/entity/automation
impact; local API workflows with AI disabled; trigger-event timing ties;
operator-looking backup preservation and stale duplicate metadata cleanup.
Static-case identity includes its configuration digest. Unknown-time refused
starts remain visible until authoritative time recovery permits ordering.

The lightweight automation-index test contains 200 automations, 4,000 historical
runs and 200,000 candidate AST nodes. The index uses one aggregate query, omits
AST/run lists and serializes below 150 kB. This checks bounded response/query
load, rather than assuming a fast empty fixture represents a large installation.
Independent source-helper probes found and verified corrections for backdated
refused-start observations and the dual graph identity of automation targets.

The controller's synthetic Safari preflight verified concrete-priority overview,
dossier→automation→failed/completed comparison, source-preserving local known
status, availability-history pagination and server search. Native select text
overflow on 320 px was reproduced and corrected; targeted readback confirmed no
page overflow, a working native menu and complete labels through menu/accessibility.
Full current-candidate routes/breakpoints and external B review remain separate
gates. No actual HA action, live provider request or 0.2.0 publication is claimed.

Final commands: `.venv/bin/python -m pytest -q` passed **160 tests in 32.01 s**
with the existing Starlette warning; `.venv/bin/ruff check .` and
`.venv/bin/ruff format --check .` passed. `node --check vision/static/app.js`,
`npx --offline prettier@3.6.2 --check vision/static/app.js vision/static/style.css`
and `git diff --check` passed. These results bind the local B implementation;
the subsequent frozen candidate still requires independent/external acceptance.

### B corrective qualification

Exact prior candidate `2f9899a7de6583969fb6784463f73b3e8eec710d` independently
passed 160 tests in 32.32 s and an ARM64 schema 1→4 upgrade/restart, private
backup verification and actual old 0.1.1 binary restoration of the original
backup. Settings, ledger and legacy history checks passed. Its synthetic Safari
qualification checked 11 rendered routes at 320, 390, 800, 801 and 1280 px with
5,207 entities: 55 checks, no page overflow/load error, with the old analysis
visible at all widths. These results belong to the previous candidate; external
B review still rejected its lifecycle, landing performance and static bounds.

The corrective regression file adds 22 synthetic cases:

- Known/expected/snoozed cases resolved and pruned before a new generation;
  stale overlays ignored before cleanup; independent real exceptions preserved.
  Repeated saves retain at most 50 notes without changing the source issue;
  restart, equal note times, retention and orphan cleanup are covered.
- An existing schema-4 database upgrades additively to schema 5, preserving
  source rows/annotations/notes and backfilling the matching first-observation
  generation. A colliding source-version backup containing operator bytes
  remains byte-identical; the new private unique backup is valid schema 4.
- Eighty persisted automation projections with 1,000 advice-producing nodes each
  produce 80,000 observed findings, select 500 with at most 20 per automation,
  and explicitly report 79,500 omissions. One batched static-issue lookup replaces
  per-finding reads. Availability precedes information-level advice. Previously
  retained budget-omitted sources remain active with limited coverage, not resolved.
- Real HTTP overview/cases routes run after one monitor refresh with 200 persisted
  current projections of 1,000 nodes, 4,000 historical runs and 5,200 inventory
  entities, including a run-linked case. Three repeated requests per route read
  no AST payloads, execute no all-run window refresh and perform no database writes;
  overview/cases use at most 20/5 queries, responses stay below 250 kB and each
  request stays below a generous 2 s local regression bound. Both routes also
  complete while another SQLite WAL connection holds a write transaction.
  These are synthetic host regression limits, not HA-device latency claims.
- A changed outcome on an existing run with unchanged row count triggers refresh;
  completed monitor sync materializes findings without any GET. Unchanged cycles
  load no AST payload and skip the run window. Nine malformed/absent summary
  variants preserve source failures and return explicit unknown/limited evidence
  through overview, cases, dossier and comparison without HTTP 500 or AI usage.
- A Node frontend contract retains three concrete availability dossiers when
  availability is the only actionable source, keeps info below that fallback and
  preserves execution-error priority despite 1,200 availability cases.

Focused command `.venv/bin/python -m pytest tests/test_insights_review.py -q`
passed **22 tests in 1.10 s** with the existing Starlette deprecation warning.
The new schema-5 candidate still requires independent container/restore, browser
and external follow-up qualification. No live HA update, paid provider call or
0.2.0 publication is claimed.

Final corrective commands: `.venv/bin/python -m pytest -q` passed **182 tests in
31.74 s**, with the existing Starlette warning. `.venv/bin/ruff check .`,
`.venv/bin/ruff format --check .` (41 files), `node --check vision/static/app.js`,
`npx --offline prettier@3.6.2 --check vision/static/app.js vision/static/style.css`
and `git diff --check` passed. Product mutations pause on the corrective commit
pending independent and external follow-up; these local passes are not B GO.

### B second corrective qualification — migration retry bounds

The preceding `5a2e8bc` candidate independently passed 182 tests in 32.83 s,
exact ARM64 schema 1→5 upgrade/restart and actual old-0.1.1-binary restoration.
Eleven rendered routes at 320 and 1280 px had no anomalies or lost legacy analysis;
an additional availability-only 320 px check showed three concrete dossiers and
a working dossier link. Those results bind that previous candidate. Its same-
channel external follow-up still found unbounded backup growth on failed retries.

Twelve new synthetic regressions now cover:

- Ten intentionally failed migration/restart attempts retain one full-copy inode
  and constant backup bytes, preserve the original snapshot and leave no temporary
  files. Committing a source change only to WAL leaves the main file SHA unchanged
  but creates a distinct fresh rollback snapshot; subsequent identical retries
  reuse that snapshot. The original still contains the first generation.
- Three changed source revisions reach the retained limit. Identical-source retry
  still reuses a snapshot; a further changed source fails closed without accepting
  stale data, changing the source schema or growing retained copies.
- Both arbitrary-byte and valid-but-stale SQLite files colliding at the exact
  source-version filename remain byte-identical with their permissions unchanged.
  A new private snapshot contains the current committed source data.
- Free space just below copy-plus-reserve and aggregate bytes below the required
  copy stop before snapshot creation or DDL, preserving schema, source bytes and
  usage reservations. Partial-copy exceptions remove only their own temporary.
  An uncertain crash/operator temporary blocks allocation without deleting or
  chmodding it. The application exposes the fixed capacity reason without paths,
  credentials or raw exception text.
- A legacy metadata map for 3,000 limited automations is compacted at the monitor
  write boundary. Overview/cases return exact aggregate counts in less than
  1,024 serialized bytes, with no GET writes; the requested automation detail
  retains its own counts.
- Case pages at `limit=100`, all run-linked, cover shared pairs, missing runs and
  malformed evidence, plus a separate page where all 100 runs are missing. Each
  page uses one bulk run/evidence query and at most five queries overall; overview
  stays within 14. There are no AST/window reads or GET writes. Missing lookups
  do not trigger per-card fallback. A concurrent WAL writer still permits reads.

Final command `.venv/bin/python -m pytest -q` passed **194 tests in 36.76 s**,
with the existing Starlette deprecation warning. Focused
`.venv/bin/python -m pytest tests/test_phaseb_retry.py -q` passed **12 tests in
0.36 s**. Ruff lint/format (42 files), Node syntax, pinned Prettier and diff
checks passed. These are synthetic local checks; the new immutable correction
still requires independent container/browser qualification and same-stream
external follow-up. No C integration, HA action, paid provider call or 0.2.0
publication occurred.

### B third corrective qualification — atomic source and independent rollback inode

The previous exact `2f90d89` candidate independently passed 194 tests in 37.99 s,
container upgrade/restart and actual old-binary restore, plus ten browser checks.
Subsequent independent and external checks exposed the concurrent-WAL write gap
and live-inode backup alias. These prior passes do not establish their correction.

Nineteen new synthetic tests and the updated capacity regression cover:

- A competing WAL writer is blocked immediately after backup and at the first
  migration DDL. Both successful commit and failed migration release the reservation.
  A later legitimate source change produces its own fresh snapshot.
- Event-coordinated concurrent startups serialize. After the first succeeds, the
  second re-reads the new schema and does not take an obsolete backup. If the first
  fails, the second obtains the reservation and reuses the matching source snapshot.
  A child-process startup has a five-second timeout to catch self-backup deadlocks.
- Candidate and original aliases of all three live main/WAL/SHM inodes are rejected
  before copy/DDL without deleting or chmodding aliases. A separate restored-source
  fixture proves byte-for-byte identity with a fresh SQLite API copy and reproduces
  the dangerous case; fail-closed rejection leaves schema 4 and original bytes intact.
- All three uncertain temporary sidecars stop startup with fixed actionable pattern/
  directory guidance and no arbitrary filename disclosure. A valid database whose
  estimate alone exceeds the snapshot budget receives the distinct size-limit code.
- Valid snapshots with differing application-id header bytes cannot grow beyond
  the fixed retained-copy cap. Current data/schema remain unchanged on rejection.
- All 100 cards with distinct entity IDs and numeric run IDs, including zero,
  resolve in one batch within five queries, with no AST read or GET write. Removing
  a current pointer cleans only ephemeral rule metadata and preserves retained
  source issues, structural history and unrelated counters.

`.venv/bin/python -m pytest tests/test_startup_atomic.py -q` passed **19 tests in
1.12 s**; `.venv/bin/python -m pytest -q` passed **213 tests in 33.12 s**, with
only the existing Starlette warning. These are local synthetic results; independent
container/browser/source qualification and same-channel external review still
apply to the immutable correction. C, public release and live-update gates remain
separate. No HA action or paid provider request occurred.

### Accepted B basis and 0.2.0-dev.1 packaging

The exact accepted foundation is
`9a3dd713e1ffa3234392991ad62adeb9fd98a98a`. Its fourth same-stream external
critical review returned GO with zero critical/high/medium findings. Independent
local verification passed **213 tests in 33.17 s**, Ruff lint/format, JavaScript
syntax and diff checks. An exact ARM64 image
`sha256:3661ca1399d0ba52cfb676933103438d52b6ea4ec2deda3e887d7d2c71253727`
passed schema 1→5 upgrade, restart and restoration of a copy of the original
snapshot with the actual 0.1.1 binary. Existing history, settings and usage
reservations were preserved. Synthetic source checks included real concurrent
startup processes and all six live main/WAL/SHM aliases. Private controller
qualification artifacts are deliberately excluded from the public repository.

The development package coordinates module, Python project, Supervisor and image
version metadata at **0.2.0-dev.1**. Packaging assertions also bind the unchanged
repository URL/slug and default AI/daily-audit settings. The payload is the accepted
B foundation: local dossiers, evidence comparisons, dependency/structural history
and bounded searchable observation history. New targeted AI, diagnostic privacy
profiles and preview/send conversations are not included or claimed here.

This package still requires its own normal review, both-architecture build,
public CI/source readback and live Supervisor update. No result from the prior
foundation is presented as proof of those later actions. AI remains off by default;
no paid provider request or Home Assistant write is part of this qualification.

Local package verification passed `.venv/bin/python -m pytest -q`: **213 tests
in 35.32 s**, with the existing Starlette deprecation warning. Ruff lint/format
(28 Python files), JavaScript syntax and diff checks passed. No monitoring,
schema or provider runtime code changed relative to the accepted B foundation.

Before publication, the controller's rendered-browser check detected the old
hardcoded 0.1.1 wordmark badge. The preview correction derives that visible HTML
value from runtime version metadata. Its HTTP regression changes the runtime
value and asserts the visible badge, removed placeholder and matching health
response. This corrects a packaging defect; prior local passes did not cover it.
The focused packaging/HTTP run passed four tests in 0.24 s, with the existing
Starlette warning; Ruff lint/format and diff checks passed. The corrected preview
still requires exact-tree full/container/browser qualification before publication.

## C implementation candidate — targeted AI, privacy and request consent

C is implemented above the corrected development-preview base
`4806463d33b020ecd48ccf0f127c4c034a534f38`, with version metadata deliberately
retained until final D packaging. This section records synthetic implementation
qualification; C external acceptance, final container/publication and live update
remain separate pending gates.

The complete local suite passed **278 tests in 35.48 s**, with the existing
Starlette/httpx deprecation warning. The six AI test files passed **82 tests in
1.11 s**, including 64 new tests beyond the corrected preview baseline. Ruff
lint/format (37 Python files), Node syntax, pinned Prettier 3.6.2 and diff checks
passed. The original closed HA gateway and image/module/project version literals
have no C diff.

Meaningful synthetic coverage includes:

- One mixed trace selects distinct template, wait-timeout and communication
  paths, retaining matching successful counterexamples. Physical siblings follow
  the failed action's target; current missing references do not become old trace
  references. A distant missing reference wins bounded node selection. Typed
  template errors mentioning communication cannot qualify as device failures.
- Exact frozen bodies for both configured providers survive local evidence
  refresh unchanged. Native Anthropic/OpenAI strict-schema request shapes,
  recursively closed/required objects, UTF-8 sent bytes, response usage, refusal,
  incomplete output, malformed/oversized replies and categorical errors use
  `httpx.MockTransport`; no external provider endpoint is contacted.
- Diagnostic consent, model/rates/configuration changes, restart, local-only and
  off→on invalidate old tokens. Intention revocation during both backoff and
  technical failover prevents every subsequent reservation/call. Concurrent or
  repeated sends claim one request once. Current-round support/counterevidence
  and requested-section allowlists are validated after received usage is billed.
- Follow-ups reject another target/task/profile/run/comparison, preserve the
  original snapshot and open-segment duration, reject stale parent previews and
  old round references, and allow at most one reviewed enum expansion/four rounds.
  Context respects UTF-8/message limits with explicit omissions; compact never
  replays free-form questions or provider prose.
- Quoted JSON/Python/escaped assignments, HTML/Unicode text, invalid surrogates,
  configured secrets and identifier categories in nested keys/error prose are
  sanitized. Alias substring/collision and cross-round stability cases pass.
  Redaction remains incomplete for arbitrary personal data; diagnostic consent
  and exact request inspection remain essential.
- Real local HTTP tests complete preview/send/revoke and scoped follow-up, reject
  the old bypass endpoint body and retain searchable legacy analyses beyond 50.
  A Node contract checks old diagnosis rendering, output escaping, task selection
  and exact run/comparison links. Additive schema 5→6 retains old analyses/options/
  ledger and private schema-5 backup. Restart preserves exact prepared payloads,
  marks interrupted requests/usage uncertain and retains attempt links. Disposable
  previews stay capped at 32 without reserving usage; daily compact once-per-day,
  primary recovery, budgets/failover and cancellation regressions remain green.

Independent early probes used mutable synthetic source and found no demonstrated
canary leak in either provider body. A template/communication overlap they found
was fixed and independently re-probed. A controller browser preflight completed
compact device-communication preview with exact selected runs, primary HTTP-mock
503, OpenAI mock response, scoped validation follow-up and recovered primary.
All three actual adapter HTTP attempts matched their preceding preview bytes;
the ledger retained one uncertain reservation and two received mock usage rows.
Legacy findings/manual checks/validation/unknowns rendered without 1280 px overflow.
These observations are preflight evidence, not final frozen-candidate acceptance.

Official schema/response references and provider limitations are linked in
[architecture](ARCHITECTURE.md#targeted-ai-investigations--c-implementation-candidate).
No real model compatibility, paid billing result, Home Assistant write, live C
installation or stable 0.2.0 release is claimed by these tests.
The publication scanner passed for the tracked tree and all reachable Git history;
ignored preparation, private fixtures and controller review artifacts are excluded.

### Dev.1 publication/live evidence reported by the controller

The corrected development-preview tree `40f8a42559dd5d389767c7f67278e3f38de878ef`
(source `4806463d33b020ecd48ccf0f127c4c034a534f38`) was published through
[PR 2](https://github.com/Patrick1610/vision-homeassistant/pull/2). The controller
recorded push/remote readback, six successful PR checks and successful main tests
plus both architecture containers, followed by a same-slug 0.1.1→0.2.0-dev.1 update
with Supervisor's previous-version backup enabled. Live Ingress reported that
version, running/fresh monitoring and read-only health. Twenty existing settings
and bounded samples of 300 availability rows, 300 runs and 500 issues had zero
missing records or changed stable fields. These are sampled API comparisons,
not a full private database export or stable-release acceptance.

One naturally retained failed HA trace was compared with the exact live Vision
selection: run/outcome/last step/context, step/error/duration projection and
run-bound configuration/digest matched. No execution was triggered. A separate
latest-run backlog counterexample remained and led to the bounded scheduler
correction below. User-authorized legacy-provider audits produced received
analyses; this qualifies the legacy preview only, not C's new native
structured-output protocol. No raw HA observations or provider credentials were
included in public fixtures/reviews.

### C consolidated corrective candidate

The three-part critical review of frozen `5bce91b` retained eight medium issues;
proposed unknown-cost refunds, configuration failover and stale-reference reuse
were withdrawn. Official documentation confirmed generally available native
Anthropic `output_config.format` with no beta header. The controller authorized
this correction, with mandatory exact-commit independent follow-up still pending.

New synthetic coverage exercises pre-reservation unsupported-task blocks, sanitized
provider-origin compact history, typed extra sections, current-citation native
enums, preserved in-flight revocation and unique redacted keys. Real local HTTP
and native MockTransport tests return 202 while a provider gate stays closed,
close the initiating client, inspect a body-free status response and then recover
the completed analysis using another client. Duplicate sends are rejected before
a second attempt. Deadline/shutdown/unexpected-error cases keep uncertain costs
and safe status breadcrumbs; revocation during an in-flight attempt retains its
promised result space and prevents failover.

Storage regressions preserve exact completed bodies/history when byte/count
admission rejects a new preview, reserve space for multiple pending results and
store a maximum-field valid Unicode diagnosis within its explicit 1 MiB result
bound. A separate smaller-bound test keeps billed usage when storage is rejected.
A receipt failure rolls usage and attempt linkage back together. Schema 6→7
backfills prior attempt identity without body changes; 120-day request pruning
leaves receipt/usage identity across restart, and 410-day usage expiry cascades its
receipt. Recent-50 API responses exclude result/evidence payloads, while a selected
legacy analysis returns its exact original mapping and history search remains.

The scheduler regression uses 165 automations × 22 retained runs each. Within
15 cycles all newest successes are inspected and 15 historical failed runs are
backfilled, at no more than 12 reads per cycle; the following cycle devotes all
12 slots to remaining history and never refetches full/compacted evidence. The
controller's independent frozen diagnostic-scale check used 5,200 entities,
5,432 identifier values, a 200k structural projection, 4,000 runs and 100 cases:
HTTP previews measured 24.3–40.1 ms on that one host, with no known test identifiers,
three planted secret canaries or raw digest in either body, and zero external
calls. This is bounded synthetic evidence, not universal privacy/performance proof.

Corrected C still requires frozen external review, container upgrade/restart and
real browser qualification. The original C browser mock proved byte identity and
consent/revoke flows, but found two long-preview paragraphs clipping internally
at 320 px; D must wrap these and verify actual readable content. D visual UX,
release-candidate publication/live native-C provider qualification and the stable
0.2.0 release remain open gates. Jev has no configured API key; no score is claimed.

Corrective local commands: `.venv/bin/python -m pytest -q` → **330 PASS, 38.54 s**,
with one existing Starlette/httpx deprecation warning; `.venv/bin/ruff check .`,
`.venv/bin/ruff format --check .` → **PASS, 55 Python files**;
`node --check vision/static/app.js`, pinned Prettier 3.6.2 and `git diff --check`
→ **PASS**. These are canonical-source local results, not container/public/live-C
acceptance. The prior ignored draft's 315 tests and subsequent focused checks are
preparation evidence, superseded by this complete corrected-source run.

The publication scanner passed for the staged tracked tree and all reachable Git
history, including all new synthetic tests; no secrets/private paths were detected.

### C3 accounting and withdrawal review follow-up

The critical follow-up on `24a4953` closed all eight prior accepted medium issues
and five lows without a reported privacy/billing regression. It found two new
medium issues: repeated body-byte scans during admission, and automatic form-edit
withdrawal of a displayed running request. This correction remains subject to
independent exact-commit review and browser/container qualification.

Schema 8 adds integer per-record byte accounting and six transactional triggers.
The schema-7 upgrade test preserves old analysis/request columns and content,
backfills exact multibyte UTF-8 lengths, and checks restart. Update/delete/rollback
and ordinary pruning keep sizes synchronized. A SQLite authorizer forbids body
reads while status-only writes and `ai_storage()` execute. The near-cap ASGI test
populates 480 completed requests plus 480 analyses (about 60 MiB), prepares a real
HTTP preview, verifies remaining headroom, then proves admission refusal preserves
all old rows and charges nothing. Captured SELECTs contain no retained-body scan
or `length(cast(...))` aggregation. The loose two-second local guard is a regression
check on this host, not a production hardware latency guarantee.

Five real-DOM tests run the shipped `index.html` and complete `app.js` in exactly
locked, test-only jsdom with fully synthetic transport. They cover running-input
edits with zero implicit revokes plus explicit withdrawal, unused-preview input
revocation, visible withdrawal errors with Send disabled, a pending POST followed
by a lost 202 response, and visible withdrawn received conversation rounds with
continuation disabled. A transport error conservatively leaves a possibly started
request in flight. No layout/native-browser claim follows from these DOM tests;
the controller's delayed Safari reproduction must be repeated on the frozen fix.
Node.js 22+ is required for this test path and CI pins Node 22; the Python runtime
and container have no Node/jsdom dependency.

Additional regressions prove independent schema-enum copies across fields,
providers and rounds, a clear empty-evidence failure before storage/charge,
withdrawn follow-up audit visibility and server-side continuation rejection, and
atomic settings fields-set restoration after a failed cross-field assignment.
The compatibility GET preview remains read-only, bounded and restricted to its
three legacy task shapes; exact sendable previews continue to use POST.

Local verification: `.venv/bin/python -m pytest -q` → **339 PASS in 44.46 s**,
with the existing single Starlette/httpx deprecation warning; `npm test` → **5 PASS**;
`.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` → **PASS, 56 files**;
`node --check vision/static/app.js`, pinned Prettier 3.6.2 and `git diff --check`
→ **PASS**. No real HA/provider request, D acceptance, public change or final
release was performed by this correction.

The publication scanner passed for the complete staged tracked tree and all
reachable Git history, including the locked test dependencies and synthetic tests.

### Accepted C3 and historical dev.1 publication checkpoint

The controller accepted exact `3e533aac7ecf16f55118a869b03f9cb9502e4f43` after
critical sequence 6 GO (zero critical/high/medium), independent **339 Python tests
in 51.14 s plus five DOM tests**, both actual architecture builds/HTTP/restart
smokes and schema 1→8/restart/actual old-0.1.1 copy-restore. Independent AI checking
passed 144 focused tests and twelve native-HTTP/ASGI groups. Schema 6/7→8 probes
preserved all 20/21 old tables, ten receipt links, options and backup bytes;
30 counter transitions and four injected atomic migration failures/retries passed.
Near-cap accounting reads no full-body byte sums. Actual Safari verified unused
input revocation without a call, running input without implicit withdrawal through
technical failover, exact preview/send bytes, and explicit round-2 withdrawal with
received result/usage/audit retained and continuation disabled. These are synthetic
provider checks, not live native-C model qualification. Jev has no key or score.

The earlier source `4806463d33b020ecd48ccf0f127c4c034a534f38` was published as
0.2.0-dev.1 through [PR 2](https://github.com/Patrick1610/vision-homeassistant/pull/2).
Its tree `40f8a42559dd5d389767c7f67278e3f38de878ef` was independently read back;
[main CI 39404961604](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39404961604)
passed tests and both architecture containers. The controller verified the same
installed slug upgraded 0.1.1→dev.1 with previous-version backup enabled, fresh
read-only monitoring and Ingress. Twenty original options and bounded samples of
300 availability rows, 300 runs and 500 issues retained their compared stable
fields; this is not a full database export. One naturally retained failed run
matched native HA steps/error/duration/context/structure without executing an HA
action. Legacy dev.1 provider requests succeeded after owner configuration;
those calls do not validate the new native C structured-output schema or reference
enums. Its latest-run backlog counterexample was corrected and synthetically
qualified in C; final live recency checks remain open.

### D action-oriented release candidate — preparation

Source packaging now consistently names **0.2.0-rc.1** in runtime, Supervisor,
Python project, Docker label, smoke default, tests and current documentation.
Visible version still comes from runtime metadata through the HTML placeholder.
The repository URL, slug, architecture/access flags, default opt-ins, settings and
schema 8 are preserved. A narrow comparison-copy correction calls digests retained
structures; it makes no raw-configuration equality claim.

Overview groups duplicate source observations of one run and availability before
applying a three-card cap; one green primary CTA leads to the dossier or filtered
availability queue. Counts support the investigation. Dossiers use aligned
problem/evidence/manual-plan/validation steps, bounded observation and step-start
timelines, visible gaps and disclosures for long facts, relations and local status.
Success with continued step errors remains separate from failed execution.
Intelligence initially shows three short proposals; full text, further proposals,
previous rounds, usage and legacy mapping remain available behind details. Exact
bodies, diagnostic consent, budgets and server-owned request behavior remain.

Real-DOM regressions cover zero/one/many groups, availability-only count/link,
duplicate run ID zero, escaping/long text, short versus full AI proposals, legacy
mapping on demand, selected run/comparison links, unknown time and continued errors,
headroom, and focus/open panels including engagement during an in-flight refresh.
The delayed-browser preflight also exposed a real fast-completion race: a job could
finish before the first retained-request GET and hide its result. One terminal
handler now serves both initial load and polling, opening completed results and
surfacing safe failed/uncertain/withdrawn states plus received-result links without
another POST or needless terminal polling. A rejected send restores an unused
preview only after one explicit lightweight server confirmation; unknown status
stays conservative. Full-HTML/app DOM tests pin these paths.

RC exact-source browser checks (all eight fixture variations and relevant widths),
containers, independent review, public CI/tree readback and live Vision upgrade/
native compact Anthropic/history checks remain open until the controller records
their actual outcome. The stable 0.2.0 tag/release is not created by this preparation.
The authorized output-option change is a controller live configuration gate;
existing provider, model, key, budgets and other settings are retained. Product
defaults and saved values are not silently changed here. Public-source research remains only
the deferred 0.2.1 scope in VISION_SPEC.md.

D local commands: `.venv/bin/python -m pytest -q` → **339 PASS, 38.35 s** with the
existing one Starlette/httpx warning; `npm test` → **19 PASS**; focused workflow,
insight and packaging command → **32 PASS**. Ruff lint/format (56 Python files),
`node --check vision/static/app.js`, pinned Prettier 3.6.2 and `git diff --check`
passed. Early mutable Safari snapshots corroborated overview/dossier navigation,
320 px preview wrapping and revealed the now-tested fast-completion race; they do
not replace browser qualification on the immutable D commit.

D publication scanning passed for the complete staged tracked tree and all
reachable Git history, including the new synthetic DOM fixtures.

### D2 consolidated correction — audit access and resilient local dashboard

Independent qualification of exact `b7764fdf33cc4e23eb31c583aa945591d1c1f6d7`
passed root 339 Python tests in 41.04 s, 19 DOM tests, both architecture builds/
HTTP/restart and schema-1→8/old-0.1.1 copy-restore. Its actual immutable Safari
matrix comprised 32 overview checks (eight named variations × 320/390/768/1280)
and twelve other navigation checks. Those initial readings reported no load/page-
overflow errors, but a later settled recheck proved D1 long_names/320 was already
552 px wide: that cell's early reading was not valid settled layout evidence.
Frozen mock primary/backup sends matched their displayed bytes. The other named
immutable checks remain bounded normal-path evidence; they did not cover every
failure/audit branch. The critical review then rejected D1 for one high and two
mediums, and independent mixed-error testing found a local wrong-step instruction.
No D1 release/public/live GO follows from its passing normal-path checks.

This authorized D2 correction keeps plain completed request links on the exact
frozen body/digest/consent audit, with a prominent received-analysis link. Plain
running audits may observe completion without leaving that audit. Only a send/
watch session auto-opens a result; its one-shot entry is replaced via Location so
browser Back cannot loop through the auto-redirect. Failed/uncertain/withdrawn
states and received-result links remain visible, without a second send or restored
continuation rights. DOM tests cover completed plain audits, fast-completed sends,
Back, running-audit completion, explicit withdrawal and unknown transport state.

Primary priorities survive failed availability-count or recent-change reads.
Unknown counts/history are explicit; retained availability samples remain linked
without inventing a total, and disagreeing snapshots are labelled. With incomplete
supporting coverage an empty sample is not advertised as no issues. Initial
primary failure is an error. Every background failure retains the last-loaded DOM,
focus, open panels and selected text, with an explicit refresh-failed notice.
Real ASGI tests pin the exact bounded availability and changed-history query strings.

Task links and local manual instructions now use one relevant typed observation:
mixed template/communication/timeout failures select their matching path, a timed-
out wait flag works without error prose, and missing paths remain unknown. The
five lows disclose/reveal references beyond four, deduplicate retained source
checks behind details, retain the concrete last-gap time and sibling-case links,
and use the server's comparison limitation. Repeated evidence links include
accessible problem context. No backend/store/schema/provider, policy/default,
version or retention change is part of D2; the same 0.2.0-rc.1 remains unpublished.

A separate frozen-D1 warm/WAL fanout probe measured 16.625–18.555 ms across tested
routes, including 18.285 ms with an external WAL write lock, with 17 read queries,
zero writes and twelve HTTP 200s. This one-host result did not justify a query or
threading architecture change. Relevant frozen-candidate browser/review checks,
public RC CI/tree readback, live native-C/history qualification and stable release
remain separate pending gates. Jev has no configured key and no score.

D2 final local verification: **341 Python tests passed in 38.67 s**, with the
existing single Starlette/httpx warning. **27 complete-app DOM tests passed**;
the two new real ASGI dashboard-contract tests also passed independently. Ruff
lint and format (57 Python files), Node syntax, pinned Prettier 3.6.2 and diff
checks passed. The publication scanner passed over the staged tracked tree and
all reachable history, detecting no secrets/private paths. These are local
corrective-candidate checks; independent D2 review/browser acceptance and all
public/live/stable gates remain pending.

### D3 narrow-screen correction and small review follow-ups

Critical D review sequence 2 closed the D1 high, two mediums, five lows and the
independent mixed-step defect on D2 `9fadab4b6f972d02359ad065be657158c64ba390`.
Its NO_GO was solely the reproducible settled long_names/320 overflow. Native
Safari identified `small.affected-id` at width 515 px/right 552 px inside a 271 px
card. D1 `b7764fdf` reproduced the same width after settling, so this is an older
D defect, not a proven D2 regression. The previous early long-name meter pass is
explicitly corrected here; original ignored proof files are retained unchanged.

The controller independently confirmed D2 341 Python/27 DOM tests, nine additional
DOM groups/six mixed-selector cases, both container checks and schema-8 checks.
Actual D2 Safari request-audit, two mock-adapter exact bodies and Back paths passed.
No actual native provider or final stable qualification follows from those mocks.

A clearly labelled ignored D2+CSS scratch preflight bound base `9fadab4b6f972d02359ad065be657158c64ba390`
and CSS-only patch SHA-256 `aa969c910f43484dcfd2d19e0bad1d3afe6f1df0b45243114a2ab8795b30de6f`.
Native Safari then measured page width 303 px at viewport 320 px, both with the
related-source disclosure closed and opened; its complete source key, exact
link and focus remained accessible. This is scratch preflight, not immutable D3
acceptance. D3 applies that affected-id width/wrap rule and includes small/span/
strong/time in the existing non-clipping text-wrap contract for long trace paths.

Four low follow-ups preserve the original history entry after a lost POST response
resolves completed, label the primary total as attention cases as of that read,
keep changes-only failure separate from priority coverage, and deduplicate refresh
warnings without replacing unrelated user notices. Added complete-app DOM branches
cover those paths plus exact-request links on new/legacy analyses, disagreeing
availability totals and full long related keys/trace paths. An initial CSSOM test
expectation omitted the existing observation suffix; the test was corrected and
no product behavior was changed for that harness repair. No Python runtime, store,
schema, provider, version, defaults or retention change occurs. Final D3 exact-source
browser/review acceptance, public RC/live native checks and stable release remain
pending with the controller; Jev still has no configured key and no score.

D3 local verification: **341 Python tests passed in 37.47 s**, with the existing
single Starlette/httpx warning; **34 complete-app DOM tests passed**. Ruff lint/
format (57 Python files), Node syntax, pinned Prettier 3.6.2 and diff checks passed.
The CSSOM contracts are styling/navigation guards, not a browser pixel-layout
claim. Personal live model/limit/budget configuration values were removed from
public documentation; the controller retains the authorized option change and
preservation contract in private evidence. Freeze this unchanged RC for settled
native-browser and same-channel critical-review acceptance.

### RC CI operational repair — full Node fixture through stdin

The first public RC PR CI test job reported **340 passed / 1 failed in 72.03 s**.
The failed frontend availability contract passed its generated script as one
Node `-e` argument; the complete 1,200-record fixture exceeded Linux's per-argument
limit and raised `Argument list too long` before Node executed. The operational
repair feeds the same complete script through stdin. All 1,200 records and all
original assertions are retained; no downsize or new skip is introduced.

The other Node `-e` test was inspected: its current helper slice is 5,965 bytes
plus small literal cases, without the large inventory fixture, so it needs no edit.
Only this test transport and this execution note change; all product/runtime/UI,
version, options, storage, schema and provider bytes remain bound to accepted D3.
The focused repaired test passed. Public CI rerun/readback and later live/stable
gates remain the controller's separate evidence; no CI success is assumed here.

Local repair verification: focused contract **1 PASS**, full Python suite
**341 PASS in 36.84 s**, with the existing single Starlette/httpx warning.
Ruff lint/format (57 Python files) and diff checks passed. This does not replace
the pending Linux public-CI rerun.
