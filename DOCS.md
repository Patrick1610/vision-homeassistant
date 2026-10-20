# Vision configuration

Change app options in Home Assistant and restart Vision to apply them. No
configuration is written to Home Assistant by Vision. A validation failure falls
back to safe defaults, disables AI and is reported as degraded configuration.

| Option | Meaning |
| --- | --- |
| `allowed_user_ids` | HA Ingress user IDs allowed to see diagnostics. Empty locks the UI. |
| `poll_seconds` | Inventory, traces, Repairs and log polling, 15–3600 s; default 60. State/trigger events are also subscribed live. |
| `retention_days` | Incident, interval, execution and analysis retention, 7–730 days; default 90. Billing records remain 400 days to protect budget accounting. |
| `ai_enabled` | Explicit consent to send reviewed evidence to configured providers; default false. |
| `ai_privacy` | `local_only`, `compact` (default) or explicitly configured `diagnostic`. Diagnostic also requires consent for each preview. Existing options default to compact. |
| `daily_audit` / `audit_hour_utc` | Optional once-daily attempt after this UTC hour. Only runs with fresh connected monitoring data; no automatic retry that day after a failed scheduled attempt. |
| `primary_provider` | `anthropic` or `openai`. Both can be configured simultaneously. |
| `allow_budget_failover` | Separate permission to use backup after primary daily budget or recognized remote quota exhaustion. Defaults false. Global monthly ceiling still applies. |
| `monthly_budget_usd` | Combined monthly application estimate ceiling, UTC calendar month; default $5. |
| `max_output_tokens` | Per-request generated-token limit, 512–8192; default 2048. |
| `{provider}_api_key` | Optional private key stored in Supervisor app options. Never displayed in Vision or sent to the other provider. |
| `{provider}_model` | Exact compatible model ID from your provider account. No model is silently selected or substituted. |
| `{provider}_daily_budget_usd` | Per-provider application estimate ceiling, UTC day; default $1. |
| `{provider}_input_usd_per_million` / `{provider}_output_usd_per_million` | Your model's current USD rates. Both must be positive to permit requests. Defaults 0, blocking AI until priced. |

Use a model supporting the configured provider protocol: OpenAI Responses with
strict JSON Schema output; Anthropic Messages with native structured output (`output_config.format`).
Both responses must match the full locally validated schema. Models, availability and pricing change: consult your provider account.
Vision does not treat a model ID or entered rate as proof of a billing contract.

Technical connection errors and 5xx responses can fail over to the backup.
Rate limits retry twice with exponential backoff/jitter and bounded Retry-After,
then may fail over. Authentication/configuration errors are surfaced. Every new
analysis tries the primary again, providing automatic recovery. Budget errors only
permit failover with the separate opt-in; no failover can bypass the global cap.

Before sending, Vision reserves a conservative token-cost estimate. Known usage
replaces the reservation at configured rates; timeout, cancellation, process crash
or malformed usage retain an uncertain reservation. This may overestimate charges,
deliberately. There is no automatic refund of uncertain requests. Provider-side
spend limits remain the authoritative protection against actual charges, including
pricing errors, provider overhead or other apps using the same key.

In **Settings**, add an expected-offline exception with a reason and expiry. This
reduces attention for the availability case while preserving its active source fact. No device,
automation or HA Repairs entry is modified.

Spook and Watchman are optional. Their entities/issues may appear like any other
integration; no dedicated service call or dependency is required.

Open a local dossier or selected automation runs, then choose a focused investigation.
Prepare and inspect the exact request preview for both configured providers before
sending. The shown task, runs, privacy profile, schema and bounded context are frozen;
a changed selection needs a new preview. Revoking stops further attempts, while
already transmitted usage stays recorded. Follow-ups stay scoped to this original
investigation and require their own preview. Compact uses a focus selector; free
questions require diagnostic consent. Local-only never reserves usage or calls a
provider. A once-daily explicitly enabled audit remains compact and retains its
scheduled exact request.

A refusal, incomplete response or invalid diagnosis/citation still records received
billed usage. Missing usage, cancellation and interrupted attempts retain uncertain
reservations. Model protocol compatibility is verified with synthetic HTTP mocks;
Vision does not claim a live paid-provider/model qualification. See
[privacy](PRIVACY.md) and [architecture](docs/ARCHITECTURE.md) for bounds and gaps.
