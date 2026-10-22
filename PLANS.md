# Vision v0.1.0 execution record

Owner authorized all four milestones, dependency installation, testing, local Git,
public GitHub publication and v0.1.0 release. Read-only HA is absolute.
Canonical root inspected: empty except existing unborn `main` Git repository;
no remotes, history or user changes. Single writer, direct owner mandate.
The agent-workflow skill was consulted; its custom-agent runtime is not activated
because this execution uses the owner's direct development mandate, not delegated
custom roles. Permanent milestone state is recorded here.

## Milestone 1 — Foundation (implemented and locally/live verified)

- [x] Root / instruction / Git inspection; preserve existing `.git`.
- [x] AGENTS, permanent specification, architecture and execution record.
- [x] App packaging, persistent storage, peer and user-authorized Ingress, usable interface.
- [x] Foundation tests and external review GO.

## Milestone 2 — Monitoring (implemented and locally/live verified)

- [x] Read-only HA transport, reconnect, inventories, traces, Repairs/logs.
- [x] Persistent incidents, exceptions, availability and execution statistics.
- [x] Integration simulations, coverage limitations, final log-counter corrections and review GO.

## Milestone 3 — Intelligence (implemented; externally reviewed GO)

- [x] Anthropic/OpenAI, common validated evidence schema, opt-in/minimization.
- [x] Retry/failover/recovery, reservations, budgets and usage history.
- [x] Manual/daily/incident/automation analyses; tests and external review GO.

## Milestone 4 — Release (published and independently verified)

- [x] Complete dashboard, desktop/mobile browser verification, docs/security/privacy.
- [x] Test suite, both architecture builds/start/persistence, four review streams GO and full-history secret scan.
- [x] Live Supervisor/Ingress, inventories, capabilities, native trace comparison and restart-history verification.
- [x] Public GitHub repository and anonymous source readback.
- [x] GitHub CI green (run `39294357509`, public candidate `dc8603c`).
- [x] v0.1.0 tag/release published after live qualification; public page and tag readback verified.

## External access

Initial `gh auth status`: stored account token invalid. Authentication requested;
development continues. Docker CLI available but daemon initially unavailable;
local Colima availability will be checked before container validation.

## Verification progress

76 pytest tests passed, including real local WebSocket/REST simulation and reconnect,
private database concurrency/persistence, provider HTTP contracts, failover/consent,
billing reservations and upstream trace golden cases. Ruff and JS syntax passed.
ARM64 and emulated AMD64 container HTTP/start/restart persistence passed for the
pre-light-UI local images; byte-identical source binding is in docs/BUILD_EVIDENCE.json. 76 tests also
passed inside the Linux image with development-only test dependencies. Browser exception save and
mobile width verified with synthetic data. See docs/VALIDATION.md for precise limits.
Live qualification is recorded below; no billable provider call is claimed. Public source is
verified independently below; the final release is recorded in the completion checkpoint.

## Safe continuation at the access gate

The initial implementation at `e2046c3e254bd4af5c912589f49cd08a1a0c7963` was
superseded by `898ebb7cff1fbb9c1c134ed67979e6b8545cfd10` after a real HTTP
regression exposed incomplete reads of fragmented automation configuration JSON.
The bounded stream reader now consumes the complete response, rejects oversized,
malformed and non-object data, and retains the exact read allowlist. Four new
network cases failed before the correction and pass after it. Two additional
smoke-readiness tests pass. Both rebuilt images passed HTTP before/after restart,
app-loaded exception persistence and an independent volume check. Their source
files were compared byte-for-byte with this implementation. External review of
the correction ended GO, with no open critical/high/medium findings.
The shared builder's cold-start socket failure was repaired by bootstrapping it;
the completed images and source comparison, rather than that failed attempt,
are the build evidence. Later evidence-only documentation does not alter runtime.
No final v0.1.0 tag/release was created. The owner explicitly selected GitHub's
browser interface for repository creation and source upload. All 50 audited
files, including hidden metadata and nested source folders, were uploaded to
`Patrick1610/vision-homeassistant` in the owner's authenticated browser session.
The separate CLI device flow was cancelled. Anonymous readback verified identical
file hashes and Git trees: public `18eef515b85d1f195664aa46bfadf3be0c689b00`
and local `889ac87505965d1cdc0518ab97a766189f205805` shared tree
`46a30cd223178f04c1b0c6800560216585300d49`. Await CI, install the concrete
candidate through HA OS/Supervisor, verify Ingress + capabilities + restart
history, and only then publish the v0.1.0 tag/release. Do not infer live
acceptance from local source-review GO. No real API keys have been supplied to
Vision, so provider live/billing behavior remains unverified. A browser-created
Git commit is a separate public commit from the local development history;
record both and verify tree equality instead of claiming identical commit IDs.

## Public CI portability correction

The first actual GitHub run `39293493525` passed both container jobs, including
startup/restart persistence on amd64 and arm64. Its test job returned 75 passed
and one failed: the packaging test's local-artifact exclusion matched the host
ancestor `/home/runner/work` and skipped the root app metadata. The exclusion now
checks repository-relative path parts; the upstream hidden/rootfs filter remains
unchanged. All 76 tests, Ruff, JavaScript syntax and publication scanning passed
locally after this test-only correction. External review `b622fc2e-52e8-4e2f-8edb-bd58a1fa0b6f`
returned GO, with no open critical/high/medium findings. The adjacent absolute
hidden/rootfs filter is retained deliberately to mirror upstream discovery.
Jev was retried but its key remains unavailable; no score is claimed.

Browser publication `dc8603ce9eab412cdefd0530622f1d80cd590d1f` matches local
`fd201aae00c31f255b96509a0ea5de7415ecdce8` at Git tree
`bb71a410b82b4129081b51c95ec7de9451ec2149`. GitHub CI run `39294357509`
completed successfully in 1m 57s: the test job and both architecture container
build/start/restart-persistence jobs passed. Runner notices about Node 20 action
migration to Node 24 and ubuntu-latest migration did not fail the run. The app
runtime is unchanged by this test correction and later validation documentation.

## Light Vision interface

The owner requested a white/light interface with Vision red/gold branding and
green accents. The existing frontend now uses white cards and sidebar on a warm
white canvas, deep red navigation/primary actions, gold details and green
positive statuses. The original CSS-generated V/gem mark needs no external
imagery or fonts. The palette decision is recorded in VISION_SPEC.md.

All seven routes and automation detail were checked in a real local browser
using synthetic data. At 1280, 801, 800, 390 and 320 px there was no page overflow.
The exception form saved locally; keyboard focus and skip-to-content preserve
the current route. Measured text contrasts pass 4.5:1 (muted canvas 4.98:1,
red status 7.19:1); the input border passes 3:1 (3.17:1). No browser warnings or
errors were observed. This is targeted verification, not a full accessibility
audit or a live Home Assistant installation test.

76 pytest tests, Ruff lint/format, JavaScript syntax, diff checking and the
publication scanner pass. External review `50f1f5ef-998d-40fe-aad5-91f89a742eba`
ended GO after two low notes were corrected; no findings remain. Jev was retried
but remains unavailable without its API key. The previous local images are
historical. The new runtime manifest is `31328546147424341568a72288303056a8c3a1541b66f58ac7e28868d2fecb86`.
Browser publication `5ddf6fb12d64bf63dc4f97d323a20d4d5c89e5ba` matches local
`3e2ca610c9a11f5796026685d8dd1a7b511a761d` at tree
`75b3c9c43ce61c91661a32241b41b9901faf5809` (all 50 files independently checked).
GitHub CI run `39297543930` completed successfully in 1m 53s: tests/lint/format/JS/
publication scan and both amd64/arm64 build/start/restart-persistence jobs passed.
Later evidence-only documentation changes do not alter the tested runtime.
Live Supervisor/Ingress qualification has now passed as recorded below.

## Resolved live Supervisor access gate

During the initial access-gate inspection, Supervisor reported Vision 0.1.0
installed and running, and Ingress served the expected locked page. AI and daily
audits were off. That initial inspection did not save options, authorize users,
restart the app or change HA devices/configurations.

The owner subsequently configured `allowed_user_ids`, restarted Vision and
reported completion. Live access was re-read and confirmed unlocked. No additional
account was authorized by the agent; AI remained disabled.

Repository data were refreshed and only Vision rebuilt to load the current light
frontend. Live inventories populated, all nine read capabilities were available
and all observed automations had structural summaries. Successful and failed
retained runs agreed with the native HA trace timeline. Every navigation page,
an automation detail, history and the local minimized AI preview rendered.
The audit button was disabled. No HA automation was triggered or configuration
edited. A separate Vision restart reconnected and completed sync; all ten sampled
incident title/first-seen pairs, including duplicate-pair counts, were retained.
Installed-source provenance uses the refreshed-repository rebuild and observed
new UI, with byte-identical backend/Dockerfile/dependency lineage across public
source. No independent byte-level comparison of the live container is claimed.
See VALIDATION.md for the precise scope and remaining known limits.
Final tag/release publication is now authorized by the original owner mandate.
Latest public candidate `82ae1714a0ec57ec1645f81e270cd02437b08579` passed CI run
`39298072551` in 2m 17s. This local checkpoint changes documentation only.

## Completion checkpoint — 2026-10-19

