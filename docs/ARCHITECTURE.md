# Architecture

Browser → Ingress → FastAPI → domain services → SQLite. Monitor → closed HA
read gateway → HA Core proxy. Intelligence → minimized evidence → provider
adapters → validated diagnosis → local history. AI never receives a transport.

The root contains `config.yaml`, `repository.yaml` and Dockerfile. Supervisor
builds the app on-device. No host port, hardware mounts, elevated capability,
Supervisor manager role or host networking. `/data` persists SQLite and app
options. Ingress verifies the actual TCP peer (`172.30.32.2`) with uvicorn proxy
header trust disabled. Local mode binds only 127.0.0.1.

`config.py`: private options, constraints, redacted views. `ha.py`: allowlisted
REST/WS, event subscription and reconnect. `monitor.py`: observation semantics.
`store.py`: transactional history, versioned initial schema, deduplication and retention.
`ai.py`: provider interface, budgets, schema validation and evidence minimization.
`app.py`: local API and lifecycle. `static/`: dependency-free responsive UI,
relative links and escaped untrusted text.

History stores only availability transitions, run/trace summaries, issue changes,
analyses and usage. Numeric sensor history and raw traces/config/logs are not
retained. Reconnects create coverage markers; offline periods are not presented
as continuously measured uptime. Future action policy would require separately
authorized capability and audit stages, absent from this version.

## Source validation (2026-10-19)

Official HA docs now redirect from developers.home-assistant.io to contributors:

- https://contributors.home-assistant.io/apps/reference/configuration/
- https://contributors.home-assistant.io/apps/guides/communication/
- https://contributors.home-assistant.io/apps/guides/ingress/
- https://contributors.home-assistant.io/core/internals/websocket-api/
- https://contributors.home-assistant.io/core/internals/rest-api/

Component-specific reads are checked against official Core source (2026.10.2):
`components/trace/{websocket_api,util}.py`, `repairs/websocket_api.py`,
`system_log/__init__.py`, `automation/config.py`. These are internal frontend
protocols and may be unavailable or change; failures must show degraded coverage.

HA's token scope is broader than Vision's application policy. The transport
allowlist enforces read-only behavior in this code; a compromised process holding
the token could bypass application policy. No claim of server-enforced read scope.

Supervisor root discovery was checked against current official `supervisor/store/data.py`
(source sha256 `3714417b3505d7308b6c1b46d6717d4d163042a5ca6f83c5a62ef1e9ea3b22ce`):
`path.glob("**/config.*")` includes the root; suffixes are JSON/YAML and hidden/rootfs
directories are excluded. This is source-level discovery evidence, not live install evidence.

The image is the official multiarchitecture Python image pinned by index digest.
Supervisor/Docker selects the target architecture; BUILD_ARCH supplies HA labels.
BUILD_FROM is deliberately not consumed because the application needs this pinned
Python runtime rather than an S6 image. init:true delegates signal reaping to Docker.
Dependencies are resolved with uv 0.13.1, pinned including transitive packages and
PyPI hashes. The app executes copied Python sources directly, without a second
build-isolation network resolution.

Supervisor REST uses `http://supervisor/core/api/`, but its WebSocket endpoint
is `http://supervisor/core/websocket` (HTTP Upgrade). A direct Core connection
uses `/api/websocket`. These are separate runtime URLs and both routing shapes
are exercised by the full local connection/reconnect integration test.

Logs use the native `system_log/list` aggregate on each poll. Group identity is
the logger, source location and final traceback frame (hashed, not retained raw),
matching HA's grouping rather than its changing five-message deque. Persisted
counter markers distinguish re-polling from new occurrences and buffer resets.
Vision does not subscribe to `system_log_event`: HA emits a fresh count-one entry
there, so combining it with aggregate counts would double-count occurrences.
