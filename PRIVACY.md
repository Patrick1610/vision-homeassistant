# Privacy

Local monitoring contacts only your Home Assistant. Vision has no analytics,
telemetry beacon, external fonts, CDN assets or automatic AI request by default.

SQLite stores availability transitions, grouped incidents, sanitized automation
structure/step summaries, local entity/dependency references, attention states,
exceptions, analyses, prepared requests and token/cost records. It does not copy
Recorder history, numeric sensor measurements, raw traces, raw automation
configuration, state attributes or credentials. Selected diagnostic messages are
redacted before storage. Local entity/device/service/area/label identifiers can
contain human names; structural sanitization does not make local history anonymous.

AI is separately opt-in and defaults off. The `ai_privacy` setting is a ceiling:

- **local_only:** local evidence inspection; no provider request or usage reservation.
- **compact (default):** bounded typed counts, coverage, availability/run summaries
  and structural counts. Local HA source names/identifiers, error prose, configuration
  operands and user questions stay out of outbound requests. Follow-ups use an
  enum focus and may include bounded re-sanitized earlier provider conclusions,
  uncertainty, unknowns and manual/validation proposals; every round has its own
  exact preview. Dependency/change/sibling context uses closed typed summaries.
- **diagnostic:** explicitly configured richer consent, plus an unchecked per-preview
  consent box. Bounded redacted errors, safe structural operands and pseudonymous
  identifiers can be included. Aliases cover entity/device/area/label/service/
  integration/run/configuration references, including dictionary keys and error
  text. Raw templates, variables and action payloads are unavailable.

Quoted JSON/Python secret assignments, configured secrets and common credential/
address/path patterns are redacted. This cannot guarantee removal of all personal
information or unrecognized secrets from arbitrary text. Avoid private details in
entity names, errors and questions; inspect each exact request body before sending.
Existing options without a privacy field load as compact; no update opts an existing
installation into richer data.

The preview shows the exact credential-free body for each configured provider,
including task instructions, schema, selected evidence/provenance and bounded prior
context. A digest binds sending to that frozen request. Local evidence/identifier
mappings are separate and stay in Vision. Each scoped follow-up has its own preview
and fresh evidence references. Previous references cannot silently mean a new fact.
Additional sections are a reviewed enum selection from the initial local snapshot;
there is no autonomous HA lookup, SQL, shell or evidence tool. Explicitly enabled
daily audits remain scheduled compact audits; diagnostic consent never transfers
to the scheduler. Disabling AI, choosing local-only, revoking a prepared request or
restarting invalidates pending consent. Already transmitted requests cannot be recalled.

Requests go directly to Anthropic or OpenAI; those services' account terms,
processing locations and retention policies apply. Vision sets OpenAI `store:false`
but does not promise provider-side zero retention. A configured backup can receive
only its displayed frozen request on technical failover; budget failover needs
separate configured consent. No paid call is made by default.

Local history defaults to 90 days. Active incidents/open intervals persist while
open; billing records persist 400 days so retention cannot bypass spending limits.
Prepared request details follow ordinary retention; minimal request/round/digest/
attempt receipts stay linked to billing for 400 days even after a body expires.
Expired unused previews are discarded. New AI admission has request-count and
payload-byte bounds and can block before payment; it never evicts existing
analyses or completed exact bodies merely to admit another request. These bounds
do not cap the complete SQLite/WAL/backups on disk. Consistent migration snapshots also contain full private database history. Keep
those backups local and allow storage for retained generations. Uninstalling or
deleting app data removes the local database; old HA backups may retain copies.
Public research is a separate explicit action: only a shown closed technical
category, bundled integration slug and current authenticated Core version can
enter public HA/GitHub queries. Household identifiers, questions, errors, keys
and custom integration names are excluded. A public host still receives the
connection IP and generic technical query. No Reddit credential/workaround is
used. Fetching sources does not send an AI request. Public excerpts are normalized,
redacted and household-alias checked before their content hashes and the new
provider bodies are frozen. Those excerpts are untrusted public claims, not
additional private HA free text. Compact local-evidence limits remain unchanged.

Plans/jobs/cache are bounded and process-local; restart discards them, while
quota/backoff persists. Exact source excerpts/provenance are retained with the
received analysis through ordinary analysis retention even after request expiry.
Following a scoped conversation never refetches sources. New diagnostic previews
require fresh explicit consent; public research does not increase the privacy
ceiling. Share only synthetic or carefully reviewed,
redacted diagnostics when filing a public issue.

Public research has no separate installation option in this version. To remove
its outbound capability, disable AI (`ai_enabled: false`) or set the privacy
ceiling to `ai_privacy: local_only`. Retained local evidence and received history
remain inspectable. Active upstream backoff shows its host/expiry and never exceeds
24 hours per response; there is no automatic research retry or reset action.
