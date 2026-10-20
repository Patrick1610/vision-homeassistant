# Security

Vision has **no Home Assistant write capability in its application API**.
`vision/ha.py` implements a closed read-command allowlist and one fixed REST GET
for automation configuration. There is no service endpoint, generic HA proxy,
state/config writer, repair executor or AI tool. Tests assert denial of writes.

This is an application-level boundary: Supervisor grants a Core token with
broader rights. A compromised process could bypass Python policy. Keep protection
mode on and restrict access to the host and backups. Vision asks for no hardware,
Docker socket, host filesystem mounts, host networking or Supervisor manager API.

Ingress validates the actual TCP peer, not forwarded IP headers; uvicorn's proxy
header trust is disabled. It additionally requires `X-Remote-User-Id` to match an
explicit `allowed_user_ids` entry. The locked setup page reveals only the requesting
user's own Ingress ID. `panel_admin` is not relied on as an access-control rule.
Local development binds loopback and is for a trusted single-user machine.

Mutating local API requests require a custom header and no CORS permission is
granted. Untrusted text is escaped before HTML rendering. CSP restricts script,
connections, forms and framing to the same origin. AI cannot choose network
destinations; provider URLs are fixed HTTPS with certificate verification and no
redirects. HA credentials never enter provider code.

Keys live in Supervisor's private options or a private development options file,
not SQLite or frontend responses. The database and WAL files use mode 0600;
process umask is 0077. This is filesystem protection, **not encryption at rest**.
HA backups can contain credentials and observations; protect them accordingly.
Known credentials and common secret patterns are redacted from outputs and
formatted logs, including quoted/escaped assignments. Compact provider bundles
exclude local HA source free text and identifiers. Diagnostic projections require explicit
richer opt-in and pseudonymize typed identifiers and bounded errors; arbitrary
personal data cannot be perfectly removed. Inspect the exact request preview.

AI send accepts a single-use prepared request ID/digest, not a new task or arbitrary
body. Settings/process consent bindings and per-attempt revocation checks prevent
reuse after off→on, profile changes or restart. Provider bodies, schema, models and
failover limits are frozen before send. Follow-ups stay on the original local
snapshot; additional evidence sections are closed enums, with no HA tools, SQL,
shell or arbitrary fetch. Local schema and current-round support/counterevidence
validation apply even to billed responses. All provider text remains untrusted.

Public research has its own human-reviewed catalog/query plan and one bounded
job. Only fixed official HA paths and catalog GitHub REST paths can be read;
model text, browser URLs, household fields and remote links cannot choose fetches.
The client disables environment proxies, redirects, credentials and cookies;
response streaming, job limits and atomic persistent pre-dispatch quotas fail
closed. Public text stays untrusted and is escaped, never executed. A new frozen
provider request binds its final source excerpts/hashes and original local
snapshot. Current-round public references and manual-step references are locally
validated in addition to the original local evidence schema.

Report security problems privately to the repository maintainer through the
repository's private vulnerability reporting facility when enabled. Do not post
tokens, raw traces, personal logs or household details in public issues. If that
facility is unavailable, request a private contact channel without disclosing the
vulnerability publicly.

Future write support would need a distinct denied-by-default action capability,
typed proposals, policy checks, explicit time-bounded authorization, preconditions,
audit trail and outcome verification. None of its executors or permissions are
implemented in this read-only application.
