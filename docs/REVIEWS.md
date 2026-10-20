# External source reviews

All four milestone streams ended **GO**, with no open critical, high or medium
findings in their reviewed scope. This is source-review acceptance, not live HA
installation, provider billing, GitHub CI or release approval.

| Stream | Review ID | Final result |
| --- | --- | --- |
| Foundation: Ingress, credentials, options, SQLite ownership, lifecycle | `b5b96318-e606-4445-8953-73fc10826b35` | GO |
| Monitoring: read gateway, trace semantics, registry coverage, log grouping/counters | `aa664480-c440-4398-8019-7b6394b61ae1` | GO on initial implementation `e2046c3` |
| Intelligence: minimization, provider contracts, budgets/failover, evidence validation | `1703f92e-a770-469c-aef6-8ed59d053a7d` | GO |
| Release integration: frontend/API, CI, history/tag scanning, privacy claims | `eef64259-009b-4d2b-9be9-642aa8ef9783` | GO |
| Follow-up: complete bounded HTTP reads and container restart readiness | `48325ab3-5893-4d3f-bc55-8187b45e4637` | GO on correction `898ebb7` |
| Public CI: repository-relative local-artifact exclusion in packaging test | `b622fc2e-52e8-4e2f-8edb-bd58a1fa0b6f` | GO on correction `fd201aa` |
| Light UI: palette, responsive layout, status contrast and keyboard focus | `50f1f5ef-998d-40fe-aad5-91f89a742eba` | GO after both low notes corrected |
| Live qualification: release evidence, privacy and publication-status wording | `e9072db7-fc88-4108-9bd1-8035f6f957d6` | GO after pending-publication wording corrections |
| Wordmark 0.1.1: dark wordmark, green accent, accessibility and version alignment | `18dac065-b5be-4e2b-8329-3eb263ccfca4` | GO; two documentation nits corrected |

Corrections include explicit Ingress user authorization, safe options recovery,
complete log-redaction sinks, cross-task transaction guards, source-backed trace
fixtures, correct Supervisor websocket routing, Anthropic quota categorization,
resolved-incident evidence, registry-only entities, persistent log-count deltas
and a scanner covering current files plus historical blobs/commits/annotated tags.

Accepted v0.1 limitations: short synchronous SQLite operations use one event
loop; per-marker log-counter metadata is not automatically compacted; internal
HA frontend APIs can change or require privileges; model/provider behavior has
only deterministic HTTP-simulation coverage. Observation gaps and retained-trace
limits remain visible. See VALIDATION.md and SECURITY.md.

Jev was invoked but returned `JEV_API_KEY is not set`; no score or successful
Jev review is claimed. External Claude reviews, executable tests and actual image
checks above supplied the available independent verification.

The follow-up review first found a medium issue in the test readiness loop; it was
corrected and covered by two tests before final GO. One low note was accepted:
malformed health JSON fails the smoke check immediately instead of being retried.
The fixed health endpoint returns a complete object or a request failure, so
malformed output remains a test failure. Actual rebuilt-container smoke checks
subsequently passed on both architectures; the Linux and Mac suites each passed
76 tests. The reviewer did not independently execute those tests.

The public CI correction changes only a test's local `work` exclusion. The low
note about the adjacent hidden/rootfs filter is accepted: that filter deliberately
uses absolute path parts to match the official Supervisor implementation. The
review reported no open critical/high/medium findings. CI results and actual HA
installation remain separately verified gates.

The live-qualification review changes documentation only. A premature unreleased
tag link was removed and the changelog explicitly marked publication pending.
Both findings were verified resolved before final GO; actual tag/release creation
is a separate browser operation with anonymous Git readback. Transient reviewer
transport/response-schema errors were retried in the same review session.

The 0.2.0 data-foundation review `70057443-b25f-46e4-852f-a9df98071c8b`
accepted immutable `7034e224a33671e5ccf199725385467fd5a38ae9` in its third
critical round with no critical/high/medium findings and four nonblocking lows.
Its first two candidates were rejected and corrected. B handles the event-row
tie, conservative backup cleanup and duplicate compact-metadata notes. The
remaining conservative historical-time blocker is preserved and explained,
because unverified timestamps cannot establish ordering. Jev was attempted but
its required key was unavailable; no score is claimed. B awaits its own immutable
candidate and external review; A acceptance is not B/release/live acceptance.

