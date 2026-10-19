# Privacy

Local monitoring contacts only your Home Assistant. Vision has no analytics,
telemetry beacon, external fonts, CDN assets or automatic AI request by default.

SQLite stores availability transitions, grouped incidents, trace outcome summaries,
local entity/dependency references, exceptions, analyses and token/cost records.
It does not copy Recorder history, numeric sensor measurements, raw traces,
raw automation configuration, state attributes or credentials. Selected diagnostic
messages are retained only after redaction; avoid including private data in entity
names or log messages even when no AI is used.

AI is separately opt-in. Before an analysis, a bounded typed projection contains
counts, coverage indicators, availability summaries, run outcomes and structural
counts. Evidence uses E1/E2 identifiers. Entity names/IDs, device names, logs,
configuration values, exception reasons, addresses and credentials are excluded.
The mapping back to local objects stays in SQLite. Preview the transmitted bundle
in Intelligence. Minimized data still reveals broad household-system patterns.

Requests go directly to Anthropic or OpenAI; those services' account terms,
processing locations and retention policies apply. Vision sets OpenAI `store:false`
but does not promise provider-side zero retention. A configured backup can receive
the same evidence on technical failover; budget failover needs separate consent.

Local history defaults to 90 days. Active incidents and open intervals persist while open; billing
records persist 400 days so ordinary retention cannot bypass spending limits.
Uninstalling/deleting the app data deletes the local database; old HA backups may
retain copies. Vision does not send data to GitHub. Share only synthetic or
carefully reviewed/redacted diagnostics when filing a public issue.
