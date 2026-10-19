"use strict";
const pages = [
  "Overview",
  "Devices",
  "Automations",
  "Issues",
  "Intelligence",
  "History",
  "Settings",
];
const $ = (s) => document.querySelector(s),
  content = $("#content"),
  notice = $("#notice");
$(".skip-link")?.addEventListener("click", (event) => {
  event.preventDefault();
  $("#main").focus();
});
const esc = (value) =>
  String(value ?? "—").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const date = (v) =>
  v
    ? new Date(typeof v === "number" ? v * 1000 : v).toLocaleString()
    : "Not observed";
const duration = (v) =>
  v < 60
    ? Math.round(v) + " s"
    : v < 3600
      ? Math.round(v / 60) + " min"
      : (v / 3600).toFixed(1) + " h";
const parse = (v) => (typeof v === "string" ? JSON.parse(v) : v);
const badge = (value, cls = "") =>
  `<span class="pill ${esc(cls)}">${esc(value)}</span>`;
const card = (title, body) =>
  `<section class="card"><h2>${esc(title)}</h2>${body}</section>`;
const empty = (text) => `<p class="empty">${esc(text)}</p>`;
function table(headers, rows) {
  return rows.length
    ? `<div class="tablewrap"><table><thead><tr>${headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`
    : empty("No observations yet.");
}
async function api(path, options = {}) {
  const r = await fetch("api/" + path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Vision-Request": "1" },
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(
      typeof data.detail === "string" ? data.detail : "Request failed",
    );
  return data;
}
pages.forEach((p) => {
  const a = document.createElement("a");
  a.href = "#" + p.toLowerCase();
  a.textContent = p;
  $("#nav").append(a);
});
let generation = 0;
function searchTable() {
  const input = $("#search");
  if (input)
    input.addEventListener("input", () => {
      document.querySelectorAll("tbody tr").forEach((row) => {
        row.hidden = !row.textContent
          .toLowerCase()
          .includes(input.value.toLowerCase());
      });
    });
}
const search = (placeholder) =>
  `<div class="toolbar"><input id="search" type="search" aria-label="Search inventory" placeholder="${esc(placeholder)}"></div>`;
function findings(analysis) {
  if (!analysis)
    return empty("No audit completed. Local monitoring works without AI.");
  const result = parse(analysis.result);
  return (
    `<p>${esc(result.summary)}</p><p class="muted">AI hypotheses · ${esc(analysis.provider)} · ${esc(analysis.model)} · ${esc(date(analysis.created))}</p>` +
    (result.diagnoses.length
      ? result.diagnoses
          .map(
            (d) =>
              `<article class="row"><h3>${badge(d.severity, d.severity)} ${esc(d.finding)}</h3><p>${esc(d.next_step)}</p><details><summary>Evidence, uncertainty & validation</summary><dl><dt>Evidence references</dt><dd>${esc(d.evidence.join(", "))}</dd><dt>Confidence</dt><dd>${esc(d.confidence)}</dd><dt>Uncertainty</dt><dd>${esc(d.uncertainty)}</dd><dt>Validation</dt><dd>${esc(d.validation)}</dd></dl></details></article>`,
          )
          .join("")
      : empty("No supported finding returned."))
  );
}
function bindAnalysis() {
  document.querySelectorAll("[data-analyze]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await api("intelligence", {
          method: "POST",
          body: JSON.stringify({
            kind: button.dataset.analyze,
            target: button.dataset.target || null,
          }),
        });
        notice.textContent =
          "Analysis started. Results appear in Intelligence when complete.";
      } catch (e) {
        notice.textContent = e.message;
      } finally {
        button.disabled = false;
      }
    }),
  );
}
function issueRows(issues, buttons = false) {
  return table(
    [
      "Issue",
      "Source / priority",
      "Observed",
      "Occurrences",
      "Status",
      ...(buttons ? ["Analysis"] : []),
    ],
    issues.map((i) => [
      `${esc(i.title)}<details><summary>Evidence</summary><pre>${esc(JSON.stringify(parse(i.detail), null, 2))}</pre></details>`,
      `${esc(i.source)} · ${badge(i.severity, i.severity)}`,
      `${esc(date(i.last_seen))}<br><small>First: ${esc(date(i.first_seen))}</small>`,
      esc(i.occurrences),
      badge(i.active ? "Needs review" : "Resolved / expected"),
      ...(buttons
        ? [
            `<button data-analyze="incident" data-target="${esc(i.key)}">Analyze</button>`,
          ]
        : []),
    ]),
  );
}
async function overview() {
  const data = await api("overview");
  const health = data.health;
  return `<div class="grid">${[
    ["Entities", data.entities, "In current inventory"],
    ["Devices", data.devices, "Registered in Home Assistant"],
    ["Automations", data.automations, "Observed, never controlled"],
    ["Unexpected offline", data.unavailable, "Unknown or unavailable"],
  ]
    .map(([a, b, c]) =>
      card(a, `<div class="metric">${esc(b)}</div><small>${esc(c)}</small>`),
    )
    .join("")}</div><div class="split">${card(
    "Observation coverage",
    `<p>${badge(health.connected ? "Connected" : "Disconnected", health.connected ? "success" : "warning")}</p><p>Last inventory sync: ${esc(date(health.last_sync))}</p><p class="muted">Monitoring session: ${esc(date(data.coverage_started))}. Downtime is an observation gap. Status may be stale while disconnected.</p><details><summary>Capabilities</summary>${table(
      ["Read capability", "Availability"],
      Object.entries(health.capabilities).map(([k, v]) => [esc(k), esc(v)]),
    )}</details>`,
  )}${card("Latest audit & improvements", findings(data.latest_audit))}</div>${card("Recent incidents", issueRows(data.issues.slice(0, 10)))}`;
}
async function devices() {
  const data = await api("devices");
  return (
    search("Find a device, entity or state…") +
    card(
      "Entities",
      table(
        ["Entity", "Availability", "Device", "Observed offline", "Exception"],
        data.entities.map((e) => [
          `${esc(e.name)}<br><small>${esc(e.entity_id)}</small>`,
          badge(
            e.availability,
            e.availability === "available" ? "success" : "warning",
          ),
          esc(e.device_id),
          `${esc(e.outages.episodes)} observed segments<br><small>${esc(duration(e.outages.seconds))} measured</small>`,
          e.expected_offline ? badge("Expected offline") : "—",
        ]),
      ),
    ) +
    card(
      "Device registry",
      table(
        ["Device", "Manufacturer", "Model", "ID"],
        data.devices.map((d) => [
          esc(d.name_by_user || d.name || "Unnamed device"),
          esc(d.manufacturer),
          esc(d.model),
          esc(d.id),
        ]),
      ),
    ) +
    `<p class="muted">Segments are bounded by observed transitions and connection gaps; they are not an exact count of physical outages. Disabled entities without a state are excluded from availability monitoring.</p>`
  );
}
async function automations(entity) {
  if (entity) {
    const data = await api("automations/" + encodeURIComponent(entity));
    const rows = data.runs.map((r) => [
      esc(date(r.started)),
      badge(r.outcome, r.outcome),
      r.triggered ? "Observed" : "Not observed",
      `<pre>${esc(JSON.stringify(parse(r.detail), null, 2))}</pre>`,
    ]);
    return (
      `<p><a href="#automations">← All automations</a></p>` +
      card(
        data.name,
        `<p>${esc(data.entity_id)} · ${badge(data.enabled == null ? "Not loaded" : data.enabled ? "Enabled" : "Disabled")}</p><p>Last HA trigger: ${esc(date(data.last_triggered))}</p><p class="muted">${esc(data.coverage)}</p><button class="primary" data-analyze="automation" data-target="${esc(entity)}">Analyze automation</button>`,
      ) +
      `<div class="split">${card(
        "Execution statistics",
        table(
          ["Outcome", "Retained runs", "Observed triggers"],
          data.stats.map((s) => [
            badge(s.outcome, s.outcome),
            esc(s.count),
            esc(s.observed_triggers),
          ]),
        ),
      )}${card(
        "Configuration structure & dependencies",
        data.structure
          ? `<dl>${Object.entries(data.structure)
              .map(
                ([k, v]) =>
                  `<dt>${esc(k)}</dt><dd>${esc(Array.isArray(v) ? v.join(", ") : v)}</dd>`,
              )
              .join("")}</dl>`
          : empty(
              "Configuration/trace not available with current HA permissions or retention.",
            ),
      )}</div>` +
      card(
        "Execution evidence",
        table(["Started", "Trace outcome", "Trigger event", "Detail"], rows),
      ) +
      card(
        "AI analyses",
        data.analyses.length
          ? data.analyses.map(findings).join("")
          : empty("No analysis for this automation."),
      ) +
      card("Issues", issueRows(data.issues))
    );
  }
  const data = await api("automations");
  return (
    search("Find an automation…") +
    card(
      "Automation inventory",
      table(
        [
          "Automation",
          "Enabled",
          "Last triggered",
          "Run outcomes",
          "Usage signal",
        ],
        data.map((a) => [
          `<a href="#automations/${encodeURIComponent(a.entity_id)}">${esc(a.name)}</a><br><small>${esc(a.entity_id)}</small>`,
          badge(a.enabled == null ? "Not loaded" : a.enabled ? "Yes" : "No"),
          esc(date(a.last_triggered)),
          a.stats
            .map((s) => `${esc(s.outcome)}: ${esc(s.count)}`)
            .join("<br>") || "No retained traces",
          a.possibly_unused
            ? badge("Possibly unused", "warning")
            : "Trigger recorded",
        ]),
      ),
    ) +
    `<p class="muted">No recorded last trigger is a hypothesis of non-use. Trigger events alone never prove successful completion. Click an automation for evidence.</p>`
  );
}
async function issues() {
  const data = await api("issues");
  return (
    search("Search incidents and evidence…") +
    card("Issues & recurring problems", issueRows(data, true)) +
    `<p class="muted">Log warnings remain observations needing review. A warning disappearing from HA's bounded log buffer does not prove its cause was repaired.</p>`
  );
}
async function intelligence() {
  const data = await api("intelligence");
  return (
    card(
      "Intelligence",
      `<p>${badge(data.enabled ? "AI opted in" : "AI disabled", data.enabled ? "success" : "warning")} ${badge(data.running ? "Analysis running" : "Idle")}</p><p>Use the same minimized evidence with either provider. Findings are hypotheses with evidence references, never automatic actions.</p><div class="toolbar"><button class="primary" data-analyze="audit" ${!data.enabled || data.running ? "disabled" : ""}>Run system audit</button><button id="preview">Preview transmitted evidence</button></div>${data.last_error ? `<p class="warning">${esc(data.last_error)}</p>` : ""}${data.daily ? `<p class="muted">Daily audit: ${esc(data.daily.day)} · ${esc(data.daily.status)}</p>` : ""}<div id="evidence-preview"></div>`,
    ) +
    card(
      "Provider usage & estimated costs",
      table(
        [
          "Provider / model",
          "Status",
          "Input tokens",
          "Output tokens",
          "Estimated USD",
        ],
        data.usage.map((u) => [
          `${esc(u.provider)}<br>${esc(u.model)}`,
          esc(u.status),
          esc(u.input_tokens),
          esc(u.output_tokens),
          Number(u.cost_usd).toFixed(6),
        ]),
      ),
    ) +
    card(
      "Audit history & recommendations",
      data.analyses.length
        ? data.analyses
            .map(
              (a) =>
                `<div class="row">${findings(a)}<details><summary>Local evidence mapping</summary><pre>${esc(JSON.stringify(parse(a.evidence).mapping, null, 2))}</pre></details></div>`,
            )
            .join("")
        : empty(
            "No AI analysis yet. Enable AI and configure a provider, model, rates and budget in app configuration.",
          ),
    )
  );
}
async function history() {
  const data = await api("history");
  return (
    card(
      "Availability transitions",
      table(
        ["Entity", "State", "Start", "End", "Coverage"],
        data.availability.map((a) => [
          esc(a.entity_id),
          badge(a.state, a.state === "available" ? "success" : "warning"),
          esc(date(a.started)),
          a.ended ? esc(date(a.ended)) : "Observed open interval",
          a.uncertain ? "Gap / uncertain boundary" : "Observed interval",
        ]),
      ),
    ) +
    card(
      "Automation execution history",
      table(
        ["Automation", "Started", "Outcome", "Trigger"],
        data.runs.map((r) => [
          esc(r.entity_id),
          esc(date(r.started)),
          badge(r.outcome, r.outcome),
          r.triggered ? "Observed" : "Not observed",
        ]),
      ),
    ) +
    card(
      "Request accounting",
      table(
        ["Time", "Provider / model", "Status", "Estimated USD"],
        data.usage.map((u) => [
          esc(date(u.created)),
          `${esc(u.provider)} · ${esc(u.model)}`,
          esc(u.status),
          Number(u.cost_usd).toFixed(6),
        ]),
      ),
    ) +
    `<p class="muted">Up to 300 recent observations per section. Retention is configurable. Billing reservations with uncertain outcomes remain charged conservatively.</p>`
  );
}
async function settings() {
  const [data, exceptions, devices] = await Promise.all([
    api("settings"),
    api("exceptions"),
    api("devices"),
  ]);
  return (
    card(
      "Configuration & privacy",
      `<p>Configure provider keys, model IDs, opt-in, prices, budgets and the daily schedule in <strong>Settings → Apps → Vision → Configuration</strong>, then restart Vision. Credentials are never returned here. Prices are user supplied in USD per million tokens; a zero rate blocks AI requests.</p><details><summary>Current configuration (secrets excluded)</summary><dl>${Object.entries(
        data,
      )
        .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
        .join(
          "",
        )}</dl></details><p class="muted">Budget failover needs its own opt-in. Costs are estimates at configured rates; enforce provider-side spending limits too. Anthropic/OpenAI process only opt-in evidence requests.</p>`,
    ) +
    card(
      "Expected offline behavior",
      `<p>Suppress availability incidents for a known exception. This changes only Vision's database. Reasons are redacted before storage.</p><form id="exception-form"><label>Entity<select name="entity_id" required>${devices.entities.map((e) => `<option value="${esc(e.entity_id)}">${esc(e.name)} (${esc(e.entity_id)})</option>`).join("")}</select></label><label>Reason<input name="reason" maxlength="300" required placeholder="For example, a battery device sleeps overnight"></label><label>Expires after hours<input name="hours" type="number" min="1" max="8760" value="24" required></label><button type="submit">Save exception</button></form>` +
        table(
          ["Entity", "Reason", "Expires", ""],
          exceptions.map((e) => [
            esc(e.entity_id),
            esc(e.reason),
            esc(date(e.expires)),
            `<button data-remove="${esc(e.entity_id)}">Remove</button>`,
          ]),
        ),
    )
  );
}
async function render() {
  const id = ++generation;
  const [page, encoded] = location.hash.slice(1).split("/");
  const active = pages.map((p) => p.toLowerCase()).includes(page)
    ? page
    : "overview";
  $("#title").textContent = pages.find((p) => p.toLowerCase() === active);
  document
    .querySelectorAll("nav a")
    .forEach((a) => a.classList.toggle("active", a.hash === "#" + active));
  try {
    const health = await api("health");
    if (id !== generation) return;
    if (health.configuration_error) notice.textContent = health.configuration_error;
    $("#connection").textContent =
      (health.connected ? "Connected" : "Disconnected") + " · Read only";
    const views = {
      overview,
      devices,
      automations: () =>
        automations(encoded ? decodeURIComponent(encoded) : null),
      issues,
      intelligence,
      history,
      settings,
    };
    const html = await views[active]();
    if (id !== generation) return;
    content.innerHTML = html;
    searchTable();
    bindAnalysis();
    const preview = $("#preview");
    if (preview)
      preview.addEventListener("click", async () => {
        try {
          const data = await api("intelligence/preview");
          $("#evidence-preview").innerHTML =
            `<h3>Exactly this bundle is transmitted</h3><pre>${esc(JSON.stringify(data.transmitted, null, 2))}</pre><p class="muted">Evidence mappings and credentials stay local.</p>`;
        } catch (e) {
          notice.textContent = e.message;
        }
      });
    const form = $("#exception-form");
    if (form)
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const fields = new FormData(form);
        try {
          await api("exceptions", {
            method: "POST",
            body: JSON.stringify({
              entity_id: fields.get("entity_id"),
              reason: fields.get("reason"),
              hours: Number(fields.get("hours")),
            }),
          });
          notice.textContent = "Exception saved in Vision.";
          render();
        } catch (e) {
          notice.textContent = e.message;
        }
      });
    document.querySelectorAll("[data-remove]").forEach((b) =>
      b.addEventListener("click", async () => {
        try {
          await api("exceptions/" + encodeURIComponent(b.dataset.remove), {
            method: "DELETE",
          });
          render();
        } catch (e) {
          notice.textContent = e.message;
        }
      }),
    );
  } catch (e) {
    if (id === generation) {
      notice.textContent = e.message;
      content.innerHTML = empty("Unable to load current observations.");
    }
  }
}
window.addEventListener("hashchange", () => {
  notice.textContent = "";
  render();
});
setInterval(() => {
  if (
    ["", "#overview", "#intelligence"].includes(location.hash) &&
    !document.querySelector("details[open]")
  )
    render();
}, 15000);
render();
