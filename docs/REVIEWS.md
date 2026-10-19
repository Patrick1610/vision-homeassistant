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
