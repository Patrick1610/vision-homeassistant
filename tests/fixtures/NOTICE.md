# Home Assistant trace test data

`ha_trace_semantics.json` contains normalized semantic projections derived from
the Home Assistant Core **2026.10.2** test data. Original sources:

- https://github.com/home-assistant/core/blob/2026.10.2/tests/components/trace/fixtures/automation_saved_traces.json
- https://github.com/home-assistant/core/blob/2026.10.2/tests/helpers/test_script.py
- https://github.com/home-assistant/core/blob/2026.10.2/tests/components/trace/test_websocket_api.py
- https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/trace/models.py

Copyright Home Assistant contributors. Apache License 2.0; see `HA_LICENSE.txt`.
Original file hashes and normalization are recorded in the fixture. Configuration,
variables, context IDs and unneeded source content were removed. This source-level
evidence is distinct from installing Vision on a live HA OS/Supervisor instance.