The B critical review `d3e801fb-824c-4bab-bbff-7a5ee7664818`, channel
`vision020-b`, rejected exact `2f9899a7de6583969fb6784463f73b3e8eec710d`:
three medium findings (orphan attention lifecycle/unbounded notes, repeated
landing-path AST/run scans, unbounded static fanout) and three lows (backup
collision overwrite, malformed retained evidence, GET write amplification).
Authorized corrective B work adds preserving schema 5 episode binding, bounded
note/static selection with explicit coverage, monitor-owned gated refresh,
bulk expected flags, no-clobber backups and explicit unknown evidence. New
synthetic regressions cover the real scaled HTTP paths, a concurrent WAL writer,
schema-4 upgrade, generation lifecycle, malformed payloads and availability-only
UI selection. Same-channel follow-up is pending; no B GO is claimed.

The same stream's second round accepted the earlier mechanisms on `5a2e8bc`,
but returned NO_GO with one new medium: repeated migration failures created
unbounded full backup copies. Two lows concerned per-automation coverage maps
in every response and per-card run lookup. The next correction proves snapshot
reuse with fresh SQLite-copy comparison, gates copy count/bytes/free space,
handles uncertain crash temporaries conservatively and exposes only fixed safe
startup reasons. Aggregate page coverage and one bulk run/evidence query replace
the two linear page costs. Independent and same-channel follow-up remain pending.

The third B round rejected `2f90d89` for adoption of a live-database hardlink as a
rollback snapshot. Independent testing additionally demonstrated a WAL write in
the backup→migration gap. Corrective startup now holds the writer reservation
across both operations and uses a separate read-only backup source. Main/WAL/SHM
inode aliases fail closed. Low notes receive safe actionable pending/size reasons,
batched ephemeral metadata and stale-key cleanup; numeric run-ID batch lookup
is covered. Two-startup and competing-writer tests include failure/retry, and the
hardlink test restores a source whose bytes exactly match a fresh API snapshot.
Nondeterministic valid copy bytes hit the retained cap rather than growing without
bound. Same-channel critical follow-up is pending; no B GO is claimed.

B's fourth critical follow-up accepted immutable `9a3dd713e1ff` with no open
critical/high/medium findings. Independent 213-test, two-architecture container,
schema-1 upgrade/restart/old-0.1.1 restore and startup-alias/concurrency probes
passed. The subsequent dev.1 package was separately reviewed and published; its
public/live evidence is recorded in VALIDATION.md.

C's critical stream `928fc673-868b-41ab-bce6-de25f40584f5`, channel `vision020-c`,
accepted immutable `3e533aac7ecf16f55118a869b03f9cb9502e4f43` in sequence 6 with
zero open critical/high/medium findings. The three initial review chunks and
consolidated follow-ups closed eight accepted mediums, five lows and the two
later accounting/withdrawal mediums. Controller adjudication retained native
structured-output GA, strict configuration failure, per-round reference scope
and conservative uncertain billing. Independent tests/container/migration and
real Safari checks qualify the named candidate separately from that source review.
Three final lows remain nonblocking: D handles rejected-send status recovery;
future source-table upserts and externally lost accounting triggers remain
unsupported-path backlog work, with no store/schema expansion in D.

D's action-oriented UI and 0.2.0-rc.1 packaging require their own frozen-source
review, layout/navigation qualification and public/live gates. No D review or
final stable-release GO is claimed here. Jev remains unavailable because its API
key is not configured; no score is invented.

The D critical review `474f6d39-7daa-4651-8d25-077d4cbf6f84`, channel
`vision020-d`, rejected exact `b7764fdf33cc4e23eb31c583aa945591d1c1f6d7` with one
high (completed audit links redirected away from the frozen sent body), two
mediums (background failure discarded engaged content; secondary read failure
hid primary priorities) and five lows. Independent testing also proved a mixed-
error manual-plan path mismatch. Consolidated corrective D preserves audit views,
scopes/consumes send-session auto-opening, degrades secondary reads with visible
unknowns, retains last-loaded content after background failure and binds task/path
from one matching typed observation. Five lows retain all references, source
checks, actual gap dates, related-case links and server comparison copy. Same-
channel follow-up is required; no corrective D GO is claimed.

D sequence 2 closed all original high/two medium/five low findings and the mixed-
step P2 on `9fadab4b6f972d02359ad065be657158c64ba390`. NO_GO remained solely for
the independently reproduced 320 px affected-id overflow, also present on settled
D1. The controller authorized D3's minimal width/wrap correction and four cheap
lows covering replacement-history scope, attention-total wording, changes-only
uncertainty and refresh-notice preservation. Scratch Safari layout preflight is
separate from the required immutable D3 same-channel follow-up; no D3 GO is claimed.