All four milestones are complete. The owner-selected GitHub browser workflow
published the stable [Vision v0.1.0 release](https://github.com/Patrick1610/vision-homeassistant/releases/tag/v0.1.0). Anonymous browser readback confirms the release is public and Latest.
Anonymous Git fetch confirms tag `v0.1.0` resolves to `321337f2307db19455917bcb9dd9018b469a88da`,
with tree `7f02fccdd10ba1921cf78a30c386abaa8559e8bb`, identical to local
`909df1a8c831c6aa4e7cd693ff8a60161ef8376e`. All 50 files were compared byte-for-byte.
The [release CI run](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39317640835) passed in 2m 16s, including tests and both container architectures.
The local working tree was clean at publication. This subsequent completion
checkpoint changes documentation only; the release tag is not moved.

Live Supervisor/Ingress, read-only monitoring, native trace comparisons and
restart persistence passed as detailed in VALIDATION.md. Optional AI remains
implemented and simulation-tested; no live billable request is claimed. The
read-only boundary, trace/observation limits, procedural installed-source binding
and unverified provider billing/full accessibility audit remain documented.
No personal HA data or credentials were uploaded. No future write capability
or recovery executor was added.

## Wordmark update — 0.1.1

The owner approved a dark Vision wordmark with a subtle green accent. Replace
only the header brand; retain the surrounding light red/gold/green interface.
Increment app/package/runtime/image metadata to 0.1.1 so Supervisor can offer an
update. The v0.1.0 tag remains immutable. Backend behavior, HA read allowlist,
provider evidence and credentials are unchanged. Browser publication follows the
owner's existing workflow after targeted UI checks, tests and external review.
76 pytest tests, Ruff lint/format, JavaScript syntax, diff checking and the
publication scan pass. The existing packaging version expectation was updated.
Real browser checks with synthetic data passed at 1280, 390 and 320 px: dark
wordmark, decorative 6 px green dot, no page overflow or badge overlap, working
Overview link and visible 3 px keyboard focus. Browser console has no warnings
or errors. External review `18dac065-b5be-4e2b-8329-3eb263ccfca4` ended GO with no
findings after two documentation nits were corrected. Jev remains unavailable
without its API key; no score is claimed. Public candidate and PR checks passed, then PR #1 was merged atomically.
The main CI run `39320978798` passed in 1m 24s, including both container
architectures. All 50 source files match local `88b088f` at tree
`384e08ae162bdcaab0ecaec0667d4249158781b6`. Supervisor offered and installed
0.1.1 with the default previous-version backup retained. The new wordmark and
version rendered, monitoring reconnected and completed fresh sync, and all ten
sampled incident title/first-seen pairs survived. No HA device or automation
action was performed. The stable [v0.1.1 release](https://github.com/Patrick1610/vision-homeassistant/releases/tag/v0.1.1)
was published through the browser; anonymous public-page and Git-tag readback
confirm `a76cdd916963cd832782e350eb97af74fc42d16c`. The v0.1.0 tag is unchanged.
This completion checkpoint changes documentation only.

## Vision 0.2.0 — authorized execution

The owner explicitly authorized the 0.2.0 scope in VISION_SPEC.md, autonomous
end-to-end development/publication/live verification and targeted AI solutions
for specific problems. Requested builder model/effort: gpt-6.1-sol/ultra; the
implementation agent cannot independently observe the effective runtime effort.
One productwriter works in this existing repository on main. No separate custom
workflow runtime, second checkout, history rewrite or HA write is activated.
The original release history above remains historical evidence.

1. **A — Data foundation:** accepted at immutable `7034e22` after critical follow-up review.
   Atomic schema 1→3 upgrade and restart recovery, persistent structural snapshots
   and transitions, bounded safe automation control flow/operands/references,
   all-step trace projection with whole-run semantics, existing-read typed graph.
2. **B — Local insight and investigation UI:** accepted at immutable `9a3dd713`.
3. **C — Targeted AI tasks/privacy/scoped conversation:** accepted at immutable `3e533aac`.
4. **D — Scale/security/UI/release qualification:** RC implementation under qualification;
   final public tree/CI/release and live Vision upgrade evidence are separate gates.

Phase A checks: `python -m pytest -q`, `ruff check .`, `ruff format --check .` and
`git diff --check` all passed: 91 tests, one existing Starlette transport
deprecation warning, final suite duration 3.29 s. The new synthetic tests cover all legacy tables and uncertain
reservations, atomic migration failure, structural source separation/reversions,
stable hashes across process hash seeds, safe operands/control flow, continued
errors, timeouts, step timestamps, truncation and typed graph persistence.
An oversized-error stress case exposed excessive regex work before truncation;
that run was interrupted after 89.94 s. Redaction now bounds input before regex
processing and drops a token split by the boundary, after replacing configured
secrets in full. A new test verifies partial secrets are not exposed; bounded
per-run error storage and the final full suite pass.
No live HA upgrade, public release or provider request is asserted for phase A.

### A corrective review iteration

External critical review `70057443-b25f-46e4-852f-a9df98071c8b` returned NO_GO.
The owner/controller authorized corrective A work; B remains closed until the
same review channel accepts the corrected immutable candidate. Jev was attempted
by the controller but remains unavailable without its configured API key.

Corrective work adds preserving schema 3, a private SQLite-consistent original
migration backup and restore instructions, an independent frozen v1 DDL fixture,
unknown/recovered run-time provenance, non-destructive degraded trace updates,
fair bounded detail reads/backoff/capability probes, per-run config associations,
safe path identity/coverage and HA deque saturation. Added detail budgets compact
only new step-detail projections while retaining all existing historical records.
Graph fingerprints avoid unchanged rewrites; all redaction paths have a hard
internal bound. Tests cover the reproduced loop timeout/old false-branch bug,
upstream 20-element truncation, exact observed/retained error counts, backup and
restore, all-schema parity, persistent circuit recovery/fairness, individual missing
traces alongside good traces, degraded stubs and aggregate storage.
Final corrective verification: 110 tests passed in 29.92 s, with the existing
Starlette test-client warning. Ruff lint/format and diff checks passed. The
2,000-run aggregate probe measured 8,383,060 retained detail bytes, 43,260 maximum
bytes for one automation, 1,614 compacted summaries and a 13,537,280-byte closed
database, preserving every run. A separate small-budget test exercises moving
compact metadata into its existing run without losing counts or allowing a
degraded stub to replace it. Unknown-time error observations also cannot replace
a newer proven incident link. Product mutations pause again for follow-up review.

### A follow-up correction

The follow-up critical review of `92301fd` returned NO_GO with no high findings
and one medium: a timestamped standalone false condition at `action/N` must remain
`condition_stopped`. The correction uses the terminal timestamped false result
without a path-name assumption, with unconditional error/timeout vetoes. It also
applies the independent legacy/unknown non-NULL timestamp authority correction
and advances compacted completion metadata on a later finished observation.

Low findings are addressed proportionately: unchanged list stubs avoid run/timing
upserts during backoff; registry cleaning and AST projection are reused; returning
rich evidence removes stale compact metadata; unknown-time blockers are visible
without changing incident history; event run/timing storage is atomic and recovered
NULL-start orphans get an observation time for retention. Future migrations create
a current source-version backup while preserving the immutable original; disk
and private-history implications are explicit in ARCHITECTURE.md.

Final local verification: 129 tests passed in 29.79 s, with the existing Starlette
warning; Ruff and diff checks pass. The 19 added regressions include seven that
failed on the previous candidate before the prepared correction. B remains
closed while the next immutable candidate receives semantic/external re-review.

### A parallel-step timestamp correction

Independent HA source review reproduced an aborted parallel wait whose older
start timestamp precedes a different branch's later false condition. Step times
are starts, so their order cannot prove the abort cause. Retained parallel paths
or any retained step error/timeout now veto inferred condition stops; the run
remains generically stopped with explicit unknown-reason coverage. A standalone
false action condition and authoritative `failed_conditions` remain recognizable.

The two new synthetic regressions first failed on `bc200e0`, then passed with
the correction. The targeted set passed 40 tests; the full suite passed 131 tests
in 38.42 s with the existing Starlette warning. Ruff lint/format and diff checks
passed. No HA capability, AI outbound behavior or later-phase product work
changed. Product mutations pause for semantic checks and external follow-up.

### A acceptance and B implementation

Critical review `70057443-b25f-46e4-852f-a9df98071c8b`, third round, accepted
`7034e22` with no critical/high/medium findings. The controller independently
passed 131 tests in 34.76 s and qualified its exact ARM64 image: schema-1 fixture
upgrade/restart, unchanged private options and legacy history, and restoration
of a copy of the original backup using the actual old 0.1.1 binary. Jev remains
unavailable without its configured API key; no score is claimed. The controller
then explicitly authorized B mutations in the existing repository.

B adds a local case service, meaningful overview priorities, redacted dossiers,
source-preserving known/expected/snoozed attention overlays, typed impact links,
run-bound configuration/step comparison and observed configuration differences.
History uses typed parameterized queries, stable keyset pages and UTC-day filters;
the automation index uses one bulk statistics query without AST/run-list payloads.
Static findings use explicit observed references, wait/continue flags and real
refused starts; dynamic references, rights and omitted source remain unknown.
No HA capability or AI outbound contract changes in B.

The final A lows are handled proportionately in B: synthetic trigger-event rows
cannot suppress a failed trace at the same proven start time; operator-looking
backup files are not deleted; identical rich evidence removes stale duplicate
metadata. Historical errors with unverified start times remain conservative and
visible in local dossiers/attention workflows. Independent B probes also fixed
backdated refused-start observation dates and inbound automation/entity graph
identity. Early browser feedback moved concrete investigations before counts,
added actionable step/error previews, grouped duplicate run-source cards, replaced
comparison JSON with readable observations and corrected native-select sizing.

Final B local verification: **160 tests passed in 32.01 s**, with the existing
Starlette warning. The 29 new B cases include the three actionable A lows, the
independent source-helper findings and conservative unknown-time refused starts.
Ruff lint/format, JavaScript syntax, pinned Prettier formatting and diff checks
pass. The synthetic 320 px select overflow is confirmed corrected by the
controller; full candidate UI/scale checks and external B review follow the
immutable commit. Product mutations pause at that gate; C remains closed.

### B review correction — lifecycle and bounded read model

External critical review `d3e801fb-824c-4bab-bbff-7a5ee7664818` rejected
`2f9899a7` with three medium and three low findings. The controller authorized
only corrective B work; ignored C preparation is preserved and paused.

Additive schema 5 binds annotations/notes to a retained case generation without
editing migrations 1–4. Prune/startup remove orphans; note history is capped at
50 and follows retention. A fresh case after pruning starts in review, while
source rows and separately configured exceptions are preserved. Finding refresh
moves to monitor startup/sync, gated by small static identities and transactional
run revision triggers; public GETs only read. Inventory exceptions are fetched
in bulk. Static selection is capped at 20 per automation/500 globally with
explicit omitted coverage and no false resolution of old budget-omitted facts.
Info-level advice ranks below availability, and availability-only overview shows
concrete dossiers. Backup collisions choose a unique private file without
overwriting operator bytes. Malformed retained summaries become explicit unknowns.

The previous exact `2f9899a7` candidate independently passed 160 tests and an
ARM64 schema 1→4 upgrade/restart/old-0.1.1-backup-restore qualification. Synthetic
Safari checked 11 rendered routes at five widths with 5,207 entities (55 checks,
no overflow/load errors). Those results are historical candidate evidence, not
acceptance of these corrections or a live 0.2.0 update. The corrective candidate
requires new internal verification and same-channel external follow-up before C.

Corrective B verification passed **182 tests in 31.74 s**, including 22 new
review regressions. Ruff lint/format (41 Python files), JavaScript syntax,
pinned Prettier and diff checks passed. Scaled real overview/cases GETs stay
within 20/5 queries and perform no writes, AST reads or all-run refresh; they
also complete with an independent WAL writer lock. These are local synthetic
checks. Freeze the coherent correction for independent/source, browser/container
and same-channel external review; C and final release/live gates remain closed.

### B second follow-up — bounded migration retry and page metadata

The second critical round in `vision020-b` closed the earlier corrective findings
but rejected `5a2e8bc` for repeated full snapshots on failed-migration restarts.
Two lows requested bounded coverage metadata and batch run lookup at page limit 100.
The controller authorized this consolidated B correction; C scratch is preserved
and paused again.

Backups now reuse a proven identical consistent same-version SQLite snapshot,
including WAL data, and enforce three retained source revisions, one temporary
comparison copy, a 1 GiB aggregate peak snapshot budget and a 16 MiB free-space
reserve before copying. Changed source history cannot reuse a stale backup to
satisfy the cap. Unknown crash temporaries fail closed without deletion; existing
operator bytes/permissions and the original snapshot remain intact. Fixed safe
startup categories report capacity/pending/invalid reasons through the application.
Case metadata contains aggregate coverage only, with per-automation details on
the requested detail route. One bulk run lookup covers a whole page, including
duplicates, malformed summaries and missing runs.

Prior `5a2e8bc` independent qualification passed 182 tests in 32.83 s and exact
ARM64 schema 1→5/restart/actual old-0.1.1-backup-restore checks. Eleven rendered
routes at 320/1280 px had no anomalies; a separate availability-only 320 px route
showed three concrete linked dossiers. Those are prior-candidate results and do
not imply acceptance of this new retry correction. No new schema, HA capability,
AI outbound expansion, version bump or release action occurs here.

Second corrective local verification passed **194 tests in 36.76 s** (12 new
retry/page regressions), Ruff lint/format for 42 Python files, Node syntax,
pinned Prettier and diff checks. Repeated failure/WAL-only source change/capacity/
operator-file/crash-temporary cases and fully run-linked pages at limit 100 pass.
Commit/freeze for independent and same-channel external checks; no B GO yet.

### B third follow-up — source reservation and live-inode exclusion

The third external round closed the prior retry-growth and page-load findings,
but rejected `2f90d89` because an otherwise valid backup could alias the live
main database inode. Independent coordinated testing also reproduced a second
writer committing new WAL data between backup and migration. Both must close
before B acceptance. The controller authorized this consolidated correction;
C scratch remains preserved and paused.

Startup now holds `BEGIN IMMEDIATE` before re-reading the source version and
through backup plus migration commit/rollback. A separate normal read-only
connection performs the backup API call without self-backup deadlock. Another
startup waits and then re-reads the committed version under the reservation.
Existing original/candidate aliases of live main/WAL/SHM inodes fail closed before
copy/DDL. Fixed pending-file guidance names the known private directory/pattern
and sidecars, and a separate oversized-source reason avoids misleading backup
cleanup instructions. Per-automation ephemeral coverage uses batch writes and
stale namespace cleanup; original structural/issue history is preserved. Run-page
lookup handles 100 distinct entities and numeric identifiers, including zero.

The exact prior `2f90d89` candidate independently passed 194 tests in 37.99 s,
container upgrade/restart/actual old-binary restore and ten browser checks. Those
are previous-candidate results; they did not close the new concurrent-writer and
live-inode defects. The new local run passed **213 tests in 33.12 s**, including
19 atomic-startup regressions (focused 1.12 s). External and independent acceptance
remain pending. No schema, HA allowlist, AI outbound or version metadata changes.

### Accepted B foundation and development preview packaging

The fourth external critical follow-up accepted exact
`9a3dd713e1ffa3234392991ad62adeb9fd98a98a` with zero critical/high/medium
findings. Independent verification passed 213 tests in 33.17 s, Ruff lint/format,
JavaScript syntax and diff checks. Its exact ARM64 image upgraded schema 1→5,
restarted with preserved settings/history/ledger and restored a copy of the
original backup using the actual old 0.1.1 binary. Independent source probes
also exercised two real startup processes and all six main/WAL/SHM backup-alias
cases. These checks accepted the B foundation, rather than the unfinished C scope.

The owner then requested a testable published preview through the restored
`ai-builder-dev` account. The controller authorized coordinated metadata/docs/
packaging tests only for **0.2.0-dev.1**, preserving the original repository URL,
slug and data volume. This version contains the accepted local investigation
foundation; targeted AI is still under construction in ignored disposable C
preparation. Existing AI-off defaults, saved options and compact outbound behavior
remain unchanged. Requested implementation configuration remains gpt-6.1-sol/ultra;
this statement records the request, not independent runtime attestation.

Preview packaging must pass local checks and a separate normal review. The
controller owns both-architecture builds, public PR/CI/readback and the live
Vision update with Supervisor's previous-version backup retained. Those gates
remain open until their actual results are recorded. No stable 0.2.0 tag or
completion claim is authorized by this intermediate package.

Packaging verification passed `.venv/bin/python -m pytest -q`: **213 tests in
35.32 s**, with the existing Starlette deprecation warning. Ruff lint/format
(28 Python files), `node --check vision/static/app.js` and `git diff --check`
passed. The package adds no monitoring, schema or provider runtime changes.
Freeze this coordinated metadata/documentation candidate for the controller's
normal review, builds, publication and live qualification.

The controller's pre-publication browser check found a stale hardcoded 0.1.1
wordmark badge. The narrow development-preview correction fills an HTML
placeholder from the same runtime `__version__` used by health/package metadata.
A real HTTP regression substitutes a probe runtime version and checks both the
visible badge and health response. The vacuous future-profile packaging guard is
removed; C will test its actual privacy options. In-progress C edits remain
outside this preview correction commit. Public publication is still pending.
Focused packaging/HTTP verification passed four tests in 0.24 s, with the
existing Starlette warning; Ruff lint/format and diff checks passed. The
controller will repeat full verification on the exact corrected preview tree.

## C — targeted AI investigations, prepared requests and scoped follow-ups

After B acceptance and isolated dev.1 packaging, the controller authorized C
implementation canonically above `4806463d33b020ecd48ccf0f127c4c034a534f38`.
The separate frozen dev.1 artifact remains the publication/live-preview candidate;
C keeps its version metadata until final D packaging. The requested implementation
configuration remains gpt-6.1-sol/ultra; effective runtime settings are not independently
attested by repository code. The existing ignored C preparation was integrated
without a second repository, worktree or custom controller.

C implements distinct task instructions and actual path/evidence selection for
audit, incident, automation logic, optimization, availability, template errors,
missing targets, refused starts, condition stops, wait timeouts and communication.
Specialized prerequisites are explicit; unsupported nonempty findings fail local
validation. Current missing-reference structure stays separate from selected
historical runs. Communication follows the failed action's physical targets and
healthy siblings, and typed template errors cannot qualify as communication errors.
Run/compare selection persists through the UI, preview binding and follow-up scope.

Additive schema 6 retains exact prepared request envelopes, local provenance,
conversation scope and attempt-to-usage links, preserving old analyses/ledger.
Compact remains the existing-installation default; local-only never reserves or
sends. Diagnostic needs configured richer opt-in and explicit per-preview consent.
Quoted/escaped JSON/Python secrets, Unicode/HTML escapes, addresses/paths and typed
identifier categories are sanitized before preview/outbound. Aliases are stable
within a conversation; fresh round references cannot reinterpret an old E1.
Redaction has explicit limits and never promises complete personal-data removal.

Every exact primary/backup body, task/schema version, bounded prior context and
budget policy is frozen and digest-bound. Sending atomically claims a preview once;
private process/configuration/consent-generation binding blocks stale tokens after
restart or off→on. Retry and failover recheck consent/revocation before every new
reservation/network attempt. Received refusal/incomplete/invalid-citation results
remain billed, while uncertain attempts preserve conservative reservations. Daily
explicit opt-in remains once-daily compact, never diagnostic. Scoped conversations
allow four rounds, eight messages/24 KiB context and one manually reviewed enum
expansion over the initial local snapshot; no HA/SQL/shell/free evidence tools.
Disposable unattempted previews are capped at 32; complete preview/local evidence
is at most 512 KiB. Older attempted/analysis history follows ordinary retention.

The UI provides dossier task preselection, exact request review/send/revoke,
evidence/alias mapping, support/counterevidence/unknowns and concrete manual checks
with validation. Legacy analyses keep rendering and are searchable beyond the
recent-50 Intelligence list. Safe allowlisted startup codes also distinguish the
existing bounded writer timeout and unavailable read-only snapshot source; backup
hashing was not speculatively optimized. Official provider contracts and bounds
are documented in ARCHITECTURE.md; no paid-model compatibility claim is made.

C local qualification passed **278 tests in 35.48 s**, including **64 new**
synthetic regressions above the 214-test corrected preview. The focused six-file
AI suite passed **82 tests in 1.11 s**. Ruff lint/format (37 files), Node syntax,
pinned Prettier 3.6.2 and diff checks passed. The only warning is the existing
Starlette/httpx deprecation. HA gateway/version/image metadata are unchanged.

Early independent mutable-source probes verified secret canaries, current-versus-
historical structure and selected-run binding, and caught a template/communication
classification overlap that now has two regressions. The controller's synthetic
browser preflight completed focused preview/send, mocked primary HTTP failure,
backup response, scoped validation follow-up and primary recovery. All three
adapter HTTP attempts matched their previously displayed body bytes. Those are
mock/mutable-source results, not final commit, real provider billing or live C
qualification. Freeze C for independent exact-commit checks and mandatory critical
external review; final D packaging/publication/live gates remain open.
The tracked-tree/reachable-history publication scanner also passed before this
commit; ignored preparation and private controller artifacts remain excluded.

### C consolidated correction — server jobs, admission and billing receipts

The critical three-part review of `5bce91b379f7fe4428cea8609cf6686a761a8f05`
identified eight accepted medium issues and five proportionate lower-severity
corrections. The controller authorized this consolidated correction. Current
primary-provider documentation confirmed native structured output without a beta
header; configuration/authentication failures remain fail-closed. Per-round
namespaces and conservative unknown billing remain deliberate safeguards.

Corrected unsupported tasks retain an explanatory local preview but cannot claim,
reserve or call a provider. Compact follow-ups include re-sanitized provider-origin
conclusions/uncertainty/unknowns and manual/validation text, while source free text
and questions remain excluded. Historical citation fields are stripped; both
native provider schemas enumerate only current references. Typed compact extra
sections retain meaningful relation/change/sibling summaries. Redacted dictionary
keys cannot silently overwrite another observation. In-flight withdrawal remains
revoked even when its received result/usage is retained.

Sending now returns HTTP 202 and a retained request ID, with a server-owned job,
900-second deadline, bounded provider timeouts and body-free status polling. A
client disconnect does not cancel the investigation. Admission reserves result
space and refuses new previews at 512 retained request rows or 64 MiB of retained
AI payloads; exact old requests and analyses are not evicted to satisfy the cap.
Expired unused previews are cleaned. Schema 7 backfills minimal billing receipts
and retains request/round/digest/attempt provenance with the 400-day usage ledger,
after ordinary heavy-body pruning. Usage/attempt/receipt insertion is atomic.
Recent analysis lists are thin, with full legacy mapping available on demand;
result search is preserved and no second list fetch occurs during binding.
Settings assignment validates atomically, including cross-field failures. Safe
HTTP status/reason/help and schema/reference/section errors exclude remote prose.
Context-window truncation is billed incomplete. Success/error envelope limits are
4 MiB/8 KiB; output cap is 65,536 with the 2,048 default and saved 8,192 untouched.

A separately demonstrated scheduler starvation defect is also corrected: newest
listed runs get an independent round-robin lane (11 count slots), historical error
backfill gets one, unused slots are shared and lane order alternates under the
existing 12-read/5-second budget. Synthetic 165×22-run qualification inspects all
165 newest successes within 15 cycles, with old backfill progressing and no full
trace refetch after compaction. Source/transport gaps still extend live coverage.
The controller independently measured frozen diagnostic previews on one host at
24.3–40.1 ms for a 5,200-entity synthetic inventory, with zero external calls;
this did not justify thread-offload complexity or a general performance guarantee.

D remains closed until corrected-C review acceptance. The owner-directed concise
visual presentation and the deferred 0.2.1 public-source research scope now have
one canonical definition in [VISION_SPEC.md](docs/VISION_SPEC.md). No research
executor, HA operation, paid request or final version/tag was added in this phase.

Corrective local qualification: **330 tests passed in 38.54 s**, including all
278 prior tests and 52 added regressions; the only warning is the existing
Starlette/httpx deprecation. Ruff lint and format (55 Python files), Node syntax,
pinned Prettier 3.6.2 and diff checks passed. Publication scanning passed for the staged tracked tree and all reachable
Git history, including the new synthetic tests. Freeze this candidate for independent schema-6
upgrade/receipt/lifecycle/browser checks and the same critical review stream.


### C3 follow-up — small accounting reads and explicit withdrawal

The same critical review accepted every prior medium/low correction on `24a4953`
but found two new medium issues. This authorized follow-up replaces repeated
retained-body byte scans in admission with additive schema-8 per-row accounting.
One migration backfill preserves all old body content; transactional insert,
body/id-update and delete triggers maintain UTF-8 sizes. Admission/headroom then
read small integer rows and status/attempt metadata. No history is deleted to
satisfy admission, and the UI exposes remaining slots/bytes without a deletion
feature. A synthetic real-HTTP preview regression seeds 480 completed requests
and analyses (about 60 MiB) and checks bounded admission with no retained-body
SELECT scan or provider call. Trigger, rollback, prune and restart behavior is
covered separately.

Form input now auto-revokes only an unused, non-in-flight preview. Running
withdrawal requires explicit Revoke. The client marks an attempted send in flight
before awaiting 202, and preserves that uncertainty after a transport error.
Automatic withdrawal errors stay visible and disable the old Send. Exactly locked
test-only jsdom tests execute the complete shipped HTML/script, covering both
branches, explicit withdrawal, failure and a pending POST/lost-response race.
Node 22 CI runs these tests; no Node dependency enters the container/runtime.

Proportionate lows are included: current-reference enums are added only after a
recursive independent schema copy; empty projected evidence fails locally before
charge; received withdrawn rounds remain labelled in conversation audit while
continuations are blocked; failed settings assignment also restores fields-set
metadata. The architecture documents the bounded read-only three-task compatibility
GET. D remains paused; no HA/provider call, public change or release is claimed.


C3 local qualification passed **339 Python tests in 44.46 s** and **5 complete-app
DOM tests**. Ruff lint/format (56 Python files), Node syntax, pinned Prettier 3.6.2
and diff checks passed. Only the existing Starlette/httpx warning remains. Freeze
the correction for independent schema-7→8, near-cap accounting, delayed native
browser and same-channel critical-review checks; D remains paused until C-GO.

The publication scanner passed for the complete staged tracked tree and all
reachable Git history, including the locked test dependencies and synthetic tests.

### C accepted; D action-oriented RC qualification

The controller accepted exact C3 `3e533aac7ecf16f55118a869b03f9cb9502e4f43`:
critical review sequence 6 GO with zero critical/high/medium, root 339 tests plus
five DOM tests, both architecture image/HTTP/restart checks and actual schema-1→8/
old-binary restore. Independent 144 focused tests/twelve AI chains, preserving
6/7→8 migrations, counter/failure/receipt probes and actual Safari request lifecycle
checks passed. Public/live dev.1 and one native retained-run comparison are now
recorded in VALIDATION.md; they do not qualify live native C.

D applies only visual/helper changes above that C3 base, preserving the actual
request/consent/budget/legacy/history contracts. It implements the single
VISION_SPEC presentation definition: three grouped overview priorities/one primary
CTA; problem→evidence→manual plan→validation; truthful visual step starts, gaps and
retained-structure language; three concise AI proposals with full/additional content
behind details; mobile wrapping and refresh focus preservation. RC metadata is
0.2.0-rc.1, with the same repository URL/slug/private volume and unchanged defaults.

The accepted rejected-send low uses one lightweight state read, restoring preview
only on confirmed unused/not-in-flight status. Early Safari preflight additionally
found a fast-completed initial-request race; the shared initial/poll terminal path
now opens the received analysis or shows safe failed/uncertain/withdrawn state.
DOM tests cover both races without new billing calls. The source-table upsert and
external trigger-loss lows remain deferred/unsupported, documented in ARCHITECTURE;
no store/migration change is added. Two earlier source-slice tests were adapted to
the new helpers and grouped availability contract; all their original legacy/
escaping/priority concerns remain covered, plus full real-DOM route tests.

After local checks, freeze D for independent eight-variant browser/navigation,
both architecture builds/upgrade/restart and new external D review. Only after
acceptance does the controller publish RC through PR/CI, verify exact public tree,
update the same installed Vision with previous-version backup, preserve original
history/settings and qualify native compact Anthropic/trace recency. Apply the
authorized output-option change while retaining the existing provider, model,
key, budgets and other settings. Final stable metadata/tag/release and
live final verification follow actual RC evidence. No public action or HA/provider
request is performed by the builder at this checkpoint.

D local verification: **339 Python tests passed in 38.35 s** with the existing
single Starlette/httpx warning; **19 complete-app DOM tests passed**, covering
initial and polled terminal outcomes plus safe send recovery. The 32 focused
workflow/insight/packaging tests also passed. Ruff lint/format (56 Python files),
Node syntax, pinned Prettier 3.6.2 and diff checks passed. The early mutable Safari
snapshots are preflight only; immutable D acceptance remains pending.

D publication scanning passed for the complete staged tracked tree and all
reachable Git history, including the new synthetic DOM fixtures.

### D2 consolidated corrective gate

D1 `b7764fdf` passed independent 339/19 tests and both images. Its initial 44
immutable Safari readings did not establish full D acceptance; the settled
long_names/320 counterexample and correction are recorded in the D3 section.
The first critical D review found one high/two mediums/five lows, and the AI helper
proved a mixed-error step-binding defect. The controller authorized one scoped
correction: keep plain request audits exact and accessible, auto-open only the
consumed send/watch session, preserve engaged/last-loaded content on background
failure, and degrade supporting reads without hiding known priorities or implying
zero issues. One task/focus selector supplies both the manual plan and its actual
matching path, with unknown paths explicit. All five lower-severity presentation
issues are included behind compact disclosures; server copy remains authoritative.

New full-app DOM tests pin completed-audit access, fast send/Back/no extra call,
running-audit completion, background rejection during focus/open details/selection,
partial supporting reads, availability disagreements, all mixed-error combinations,
wait-only evidence, unknown path and retained low-level guidance/links. Real ASGI
tests pin the two dashboard query strings and their bounded response shapes.
No store/schema/provider/default/retention expansion or RC version change occurs.
The independent frozen-D1 fanout/WAL probe is recorded as bounded evidence rather
than prompting speculative performance work. Freeze D2 after local checks for
same-channel review and relevant independent browser regression checks. Public/live
RC and final stable steps remain with the controller after actual GO.

D2 final local verification: **341 Python tests passed in 38.67 s**, with the
existing single Starlette/httpx warning. **27 complete-app DOM tests passed**;
the two new real ASGI dashboard-contract tests also passed independently. Ruff
lint and format (57 Python files), Node syntax, pinned Prettier 3.6.2 and diff
checks passed. The publication scanner passed over the staged tracked tree and
all reachable history, detecting no secrets/private paths. These are local
corrective-candidate checks; independent D2 review/browser acceptance and all
public/live/stable gates remain pending.

### D3 consolidated layout and low-severity follow-up gate

D2's same-channel review closed the original high/two mediums/five lows and mixed-
step defect; only the known 320 px overflow blocked acceptance. Native metrics
identified a 515 px affected-id flex child and 552 px page on both settled D1 and
D2. Correct the earlier premature long-name meter result rather than treating it
as proof. The labelled ignored D2+CSS preflight measured 303 px at 320 px and kept
the full opened related source link/focus; immutable D3 must still be requalified.

Apply only targeted non-clipping text wrapping/bounded affected-id width and four
small lows: consume actual watch=1 history entries only, preserve original entries
on lost-POST completed recovery, label primary totals by their read, distinguish
history-only failure from unknown priorities, and preserve unrelated notices during
refresh failures. Add the requested complete-app navigation/CSSOM/read-failure
contracts. Keep runtime Python, schema/storage/providers, defaults/retention and
0.2.0-rc.1 metadata unchanged. D2's independent 341/27 tests, nine extra DOM groups/
six mixed cases, both container/schema-8 checks and actual Safari audit/mock-byte/
Back checks remain bounded evidence. Future unsupported database upsert/trigger
lows remain deferred. Freeze D3 after proportional local checks for root's same-
channel critical review and settled exact-source browser qualification; no public,
live or stable release action belongs to this writer checkpoint.

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

### RC CI operational repair — yield to JSDOM history timers

The next Linux CI attempt passed 341 Python tests and both containers, but two
of 34 DOM tests exhausted their `setImmediate` iteration wait during browser Back.
With the exact CI Node **22.23.3**, ten unmodified targeted runs reproduced five
failures. Scratch instrumentation observed one 100-check budget end after 1.67 ms;
the same original predicate became true after yielding to the timer phase. JSDOM
queues history traversal via timers, so this was a test-scheduler limit, not a
changed application outcome.

Only that test helper now checks a monotone one-second deadline and yields via
`setTimeout(0)` until the original predicate succeeds. No fixed long sleep,
assertion removal, fixture reduction or skipped test is introduced. All **34 DOM
tests passed** on Node 22.23.3 (877 ms), followed by ten passing targeted repeats.
Syntax/format/lint/diff checks passed. All runtime/config/package bytes remain
identical to the prior accepted candidate; its green 341-test Python/container
evidence is carried, not claimed as a new Python rerun. Public Linux CI rerun
remains pending with the controller.

### Stable 0.2.0 metadata checkpoint — 2026-10-20

The controller accepted D3 and both test-only CI repairs, published exact RC tree
`4ffd54df7066c9ee2efb22cb86ecde80e1bcd709` through PR #3/main CI and qualified the
same live Supervisor install with backup, fresh read-only sync, bounded history/
settings preservation, 16/16 native historical-trace checks and one real compact
Anthropic structured-output investigation. VALIDATION records the exact scope,
including pending historical backfill, no exported live-image digest and no real
OpenAI/diagnostic claim. No private configuration values or raw IDs are published.

The authorized stable delta is version fields/tests and current documentation only;
functional D3, defaults, schema, providers and the deferred 0.2.1 scope remain
unchanged. At this checkpoint stable review/public CI, the final Vision update/
history check and then immutable tag/release are still pending controller work.

Stable metadata checkpoint local checks: **341 Python tests passed in 38.08 s**
with the existing single Starlette/httpx warning; exact Node 22.23.3 passed all
**34 DOM tests**. Ruff lint/format (57 files), JS syntax and diff checks passed.
All 18 Vision source/assets match the qualified RC except `__version__`; the five
linked packaging/test files contain version substitutions only. No feature,
provider/model, option/default, schema/store or 0.2.1-backlog change is included.

## Vision 0.2.1 — accepted phase A, started 2026-10-20

Direct owner mandate continues with one canonical writer, requested gpt-6.1-sol /
ultra and no custom workflow runtime. Start from clean `6fd7923a5d4e3ab38fbe5eaa6c03fad1514f7d95`,
matching published v0.2.0 tree `c662bd9a1e7e646b470ba2a52d7b1236c932efcc`
(public commit `d1a49bf55ceae40e0ceaeb755dd397b114d47254`). The accepted phase A
scope is in VISION_SPEC. The controller owns external review/public/live gates;
this writer does not push, call HA or use paid providers. Phase B research is
separate and must not become phase-A code. Existing provider options/consent,
ledger/history and immutable tags remain intact.

Implementation plan: a monitor-owned reliability service records new timestamped
device-state/cohort intervals, coverage sessions, durable local device policies
and bounded local check markers through an additive migration. A small current-
observation pointer per device avoids scanning all history at startup. No old entity
availability row is rewritten into a supposed historical device fact. Missing
pre-upgrade mapping/coverage is visible. Closed-role classification requires
actual enabled meaningful entity evidence; state `unknown`, unavailable, partial,
diagnostic-only, disabled and unmapped coverage are distinct. Effective device
class is a bounded enum from existing get_states attributes; entity_category and
disabled metadata use the existing registry read. No numeric state is retained.

Pure interval kernels union/clip [start,end) per device and coverage. Cached
24 h/7 d/30 d windows use at most 72 buckets; expected/new/persistent are disjoint,
and imported/gap baselines do not become invented new outages. Monitor refresh
owns bounded history work; HTTP views read small snapshots. Trend comparisons
require a stable covered cohort; deletion is not improvement. Persistent local
known/expected policies do not expire weekly. Local check validation requires
appropriate later covered observations and never claims causation. API/UI must
remain useful with no history/registry and preserve current evidence/navigation.

Build end to end, add metric/coverage/cohort and real UI regressions, test the
preserving upgrade and scale bounds, then freeze a coherent candidate (eligible
for 0.2.1-dev.1 metadata) for the controller's critical phase-A review. No phase-A
completion or new live/release acceptance is claimed at this start checkpoint.

### 0.2.1 phase A — implementation freeze checkpoint

Implemented the monitor-owned device cohort, additive schema 9 and local API/UI.
The first screen is a device-observation chart with visible axes and window controls,
then at most three grouped manual-check priorities and one primary link. Registered
devices are not asserted to be physical products. Diagnostic/update/disabled/unknown
and partial evidence stay distinct. Integration groups retain individual drilldown
links and do not assert a shared physical outage or network cause.

Device-hours use clipped per-device unions; coverage watermarks prevent restart
or storage-failure gaps being stretched into observed time. Equal-half burden
comparisons show their stable known subset and exclusions. First/last status is
separate. Persistent device attention does not expire weekly; actual same-cohort
partial→offline transitions can resurface known backlog. Health/run priorities
respect existing episode-bound, unexpired annotations. Ordinary modes/conditions
and old poll-refreshed logs remain in the source archive, outside the action queue.
Local performed-check markers require later continuously covered known evidence
from the same cohort, with unknown intermediate states/mapping changes blocking
recovery claims. Markers and source data do not establish causation.

Validation performed before this freeze: `.venv/bin/python -m pytest -q`:
**377 PASS**, one existing Starlette TestClient deprecation warning, 33.04 s.
The complete real-DOM suite on Node **22.23.3**: **42 PASS**, including all previous
34 tests and eight new dashboard/window/filter/check/policy/unknown/focus/duration cases.
`ruff check .`, `ruff format --check .`, JS syntax and `git diff --check` passed.
The 36 new Python cases cover interval arithmetic, corrupt/conflicting evidence,
known cohort comparisons, source-preserving attention/markers, rollback/restart,
additive upgrade, paging and actual bounded local API reads. A synthetic fixture
with 5,686 entities and 100,003 old availability rows has no history-table scan or
DB write on repeated reliability/overview GETs, ≤16 SQL statements and <160 KB
responses in that fixture. This is bounded local evidence, not a HA hardware SLA.

Initial full-suite failures were a schema-8 literal and a registry-projection spy
that did not include entity_category; both contracts were updated while retaining
all preservation assertions and strengthening category-change deduplication coverage.
The new DOM harness initially matched the static header too early; waiting for
actual rendered content exposed and helped correct the device-filter route binding.
No assertion or large fixture was removed to obtain the green results.

The package is **0.2.1-dev.1**, with repository URL/slug/options unchanged. Requested
implementation configuration remains gpt-6.1-sol/ultra; effective runtime identity
is not independently inspectable from repository code. Independent metrics/upgrade,
both architecture containers, native Safari, critical external review, public CI
and any new live acceptance remain controller gates. No new HA/provider/research
network request, publication or phase-B implementation was performed by this writer.

Deliberate limits: only newly timestamped device history; finite closed-role
classification; unknown unclassified/missing evidence; at most 6,000 retained
current identities and bounded interval/coverage caches. Capacity omission and
conflicts disable complete metric claims. A known partial→offline transition is
supported; frequency-worsening inference is not. Device power/sleep expectation
requires an explicit local declaration. Device/integration context is not yet a
new AI target or public-source research executor; that remains phase B after GO.


### 0.2.1 phase A — corrective freeze checkpoint

The initial `e676c3895c05` checkpoint remains historical: 377 Python / 42 DOM,
independent 73 metric/lifecycle/queue plus six API groups, populated schema-8
upgrade/all 22 old tables and host-local scale evidence. Its critical review was
NO_GO. The reviewer and native browser found real history-growth, loop-blocking,
durable-worsening, bounded-selection and presentation gaps; those are corrected
here before any phase-A publication. The note-redaction allegation was a broker-
redaction false finding: the original test did supply its token canary, and the
controller's 13 additional API/SQLite probes passed. Assertions were retained.

The correction uses lean history boundaries and separate bounded current evidence,
trigger-accounted append limits, independent complete-device window selection and
one off-loop coalescing cache worker. ARCHITECTURE.md defines the precise encoded
bounds, failure/recovery semantics and source-backed classification policy.
Current observations/attention are separate from the last coherent chart. Ordinary
note/power edits cannot rebaseline known worsening; an explicit guarded local
acknowledgment can. Removed pointers yield capacity to active registry devices
without losing their old history, policy or performed checks. No new HA/API read,
provider option, AI behavior, research executor or phase-B code is included.

The primary manual check now appears early, beside a compact chart on desktop and
before it on mobile. New versus persistent groups have distinct titles/timing and
exact affected-device navigation. Long comparison methodology remains available
behind a disclosure; empty/limited membership remains grey. Monitoring gaps,
capabilities, static limits, audit/history links and correct entity backlinks are
retained without dead secondary reads on the modern overview.

Local final verification: **401 Python PASS in 39.30 s** and **49 Node 22.23.3
DOM PASS**; Ruff lint/format, JS syntax, diff and publication scan passed. Detailed
commands, performance measurements and limits are recorded in VALIDATION.
During development the full suite caught two unchanged query-budget assertions:
the added capacity read exposed a duplicate overview health probe, which was
removed without relaxing those budgets. A benchmark fixture initially omitted its
required coverage reason; that ignored harness was repaired without product changes.
The historical **341 PASS / 36.84 s** checkpoint is restored exactly; it is not
replaced with today's larger count. Schema 9 is not yet public and was corrected
in place; frozen migrations 1–8 remain identical. External critical follow-up,
new independent/native/container acceptance and public/live GO remain pending
controller work at this corrective freeze. Phase B remains closed.


### 0.2.1 phase A — second corrective checkpoint

The critical follow-up of `fdee9380` closed both original HIGHs and all eight
original MEDIUMs, and identified five new MEDIUMs. This delta integrates the
prepared evidence-time/heatmap fix, fails cold cache start/capture/compile to null
rather than zero, preserves the real measurement-start metadata and distinguishes
that state in the shipped UI. A real initial RO-open failure is tested through
startup, ASGI and the whole DOM; successful retry and legitimate known zero are
kept distinct.

Global gaps no longer append a continuation per unchanged non-offline device:
coverage, not the apparent long interval, masks all unobserved time. Offline
resumption still needs a baseline. The 601-device/eight-gap regression adds only
eight offline rows and zero online continuation rows; exact known/device-hours
and unknown marker validation remain covered. Capacity status now includes use,
limits/headroom and cached earliest ordinary-retention eligibility, explicitly
not a resumption promise. New worsening cannot be proved while capture is blocked.

A frozen literal e676 experimental-schema-9 fixture proves early controlled
rejection with source bytes, permissions, old history and its v8 backup preserved.
No schema bump/rewrite is needed for an unpublished scratch format; current
migration 9 and frozen migrations 1–8 are unchanged. Role rules now recognize
source-backed classless sensors/binary sensors and closed functional domains,
while unknown primary evidence still blocks whole-device offline. Actual role/
state distribution remains conditional on controller live validation.

Small lows: action-first desktop focus/visual order, explicit RO-reader closure/
3 s busy timeout, episode defaults/finite validation and oldest-removed pointer
priority. Published-0.2.0 overview compatibility is retained behind an explicit
shape guard, preserving the 14 historical DOM/1,200-fixture checks without allowing
malformed modern data to become legacy zero counters. No fallback framework,
provider/privacy option, new HA operation or phase-B executor is introduced.

Local verification: **427 Python PASS in 41.26 s**, with the existing single
Starlette warning; all **56 Node 22.23.3 DOM tests PASS**. Ruff lint/format (62
Python files), JS syntax and diff checks passed. The new malformed-snapshot DOM
test initially looked only in the generic main error panel; the existing fixed
error reason is shown in the notice, so the oracle now verifies both actual
visible surfaces. No product behavior was changed for that test correction.
New external critical review and frozen native/container acceptance are pending.

### 0.2.1 phase A — startup recovery corrective checkpoint

The critical review of `c5064453` closed the prior five MEDIUMs and three LOWs;
one new MEDIUM concerned the preliminary read-only schema check blocking SQLite
crash recovery. That check now catches only SQLite errors and defers to the
authoritative writable check. Affirmative unsupported-schema errors still fail
closed, and permission tightening follows the writable schema validation. A real
hot DELETE-journal subprocess crash, read-only open/read failures and rejected
experimental-schema preservation cover the recovery boundary.

Published 0.2.0 has no device cohorts; measurement starts with this preview. All
earlier phase-A role revisions were unpublished. No schema/cohort migration is
added. Existing populated-cohort changes remain unknown for comparisons/check
validation and are disclosed; the burden label now says first → second half of
the selected window. Capacity DOM guards distinguish the conditional blocked
warning from ordinary details; the RO-reader spy ignores unrelated connections.

The controller qualified exact `c5064453`: 427 Python tests, 56 DOM tests,
populated schema-8 migration/restart/old-store snapshot restore, experimental-9
preservation, bounded scale/worker gates, both architectures' real HTTP/restart
and network-isolated RO-WAL capture, plus native 320/390/1280 px workflows.
These are completed, version-bound checks; acceptance of this startup delta,
critical follow-up, public/live gates and phase B remain pending. Local commands
and results for the new freeze are recorded in VALIDATION.

### 0.2.1 phase B — accepted implementation start

Phase A received critical GO on exact `83355b6`; the controller qualified the
actual images, journal recovery/history, native workflows and independent gates.
The explicit next mandate is a tested 0.2.1-dev.2 public-source investigation,
within the accepted scope in VISION_SPEC. The existing single writer owns tracked
implementation; the controller owns independent review/public/live acceptance.

Reuse the existing frozen preview, provider send/CAS/reservation/receipt chain.
Add one small separate public research service: plan → 202 job → new frozen
preview over the same local evidence. Keep quota/backoff in existing Store meta,
temporary plans/cache/jobs bounded and process-local, and no new framework.
Typed device availability capture and v3 source/manual-plan validation extend
only their explicit paths; old v2 request bytes/digests are never recomputed.
First implement closed catalog/transport/quota/hash contracts and meaningful
synthetic HTTP/API tests, then source-bound providers/device scope and complete
UI/DOM workflows. Preserve all A metrics, history, options and privacy ceilings.
Coordinate dev.2 package metadata only with the coherent working candidate.
No builder HA/provider/publication calls; freeze for mandatory critical review.

### 0.2.1 phase B — coherent implementation checkpoint

The controller accepted A3 `83355b6`: critical sequence 4 GO, then PR #5,
all nine push/PR/main CI checks, exact anonymous tree readback and the existing
Supervisor installation's dev.1 update with backup enabled. Native read-only
connection/cache, first device-measurement boundary, role examples and bounded
history/settings preservation passed. This is completed A evidence, not B
acceptance; private household samples/configuration remain outside the repository.

B now implements plan → bounded 202 public job → new exact provider preview over
the original local snapshot, with the closed catalog/transport, persistent atomic
quota/backoff and finalized source hashes described in ARCHITECTURE. Exact-device
availability keeps own healthy counterevidence and unknown coverage. Device
observed duration intersects real coverage rather than a gap-spanning interval.
Source-bound v3 manual plans and round references are validated locally; analyses
retain sources after request expiry. Original v2 native bodies have accepted-base
golden hash guards and stored request audit bytes are not recomputed.

The complete shipped DOM covers query-plan review before fetching, resume without
a second start, separate fresh diagnostic attachment consent, failed/withdrawn
research, new preview before paid send, current source/manual/validation cards and
one central latest solution with compact older history. Existing paid lifecycle,
withdrawal/Back/audit/legacy and reliability DOM checks stay enabled. Small accepted
polish changes only display names/count wording/integration labels; exact targets
and queue/metric semantics stay preserved. Actual own SQLite sidecars are tightened
after authoritative schema validation, with unsupported-schema preservation tests
unchanged. There is no new migration, option/default or HA read operation.

Local checks: 487 Python PASS in 39.05 s, one existing Starlette/httpx warning;
64 Node 22.23.3 DOM PASS. The first full run found a new target-type JSON extraction
against a retained non-JSON audit fixture; a guarded extraction preserves its
legacy entity meaning without altering stored bytes. The final full run passes.
New native adapter mocks prove exact primary/backup bytes, technical uncertain
billing, valid v3/manual retention, billed invalid-reference rejection and frozen
follow-up reuse. No builder HA, real provider or app-public-research call occurred.
Coordinated package version is 0.2.1-dev.2. Mandatory independent critical review,
container/public/live B qualification and stable release remain controller gates.

The implementation retains the requested gpt-6.1-sol / ultra single-writer
configuration. Effective model/effort is not independently observable through
this workspace; no separate runtime proof is claimed.


### 0.2.1 phase B — targeted review corrections

The controller independently qualified exact `5bb9947`: full Python/Node checks,
both actual architecture images/HTTP/restart/RO-WAL/hot-journal recovery, populated
v8 (22 old tables) and dev.1 schema9 (28 tables) preservation including device data,
measurement start, options/backups and sidecar permissions. Source/private-reference
scans passed. Independent device/version/gap, native provider/quota/privacy,
v2 byte/audit-load and source-hash/retention gates passed except one retained-device
UI label. Critical review reported one further MEDIUM: legitimate public terms were
over-aliased. These are completed version-bound checks, not B acceptance.

The correction uses a research-only known-private-reference projector: no discovery
from public prose, with closed public technical tokens preserved even if seeded
by prior diagnostic aliases. Private/v2 alias defaults stay unchanged. Retained GET
now displays its exact device scope; a real POST/GET fixture feeds the complete
shipped DOM and verifies device/entity/system scopes, digest and actual native
bodies without sending. Public-fidelity tests cover all four catalog integrations,
both profiles, canaries, native previews, retained sources and scoped follow-ups.

Small accepted lows: full HTML void tags (genuine excessive nesting remains an
explicit gap); 24-hour backoff with visible host/expiry; one unclaimed plan per
base; 32 balanced own members preserving all bounded history/healthy peers in both
final native bundles; fixed 400 reconstruction/hash refusals; one evidence parse
per findings render; accurate final comment-retention counts and documented global
AI/local-only capability controls. No new option/migration, permission/DNS/reset
framework, sync policy, HA operation or version change. The candidate remains dev.2.
New independent same-session critical acceptance/public/live gates remain pending.

Corrective local checks: 501 Python PASS / 38.88 s with the existing warning,
65 Node 22.23.3 DOM PASS / 2.27 s, Ruff lint/format (71 files), JS syntax and diff
checks passed. Requested implementation runtime remains gpt-6.1-sol / ultra;
effective runtime identity is not independently observable. Freeze for the same
critical review channel and independent acceptance; no builder external operation.

### 0.2.1 phase B — bounded pre-publication guards

Critical sequence 2 accepted exact `981fad1` with zero critical/high/medium; the
independent source-fidelity/native/retention/v2/device projection checks passed.
The controller then authorized only four nonblocking lows and the demonstrated
CI-fixture repair before publication. No phase/feature/version expansion follows.

The ASGI DOM fixture now explicitly imports its own checkout root and reports
missing Python setup separately, with a 30-second deadline. Dependency-only
isolated execution (without editable .pth/CWD import support) emits all three
actual fixtures from the bound source. Public-only alias boundaries remove known
IDs before terminal punctuation, while longer entity/domain tokens and public
technical terms remain intact; private/v2 aliases are unchanged. Unclaimed plans
are replaced when authenticated version/time or active backoff changes, retaining
one identifier map per base. Valid numeric old unpublished backoffs normalize
once to 24 hours inside the claim transaction; refusal follows commit, preserving
request/search and billing ledgers. Malformed quota still fails closed. A final
12 KiB snapshot guard and full five-source/two-backoff test pin the budget in both
native previews. Clean-CI/independent final delta/public/live acceptance remains
with the controller; metadata stays dev.2 and no external builder call occurs.

Local final-delta checks: 519 Python PASS / 39.68 s with the existing warning,
65 Node 22.23.3 DOM PASS / 2.59 s, Ruff72/format/JS/diff passed. Tests remain
fully enabled. Freeze one bounded delta for the same critical channel; builder
performs no HA/provider/publication operation and metadata remains dev.2.

### 0.2.1 — accepted B and stable metadata-only packaging

The controller accepted exact `f146ec01ac2f9145bcce0ca501f737599527a4bc` after
critical sequence 3 GO (zero critical/high/medium), clean 519-Python/65-DOM CI,
both real architecture images, populated v8/schema9 preservation and independent
source/privacy/native-body/quota/legacy-v2/device gates. Public PR #6 merged as
`adb9f4ea52fe708a4ab0ee3fbf46d6232e26759d`; all nine public CI checks and anonymous
97-file source readback passed. The existing Supervisor updated to dev.2 with
backup enabled; connected/read-only/source/WAL checks, bounded retained-data and
all-settings comparisons, and the unchanged device measurement start passed.

One real generic public-source job and one authorized compact Anthropic v3
investigation completed. The controller checked exact sent/retained body/digest,
source-bound manual steps, counterevidence, unknowns and validation. No proposed HA
action was executed. Detailed scope and limits belong in VALIDATION; no household
content, options or exports are published. OpenAI remains mock-qualified, Reddit
authentication is unavailable and invoice costs remain unverified.

The authorized final delta coordinates six version fields and existing current
documentation at 0.2.1. Functional source, options/defaults, schema/migrations,
permissions and billing stay bound to f146ec01. The three nonblocking critical-
review lows are accepted within this scope, not new implementation work. Requested
writer configuration stays gpt-6.1-sol / ultra with no independent effective-
runtime proof. At the 2026-10-20 metadata-freeze checkpoint, stable review/public
CI/readback/final live update/tag remain controller-owned gates. Earlier phase
checkpoints and their original test counts remain unchanged.

Local metadata-freeze checks passed: 519 Python tests / 39.86 s (existing warning),
65 Node 22.23.3 DOM tests / 2.85 s, lint/format/JS/diff/publication scans and exact
source invariants. Six metadata replacements and six documentation files are the
entire delta; all other tracked bytes match f146ec01. Freeze for controller review.

## Vision 0.3.0 — authorized execution, 2026-10-22

Owner instruction “Voer plan uit” authorizes the accepted complete 0.3.0 plan.
Canonical input is clean 1dbc2f71d6643cf8710569088588cf362f60486c. The same sole
tracked writer implements directly in this repository; the controller handles
immutable external reviews, independent QA, publication/live HA and real human
usability availability. No new custom workflow runtime/profile/controller.

Stage A builds the local Today/problem/intake journey immediately after recording
scope in VISION_SPEC. Additive local importance/preferences/episode-feedback storage
preserves metric/known/expected baselines and old history/billing. NL/EN, friendly
local names/rooms, truthful grouping/counterevidence, at most three priorities and
manual follow-through must work end-to-end without AI. Version 0.3.0-dev.1 only when
installable. Preserve all 519 Python/65 DOM baseline checks and add meaningful
API/DOM/migration/privacy/noise/coverage regressions. Freeze a coherent candidate
for mandatory critical review; no Stage B product work before explicit A GO.

Stage B then adds durable one-click orchestration and opt-in v4 typed localized
results over existing research/provider hooks. Old native bodies, consent, usage
and receipts remain immutable. Five human participants are an owner/controller
acceptance gate, not five agent personas. Requested writer remains gpt-6.1-sol /
ultra; effective runtime identity is not independently observable here.

### 0.3.0 Stage A — local dev.1 freeze checkpoint, 2026-10-22

The local Today → problem → manual-check/report journey now works without AI.
Five primary routes, bilingual daily labels, local names/rooms, optional cancellable
intake, independent importance/known/usual choices and later observational feedback
are implemented. Covered grouping, exact typed source scope, critical-case admission,
healthy contrary evidence and concrete declared dependency links retain uncertainty.
Healthy/unassessed devices open their exact existing evidence route, not a fabricated
problem; capacity or sync-pending states cannot imply a quiet day. New local feedback
does not resolve source facts or rewrite the user's earlier device-policy baseline.

Schema 10 adds four tables: home_preferences, home_device_preferences,
home_problems and home_feedback. New admission refuses excess rows without evicting
existing history. Source comparison confirms migrations 1–9 and the entire Store
class, reliability kernel, AI/research/config code, locked dependencies and CI bytes
equal the accepted 0.2.1 input. Only the exact optional area-list read is added to
the closed HA gateway; local room metadata is outside external evidence projection.
Six version fields coordinate 0.3.0-dev.1. Existing expert routes and historical
analysis prose remain intact. Stage B one-click orchestration/v4 is not implemented.

Builder-local final checks: 534 Python PASS / 44.95 s (the existing Starlette warning),
74 Node 22.23.3 DOM PASS / 3.26 s, Ruff check/format (62 Python files), both JavaScript
syntax checks, diff whitespace and tracked-tree/all-reachable-history publication
scans passed. The earlier local 534/73 checkpoint
predated the added concrete-impact DOM regression; it remains a local checkpoint,
not independent acceptance. Source-bound API/DOM tests cover cancelled/rerun intake,
explicit-only edits, both independent booleans, durable worsening/explicit ack,
subjective and retrospective feedback, no false recovery, admitted links, capacity,
pending/unknown views, area bounds/failure, exact source episodes, read-only GETs,
additive migration/restart and preserved compact external evidence.

Ignored local logs/proofs are under work/030-stagea-validation; they contain synthetic
fixtures only. The controller's early native prototype review is not a frozen-source
acceptance result. Independent critical review, populated-table/container/performance
qualification, final native desktop/mobile checks and any public/live update remain
open. The five-real-human usability criterion also remains open; agent checks do not
count as users. Freeze this local A candidate for controller review; do not start
Stage B until explicit A GO. No builder HA/provider/publication operation occurred.

### 0.3.0 Stage A — bounded corrective freeze, 2026-10-22

Initial critical review `846d4361-b968-43de-8a32-df21573f69e4` returned NO_GO on
`1395854bc22bad77dbe803cc68671094dce1bcaa`. The controller independently confirmed
534 Python/74 DOM, all 28 released tables/options/backups across upgrade/restart,
both architecture HTTP/restart/hot-journal/RO-WAL checks, and the full synthetic
6,000-device/250,000-interval workload. That source-bound technical evidence did
not qualify the pending/feedback/storage/locale user-journey findings. Its near-cap
probe measured 40.96 MB of needless snapshot reads, but did not demonstrate an
event-loop stall over 200 ms on that host; no new thread framework was warranted.

The bounded correction keeps coherent priorities/as_of during pending work and
shows retained unknown-state evidence during disconnect. Empty stale snapshots
cannot claim quiet after a relevant event; unchanged numeric/available states do
not invalidate the daily view. Sync flags clear on failure. Feedback works on HTTP
without randomUUID, retains its idempotency key, and replays the original check
kind before evaluating a new episode. Subjective reports survive missing devices
and check-capacity refusal with explicit unavailable-marker reasons; old reports
and their checks are disclosed separately from the current episode.

Group IDs now bind stable device/cohort membership and integration while episodes
stay in the snapshot. Only expired retired presentation rows without feedback may
be reclaimed, at most 1,000 per minute after configured retention; retirement gets
its own current timestamp. Owner reports and every earlier history/billing table
remain outside cleanup. Refresh reads small metadata and caches body hashes,
performs conditional batched writes and coalesces relevant event work every two
seconds. A direct refresh remains available after sync and for synthetic seeding.
No Store/migration, HA allowlist, options, metric or AI/research code changes.

Explicit null now restores legacy inheritance while absence preserves a previous
boolean. All direct primary routes resolve server locale; Settings/History shell
labels follow NL/EN without changing typed values or old analysis prose. Device
lists have no dead intake controls, healthy links accurately open device evidence,
group cards avoid repeated caveats, and a bounded integration strip is visible by
the chart. Parent-area inheritance is restricted to the officially verified main-
parent hop with own-area precedence and dangling/cycle/via-device negatives.

Corrective regressions cover all these paths: 25 focused Python and 15 whole-app
DOM cases. The released 519/65 baseline stays active. Local near-cap Home-only
measurement (6,000 devices, 10,000 × 4,095-byte snapshots) returned zero snapshot
body bytes; one cold batched refresh took 191 ms, warm refreshes 71–84 ms. A 2.6 s
coalescer probe produced one refresh, 157 retained-attention samples and an 84 ms
maximum heartbeat gap. These are bounded host measurements, not a hardware SLA;
the controller repeats full workload/native layout checks on the next immutable
source. Initial prototype and initial freeze proofs are preserved separately.

Final corrective checks: 544 Python PASS / 46.83 s (existing warning), 80 Node
22.23.3 DOM PASS / 4.06 s, Ruff lint/format (62 files), both JS syntax and diff
checks passed. The additional cold-write batching change was followed by the full
Python suite; DOM/source boundaries remained unchanged. Stage A source invariants
keep 21 core/packaging files exactly equal to the first freeze.
The tracked-tree/all-reachable-history publication scan also passed.

The candidate remains 0.3.0-dev.1 / schema 10 / four new local tables. Stage B is
still not implemented. Same-session critical follow-up, independent corrective
acceptance and the real-human usability/public/live gates remain open. Builder
performed no HA/provider/publication operation; requested model configuration is
still gpt-6.1-sol / ultra without independent effective-runtime proof.

Immediately before handoff, the controller requested one final existing-scope
guard: a first unknown-coverage Today now gives a short manual connection/freshness
check and opens the existing technical coverage view, without inventing a device
problem. A real initial API response drives its DOM regression. Final DOM is
81 PASS / 3.02 s; the unchanged Python source retains the 544-PASS result above.
The main correction commit is retained, followed by this small UI/test/doc commit;
no history rewrite or additional feature scope. Freeze both as one review delta.

### 0.3.0 Stage A — native-observed UI-only follow-up

Native and independent API/DOM checks on 404c86b found two remaining presentation
defects. The visible integration caption omitted unassessed/partial counts and
could present a cached zero-unavailable fraction as current during disconnection.
Intake cancel preserved data correctly but retained the old page scroll, placing
the next daily action above the visible viewport. The authorized follow-up changes
only two JS files, their DOM regressions and documentation.

Integration captions now identify the retained snapshot/time and list unavailable,
partial and unassessed counts separately. Missing/failed/pending/unreliable cache
explicitly leaves current availability unknown; no complete-looking offline
fraction is shown. Foreground route navigation focuses and scrolls the main region
to its start, while successful/engaged background refresh keeps scroll and focus.
All 61 tracked Python files and 71 selected source/packaging contracts are byte-
exact 404c86b, carrying its 544-Python result. Full DOM: 83 PASS / 3.49 s; lint/
format/syntax/diff passed. Native layout and critical follow-up remain controller
gates, as does the separately measured full-capacity admission-path investigation.
No kernel, schema, allowlist, provider, option or version change is included.

### 0.3.0 Stage A — sequence-2 bounded documentation/robustness correction

Critical sequence 2 on a8cb4f2 returned NO_GO for omitted latency-failure disclosure
(zero critical/high; one documentary medium and four robustness lows). Record the
separate **OPEN FAIL: 200 ms full-capacity gate**. With 6,000 devices, 250,000 device
history rows and 10,000 × 4 KiB snapshots, the full probe measured 493.4 ms heartbeat.
Isolated 404c86b measured 281.8 ms heartbeat / 274.9 ms observe; identical-checkpoint
1395854b measured 271.9 / 264.3 ms. Closing 6,000 intervals took 83.9 ms, NULLing
pointers 12.4 ms, outer commit 174.5 ms. The released reliability/Store path is
unchanged: a pre-existing one-shot capacity-transition spike, without old-row loss
or false recovery. Device-history capture stops explicitly with gap/limited status.
The one-off 16 MiB cache experiment still measured 267.8 ms and FAILED. WAL cause
is unproven; no input, threshold, pragma, durability or concurrency architecture
is altered for a PASS. This remains separately scoped OPEN FAIL, not “all qualified.”

The small code/test correction confines exact-copy localization to app-owned shell
nodes, keeping entity options, notes and original AI prose unchanged. Initial body
or already-chosen focus remains untouched; a default initial visual scroll still
keeps the daily action visible without moving initial keyboard focus. Later route
changes focus main; background keeps scroll/drafts. Locale GET failure falls back
cosmetically and retries, including primary/intake/expert routes. A native exact-
message regression pins the existing check-capacity contract; unexpected check
errors are not converted into capacity-success reports. No kernel or request bytes
change. Stage B remains closed pending explicit A GO and the same review stream.

Root source-bound a8cb4f2 native scenes (quiet/outage/group/insufficient 320×700,
outage 390/1280×700) had visible actions/no overflow; intake cancel retained API
bytes, and both architecture HTTP/start/restart passed. These do not substitute
for human participants or erase the explicit failed full-capacity timing gate.

Final bounded-candidate checks: 545 Python PASS / 51.32 s (existing warning),
86 Node 22.23.3 DOM PASS / 4.11 s, Ruff lint/format (62 files), both JS syntax
and diff checks passed. Thirty runtime/packaging contracts, including every Python
runtime module, are byte-exact a8cb4f2. Changes are labels/focus/fallback, tests and
explicit failure documentation; no capacity timing repair or Stage B is claimed.
Publication hygiene (tracked tree and reachable history) passed; the explicit
full-capacity latency gate remains OPEN FAIL regardless of these passing checks.

### 0.3.0 Stage A — sequence-3 preference-preservation correction

Critical sequence 3 found a same-window stale preference cache: a saved language
could be reset by the next intake save. All four successful preference-save paths
now cache the validated server response. Intake sends locale only after an explicit
change, preserving server choices through a failed read or another-window edit;
failed saves keep the prior cache and dirty draft. An unexpected check ValueError
now becomes a fixed internal error with a generic 500, preserving rollback and
keeping raw exception text private. The known capacity fallback remains unchanged.
The controller's A4 545-Python/86-DOM, both-architecture HTTP/restart and native
focus/layout checks passed; this new delta still requires same-session review.
The separate 200 ms full-capacity gate remains OPEN FAIL. Stage B stays closed.

Final local checks: 545 Python PASS / 52.34 s (existing warning), 90 Node 22 DOM
PASS / 3.90 s, Ruff lint/format (62 files), JS syntax, diff and publication scan.
The only Python runtime delta is the fixed internal-error boundary in Home.feedback;
Store, reliability, schema, HA, AI/research, settings and packaging stay exact A4.
