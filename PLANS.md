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

## Milestone 4 — Release (local candidate verified; browser publication in progress)

- [x] Complete dashboard, desktop/mobile browser verification, docs/security/privacy.
- [x] Test suite, both architecture builds/start/persistence, four review streams GO and full-history secret scan.
- [ ] Live HA install verification (needs test-environment access).
- [ ] Public GitHub repo, CI green, remote readback, v0.1.0 tag/release.

## External access

Initial `gh auth status`: stored account token invalid. Authentication requested;
development continues. Docker CLI available but daemon initially unavailable;
local Colima availability will be checked before container validation.

## Verification progress

76 pytest tests passed, including real local WebSocket/REST simulation and reconnect,
private database concurrency/persistence, provider HTTP contracts, failover/consent,
billing reservations and upstream trace golden cases. Ruff and JS syntax passed.
ARM64 and emulated AMD64 container HTTP/start/restart persistence passed for final
images; byte-identical source binding is in docs/BUILD_EVIDENCE.json. 76 tests also
passed inside the Linux image with development-only test dependencies. Browser exception save and
mobile width verified with synthetic data. See docs/VALIDATION.md for precise limits.
No live HA installation, billable provider call or GitHub publication claimed.

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
browser interface for repository creation and source upload. The public empty
repository `Patrick1610/vision-homeassistant` has been created in the owner's
authenticated session; the separate CLI device flow was cancelled. Upload only
the audited tracked tree, including hidden metadata and nested source folders,
then independently read back and compare every public file, await CI, install
the concrete candidate through HA OS/Supervisor, verify Ingress + capabilities +
restart history, and only then publish the v0.1.0 tag/release. Do not infer live
acceptance from local source-review GO. No real API keys have been supplied to
Vision, so provider live/billing behavior remains unverified. A browser-created
Git commit is a separate public commit from the local development history;
record both and verify tree equality instead of claiming identical commit IDs.
