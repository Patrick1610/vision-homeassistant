# Vision v0.1.0 execution record

Owner authorized all four milestones, dependency installation, testing, local Git,
public GitHub publication and v0.1.0 release. Read-only HA is absolute.
Canonical root inspected: empty except existing unborn `main` Git repository;
no remotes, history or user changes. Single writer, direct owner mandate.
The agent-workflow skill was consulted; its custom-agent runtime is not activated
because this execution uses the owner's direct development mandate, not delegated
custom roles. Permanent milestone state is recorded here.

## Milestone 1 — Foundation (implemented and locally verified)

- [x] Root / instruction / Git inspection; preserve existing `.git`.
- [x] AGENTS, permanent specification, architecture and execution record.
- [x] App packaging, persistent storage, peer and user-authorized Ingress, usable interface.
- [x] Foundation tests and external review GO.

## Milestone 2 — Monitoring (implemented and locally verified)

- [x] Read-only HA transport, reconnect, inventories, traces, Repairs/logs.
- [x] Persistent incidents, exceptions, availability and execution statistics.
- [x] Integration simulations, coverage limitations, final log-counter corrections and review GO.

## Milestone 3 — Intelligence (implemented; externally reviewed GO)

- [x] Anthropic/OpenAI, common validated evidence schema, opt-in/minimization.
- [x] Retry/failover/recovery, reservations, budgets and usage history.
- [x] Manual/daily/incident/automation analyses; tests and external review GO.

## Milestone 4 — Release (public source verified; live installation pending)

- [x] Complete dashboard, desktop/mobile browser verification, docs/security/privacy.
- [x] Test suite, both architecture builds/start/persistence, four review streams GO and full-history secret scan.
- [ ] Live HA install verification (needs test-environment access).
- [x] Public GitHub repository and anonymous source readback.
- [x] GitHub CI green (run `39294357509`, public candidate `dc8603c`).
- [ ] v0.1.0 tag/release after live installation verification.

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
No live HA installation or billable provider call claimed. Public source is
verified independently below; a final tag/release is not yet created.

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
Full live Supervisor/Ingress validation remains pending; partial observations
and the current access gate are recorded below.

## Live Supervisor access gate

The owner's existing installation now reports Vision 0.1.0 in Supervisor and
is running. Its Ingress route serves the expected locked access page. AI and
daily audits were observed disabled. No options were saved, users authorized,
app restarted or HA devices/configurations changed by this validation attempt.

The current HA user's access has not been authorized in `allowed_user_ids`.
The locked state was rechecked in two successive goal continuations. The browser
confirmation question remains unanswered: add only the current HA user, save
Vision's options and restart only Vision for monitoring/history verification.
Do not treat the general goal continuation as that security confirmation, repeat
the question, or work around the gate through private APIs or database access.

Once authorization arrives, re-read the active session identity, preserve all
other options with AI off, and verify the installed source candidate, connection,
capability coverage, inventories, retained trace outcomes and restart history.
A displayed version alone does not bind the installed image to the current Git
candidate. Only after those checks may the final v0.1.0 tag/release be published.
Latest public candidate `82ae1714a0ec57ec1645f81e270cd02437b08579` passed CI run
`39298072551` in 2m 17s. This local checkpoint changes documentation only.
