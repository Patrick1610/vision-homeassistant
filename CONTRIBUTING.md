# Contributing

Read AGENTS.md and the specification before changing behavior. Preserve the
read-only invariant. Use synthetic test fixtures; do not submit household logs,
real entity names, credentials or personal installation details.

Run the README's tests, Ruff, JavaScript syntax check and container smoke test.
Tests should exercise observations, missing coverage and failure behavior. Include
a focused independent review for meaningful changes. Never describe a trigger as
completed without outcome evidence, or an AI hypothesis as an established cause.

Keep changes small and document material limits. Publish only after validation,
secret review, successful push and remote hash readback. GitHub publication and
live installation are separate evidence claims.

For the interface regressions, use Node.js 22 or newer and run
`npm ci --ignore-scripts --no-fund --no-audit` followed by `npm test`.
The exactly locked jsdom dependency executes the real HTML and complete app script
against synthetic transport. It is test-only, excluded from the Python runtime
and container. DOM behavior tests complement actual browser/layout qualification.

Install the locked Python test requirements before running the DOM suite, as in
README/CI: `python -m pip install --require-hashes -r requirements-test.txt`.
One DOM regression replays actual local ASGI POST/GET fixtures; it needs that
qualified Python environment as well as Node/jsdom. The fixture binds imports to
the checked-out source, uses a 30-second startup deadline and fails explicitly
on missing Python dependencies; it never skips the regression or contacts HA/AI.
