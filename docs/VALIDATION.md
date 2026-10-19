# Validation and release status — 2026-10-19

**0.1.1 wordmark update:** prepared and locally verified; publication and live
update verification pending. The following v0.1.0 evidence remains historical.

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

## Wordmark update — 0.1.1 preparation

The owner approved a dark text wordmark with a small green decorative dot.
Only brand HTML/CSS and coordinated app/package/runtime/image version literals
change; monitoring/provider/HA behavior and dependencies remain unchanged.
All 76 tests pass; Ruff lint/format, JavaScript syntax, publication scanning and
diff checks pass. Targeted real-browser checks use synthetic data at 1280, 390
and 320 px: no document overflow or wordmark/badge overlap, expected dark/green
colors, working brand navigation and visible keyboard focus. No console warnings
or errors. External review `18dac065-b5be-4e2b-8329-3eb263ccfca4` ended GO with no
findings. No new live provider call or full accessibility audit is claimed.
Public CI and live Supervisor update checks are pending.
