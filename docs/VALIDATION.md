# Validation and release status — 2026-10-19

Status: **public v0.1.0 release candidate source; final tag/release pending**.
Do not interpret component tests as live Home Assistant installation approval.

| Evidence | Result |
| --- | --- |
| Python component and local WS/REST integration suite (Mac and Linux container) | 76 passed; includes authentication, read policy, state inventory, Repairs/logs, trigger/trace deduplication, reconnect, fragmented/invalid/oversized HTTP responses and bounded container readiness. |
| Ruff lint / format | Passed. |
| JavaScript syntax | `node --check vision/static/app.js` passed. |
| Dependencies | Exact transitive versions and SHA256 hashes; clean ARM64 and AMD64 image installs succeeded. `pip check` passed. |
| Container startup and restart history | HTTP health before and after restart, exceptions loaded by the restarted app, and independent SQLite volume persistence passed on ARM64 and emulated AMD64 candidate images. Final source binding recorded in BUILD_EVIDENCE.json. |
| Browser | Synthetic inventory/detail rendering and saving an exception verified through real browser interaction. 390 px and 1280 px viewports: document widths match, no page overflow or browser console errors. |
| Upstream trace semantics | Six normalized cases from HA 2026.10.2 official fixtures/assertions, plus mode-block tests. Source downloaded and independently compared byte-for-byte with Git objects at `8d7fd8b68677c2585be36ec86043308f403875b8`. |
| External review | The four milestone streams and subsequent stream-reader/restart correction ended GO with no open critical/high/medium findings. See REVIEWS.md. Jev unavailable because its API key is not configured; no score claimed. |
| Live HA OS / Supervisor installation | Not performed yet. Existing user browser sessions are not proof of an app installation. |
| Live billable Anthropic/OpenAI request | Not performed: no provider credentials supplied. Both adapters tested through deterministic HTTP simulations. |
| GitHub source publication | All 50 tracked files uploaded through GitHub's web interface. Anonymous readback confirms identical content and Git trees. No CLI authentication was used for publication. |
| GitHub CI | [Run 39294357509](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39294357509) passed in 1m 57s: tests/lint/format/JS/publication scan plus build/start/restart-persistence on amd64 and arm64. First run exposed a test-only absolute-path exclusion bug; a repository-relative exclusion fixes it. |
| Final tag/release | Not created; live Supervisor/Ingress installation remains a release gate. |

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

## Remaining release gate

The source, builds, tests, reviews and local Git-history secret scan are complete.
The audited source is public at [Patrick1610/vision-homeassistant](https://github.com/Patrick1610/vision-homeassistant).
Initial public commit `18eef515b85d1f195664aa46bfadf3be0c689b00` exactly matched
local `889ac87505965d1cdc0518ab97a766189f205805` (50 files; tree
`46a30cd223178f04c1b0c6800560216585300d49`). The test-only CI correction is public
at `dc8603ce9eab412cdefd0530622f1d80cd590d1f`, matching local `fd201aa` at tree
`bb71a410b82b4129081b51c95ec7de9451ec2149`. Its actual workflow is
[CI run 39294357509](https://github.com/Patrick1610/vision-homeassistant/actions/runs/39294357509).
CI reported non-failing runner notices for Node 20 actions forced to Node 24 and
the ubuntu-latest image migration. Install the
concrete candidate on HA OS/Supervisor and verify Ingress, capabilities and restart
history. Only then create the final v0.1.0 tag/release and update this status.
