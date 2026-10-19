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
without its API key; no score is claimed. Public CI, publication and live update
verification are pending.
