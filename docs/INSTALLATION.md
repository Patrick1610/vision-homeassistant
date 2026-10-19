# Installation and recovery

1. Use HA OS with Supervisor on amd64 or aarch64. The app requires no host mounts,
   host networking, hardware access, manager role or disabled protection mode.
2. Add **https://github.com/Patrick1610/vision-homeassistant** in the app store's repository
   dialog. Publication status is recorded in `VALIDATION.md`; a local folder is
   not proof of a publicly installable repository.
3. Refresh the store, select Vision, install and start it. The root `config.yaml`
   is discovered by Supervisor's recursive `**/config.*` scan. The root is the
   build context; there is intentionally no second project directory.
4. Open the web UI. Copy the user ID displayed on the locked page into
   `allowed_user_ids` in Vision's configuration. Save and restart Vision. This
   explicitly authorizes that HA user to see diagnostics.
5. Open Overview. Verify connected status, last successful sync, device/entity
   counts and the capability list. Optional reads that fail are marked unavailable;
   an empty Repairs list without an available capability is not proof of no issues.
6. Verify an automation detail against HA's trace view. Read-only operation needs
   no automation trigger or device interaction during this check.
7. Restart Vision and confirm historical observations remain in History. `/data`
   is the app's persistent private storage. Updates keep it. Uninstalling or
   deleting app data removes it; use HA app backups before that.
8. AI is optional. See `DOCS.md`, enter model, key, rates, budgets and consent,
   restart, preview evidence, then run a manual audit. Inspect usage and output.

## Troubleshooting

- **Access locked:** use the ID shown by this Ingress session; a missing user ID
  fails closed. `panel_admin` only controls sidebar visibility, not authorization.
- **Disconnected:** check Core is online and inspect capabilities. Supervisor must
  provide the Core API token. The app reconnects with bounded backoff.
- **Trace/log/config unavailable:** HA admin permission or components may be
  unavailable; JSON UI config endpoints do not cover all YAML-only automations.
  Retained traces may still provide structural summaries. Keep missing coverage
  distinct from zero executions or zero problems.
- **Invalid options:** Overview reports safe defaults; review the option types
  and ensure daily audits imply AI opt-in. Restart after correction.
- **Budget blocked:** enter correct positive model rates and inspect all recorded
  usage, including uncertain reservations. Do not raise limits as a debugging fix
  without deciding the intended budget.
- **No incidents/history after install:** Vision starts observing on first run;
  it deliberately does not copy the Home Assistant Recorder database.

## Local container verification

```sh
docker build --build-arg BUILD_ARCH=amd64 -t vision:0.1.0 .
docker run --rm -e VISION_DATA=/data -v vision-data:/data vision:0.1.0
```

Local mode binds loopback *inside* the container. A meaningful smoke check uses
`docker exec` against `http://127.0.0.1:8099/api/health` inside the container; it is
not exposed to the host. Production mode with a Supervisor token binds the
container interface and accepts only the Supervisor TCP peer plus authorized
Ingress user IDs. Do not expose the backend directly on a LAN.
