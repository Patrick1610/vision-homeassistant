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
const issueLink = (key, text) =>
  `<a href="#issues/${encodeURIComponent(key)}">${esc(text)}</a>`;
const autoLink = (entity, text = entity, runId = null) =>
  `<a href="#automations/${encodeURIComponent(entity)}${runId ? "?run_id=" + encodeURIComponent(runId) : ""}">${esc(text)}</a>`;
const list = (items) =>
  items.length
    ? `<ul>${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`
    : empty("None recorded.");
function caseCards(items) {
  return items.length
    ? items
        .map(
          (item) =>
            `<article class="case-row"><div>${badge(item.severity, item.severity)} ${badge(item.status)} ${badge(item.source)}</div><h3>${issueLink(item.key, item.title)}</h3><p class="evidence-text">${esc(item.summary)}</p><p><strong>Check:</strong> ${esc(item.manual_check)}</p>${item.detail.entity_id ? `<p>${item.detail.entity_id.startsWith("automation.") ? autoLink(item.detail.entity_id, item.detail.entity_id, item.detail.run_id) : `<a href="#devices/${encodeURIComponent(item.detail.entity_id)}">${esc(item.detail.entity_id)}</a>`}</p>` : ""}${item.related_case_keys?.length ? `<p>${item.related_case_keys.map((key) => issueLink(key, "Related source observation")).join(" · ")}</p>` : ""}<small>First observed ${esc(date(item.first_seen))} · Last observed ${esc(date(item.last_seen))}</small></article>`,
        )
        .join("")
    : empty("No cases require review in this selection.");
}
function deltaView(delta) {
  if (!delta) return empty("Structural comparison unavailable.");
  return `<p>${esc(delta.summary)}</p>${
    delta.items.length
      ? `<details><summary>Observed projection differences</summary>${table(
          ["Path", "Before", "After"],
          delta.items.map((item) => [
            esc(item.path),
            esc(item.before),
            esc(item.after),
          ]),
        )}${delta.truncated ? "<p>First 20 differences shown.</p>" : ""}</details>`
      : ""
  }`;
}
function nodeLink(key, present = true) {
  if (!present) return `${esc(key)} <small>(not in current inventory)</small>`;
  const [kind, ...parts] = key.split(":"),
    identifier = parts.join(":");
  if (
    kind === "automation" ||
    (kind === "entity" && identifier.startsWith("automation."))
  )
    return autoLink(identifier);
  if (kind === "entity")
    return `<a href="#devices/${encodeURIComponent(identifier)}">${esc(key)}</a>`;
  if (kind === "device" || kind === "integration")
    return `<a href="#devices/${encodeURIComponent(key)}">${esc(key)}</a>`;
  return esc(key);
}
function impactView(data) {
  if (!data) return empty("No retained dependency observations.");
  return (
    `<p class="muted">${esc(data.coverage)}</p>` +
    table(
      ["From", "Relation", "To", "Declared path"],
      data.relations.map((row) => [
        nodeLink(row.source, row.source_present),
        esc(row.relation),
        nodeLink(row.target, row.target_present),
        esc(row.path),
      ]),
    ) +
    (data.truncated ? `<p class="muted">First 100 relations shown.</p>` : "") +
    `<h3>Automations with declared dependencies</h3>` +
    table(
      ["Automation", "Relation", "Via"],
      (data.affected_automations || []).map((row) => [
        nodeLink(row.source, row.source_present),
        esc(row.relation),
        nodeLink(row.target, row.target_present),
      ]),
    ) +
    (data.affected_truncated || data.members_truncated
      ? `<p class="muted">Impact coverage is limited to 200 members and 100 declared automation relations.</p>`
      : "")
  );
}
function stepObservation(step) {
  if (!step) return "Not retained / execution unknown";
  const result = [];
  if (step.result != null) result.push("Condition result: " + step.result);
  if (step.wait_completed != null)
    result.push(step.wait_completed ? "Wait completed" : "Wait incomplete");
  if (step.timeout || step.wait_timed_out) result.push("Timeout observed");
  if (step.errors) result.push(step.errors + " error observations");
  if (step.done) result.push("Step completed");
  if (step.explicit_stop) result.push("Explicit stop observed");
  if (step.offset_seconds != null)
    result.push(
      "Started +" + duration(step.offset_seconds) + " from run start",
    );
  return result.join(" · ") || "Step observed; result not retained";
}
function runDigest(run) {
  return run.configuration_digest
    ? `<span>Run-bound configuration ${esc(run.configuration_digest.slice(0, 12))}</span><details><summary>Full retained configuration digest</summary><code>${esc(run.configuration_digest)}</code></details>`
    : "Run-bound configuration unknown";
}
function stepView(run) {
  if (!run) return empty("Select a retained run to inspect its steps.");
  const raw = run.evidence;
  const evidence =
    raw &&
    typeof raw === "object" &&
    Array.isArray(raw.steps) &&
    Array.isArray(raw.errors) &&
    raw.steps.every(
      (step) =>
        step && typeof step === "object" && typeof step.path === "string",
    ) &&
    raw.errors.every(
      (error) =>
        error &&
        typeof error === "object" &&
        typeof error.path === "string" &&
        typeof error.message === "string",
    ) &&
    raw.coverage &&
    typeof raw.coverage === "object" &&
    !Array.isArray(raw.coverage)
      ? raw
      : null;
  const nodes = new Map(
    (run.configuration?.nodes || []).map((node) => [node.path, node]),
  );
  const refs = (path) =>
    (run.configuration?.references || [])
      .filter((ref) => ref.path === path)
      .map((ref) => ref.id)
      .join(", ");
  return (
    `<p>${badge(run.outcome, run.outcome)} · Started ${esc(date(run.started))} · ${esc(run.start_source)}</p><div class="muted">${runDigest(run)}</div>` +
    (evidence
      ? `<p>${esc(evidence.step_count)} returned step observations · ${esc(evidence.error_count)} error observations${evidence.coverage.error_count_is_lower_bound ? " (lower bound)" : ""}${evidence.completed_with_errors ? " · Completed with step errors" : ""}</p><p class="muted">Step times are starts; they do not prove parallel completion order. ${evidence.coverage.details_compacted ? "Step details compacted under the storage budget." : ""}${evidence.coverage.abort_reason_unknown ? " Abort reason is unknown." : ""}</p>` +
        table(
          [
            "Path / iteration",
            "Declared logic",
            "Step start",
            "Result",
            "Wait / errors",
          ],
          evidence.steps.map((step) => [
            esc(step.path) + " / " + esc(step.iteration),
            esc(nodes.get(step.path)?.kind || "Not retained") +
              "<br>" +
              esc(refs(step.path)) +
              (nodes.get(step.path)?.predicate
                ? "<br>" + esc(JSON.stringify(nodes.get(step.path).predicate))
                : ""),
            esc(date(step.observed_at)),
            step.result == null ? "Not retained" : esc(step.result),
            esc(
              [
                step.wait_completed === false
                  ? "Wait incomplete"
                  : step.wait_completed
                    ? "Wait complete"
                    : "",
                step.wait_timed_out || step.timeout ? "Timeout observed" : "",
                step.errors ? step.errors + " errors" : "",
              ]
                .filter(Boolean)
                .join(" · "),
            ),
          ]),
        ) +
        evidence.errors
          .map(
            (error) =>
              `<article class="row"><strong>${esc(error?.kind || "Unknown error")} · ${esc(error?.path || "unknown")}</strong><p class="evidence-text">${esc(error?.message || "Error text unavailable")}</p></article>`,
          )
          .join("") +
        `<details><summary>Coverage</summary><pre>${esc(JSON.stringify(evidence.coverage, null, 2))}</pre></details>`
      : empty(
          "Retained step evidence is unavailable or has unknown coverage; step outcomes are unknown.",
        ))
  );
}
function overviewCases(items) {
  const concrete = items.filter(
    (item) => item.source !== "availability" && item.severity !== "info",
  );
  if (concrete.length) return concrete;
  const availability = items.filter((item) => item.source === "availability");
  return availability.length ? availability.slice(0, 3) : items.slice(0, 3);
}
async function overview() {
  const data = await api("overview"),
    health = data.health;
  const local = data.local;
  const visible = overviewCases(local.cases.items);
  return (
    card(
      "Investigate first",
      `<p class="muted">Local observations and checks, available with AI disabled. Source severity and execution errors take priority over availability volume.</p>${local.cases.rule_coverage?.truncated ? `<p class="callout">Local static checks are bounded: ${esc(local.cases.rule_coverage.retained)} retained, ${esc(local.cases.rule_coverage.omitted)} additional checks omitted. Coverage is incomplete.</p>` : ""}${caseCards(visible)}<p><a href="#issues">Review all ${esc(local.cases.total)} cases needing attention →</a></p>`,
    ) +
    `<p class="summary-strip">${esc(data.entities)} entities · ${esc(data.automations)} automations · ${esc(local.structural_changes_24h)} structural changes observed in 24 h</p>` +
    `<div class="split">${card("Availability", `<p><strong>${esc(local.availability_count)}</strong> active source observations; ${esc(data.unavailable)} are unexpected in the current inventory.</p><p>Expected, known and snoozed cases keep their source facts.</p><a href="#issues/?source=availability">Investigate availability →</a>`)}${card("Observation coverage", `<p>${badge(health.connected ? "Connected" : "Disconnected", health.connected ? "success" : "warning")}</p><p>Last sync ${esc(date(health.last_sync))}</p><p class="muted">Monitoring began ${esc(date(data.coverage_started))}. Last gap ${esc(date(data.last_gap))}. Gaps are unknown coverage.</p><details><summary>Read coverage and pending traces</summary><pre>${esc(JSON.stringify({ capabilities: health.capabilities, traces: health.trace_detail_coverage }, null, 2))}</pre></details>`)}</div>${card("Latest optional audit", findings(data.latest_audit))}`
  );
}
async function devices(route) {
  const data = await api("devices");
  if (route && /^(device|integration)%3A/i.test(route)) {
    const key = decodeURIComponent(route),
      [kind, ...parts] = key.split(":"),
      identifier = parts.join(":");
    const impact = await api(
      "dependencies?" + new URLSearchParams({ kind, identifier }),
    );
    return (
      `<p><a href="#devices">← Entity inventory</a></p>` +
      card(key, impactView(impact))
    );
  }
  if (route) {
    const entity = decodeURIComponent(route),
      item = data.entities.find((value) => value.entity_id === entity);
    if (!item) return empty("Entity not in current inventory.");
    const dossier = await api(
      "entities/" + encodeURIComponent(entity) + "/investigation",
    );
    return (
      `<p><a href="#devices">← Entity inventory</a></p>` +
      card(
        item.name,
        `<p>${esc(entity)} · ${badge(item.availability)}</p><p>Device ${esc(item.device_id)} · ${esc(item.outages.episodes)} observed offline segments · ${esc(duration(item.outages.seconds))} measured.</p><p>${item.expected_offline ? "Expected-offline attention exception is active; source state is preserved." : "No expected-offline exception."}</p>`,
      ) +
      card(
        "Local observations",
        dossier.cases
          .map((value) => `<p>${issueLink(value.key, value.title)}</p>`)
          .join("") || empty("No retained case for this entity."),
      ) +
      card("Affected automations and relations", impactView(dossier.impact))
    );
  }
  return (
    search("Find a device, entity or state…") +
    card(
      "Entities",
      table(
        ["Entity", "Availability", "Device", "Observed offline", "Exception"],
        data.entities.map((e) => [
          `${`<a href="#devices/${encodeURIComponent(e.entity_id)}">${esc(e.name)}</a>`}<br><small>${esc(e.entity_id)}</small>`,
          badge(
            e.availability,
            e.availability === "available" ? "success" : "warning",
          ),
          e.device_id ? nodeLink("device:" + e.device_id) : "—",
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
          `<a href="#devices/${encodeURIComponent("device:" + d.id)}">${esc(d.name_by_user || d.name || "Unnamed device")}</a>`,
          esc(d.manufacturer),
          esc(d.model),
          esc(d.id),
        ]),
      ),
    ) +
    `<p class="muted">Segments are bounded by observed transitions and connection gaps; they are not an exact count of physical outages. Disabled entities without a state are excluded from availability monitoring.</p>`
  );
}
async function automations(route) {
  if (!route) {
    const data = await api("automations");
    return (
      search("Find an automation…") +
      card(
        "Automation inventory",
        table(
          ["Automation", "Enabled", "Last triggered", "Retained outcomes"],
          data.map((item) => [
            autoLink(item.entity_id, item.name),
            badge(
              item.enabled == null ? "Not loaded" : item.enabled ? "Yes" : "No",
            ),
            esc(date(item.last_triggered)),
            item.stats
              .map((stat) => `${esc(stat.outcome)}: ${esc(stat.count)}`)
              .join("<br>") || "No retained runs",
          ]),
        ),
      ) +
      `<p class="muted">A trigger is not a completed run. Open an automation for local logic, step evidence, comparisons and impact.</p>`
    );
  }
  const [encodedEntity, query = ""] = route.split("?"),
    entity = decodeURIComponent(encodedEntity),
    params = new URLSearchParams(query);
  const data = await api(
    "investigation/" + encodeURIComponent(entity) + "?" + params,
  );
  const structure = data.structure;
  const selected = params.get("run_id") || "";
  const options = (chosen) =>
    `<option value="">Choose a run</option>` +
    data.runs
      .map(
        (run) =>
          `<option value="${esc(run.run_id)}" ${run.run_id === chosen ? "selected" : ""}>${esc(date(run.started))} · ${esc(run.outcome)} · ${esc(run.run_id)}</option>`,
      )
      .join("");
  return (
    `<p><a href="#automations">← All automations</a></p>` +
    card(
      data.name,
      `<p>${esc(entity)} · ${badge(data.enabled == null ? "Not loaded" : data.enabled ? "Enabled" : "Disabled")}</p><p class="muted">${esc(data.coverage)}</p>`,
    ) +
    card(
      "Retained execution comparison",
      `<form id="run-form" data-entity="${esc(entity)}"><label>Inspect run<select name="run_id" required>${options(selected)}</select></label><label>Compare with<select name="compare">${options(params.get("compare"))}</select></label><button type="submit">Inspect evidence</button></form><p>Each run is bound to its own configuration digest when available. Different or unknown digests limit comparison.</p>${
        data.comparison
          ? `<p class="callout">${esc(data.comparison.limitation)}${data.comparison.coverage_limited ? " Step coverage is incomplete or compacted; missing observations do not prove absence." : ""}</p>` +
            (data.comparison.comparable
              ? table(
                  [
                    "Step / iteration",
                    "First run observation",
                    "Compared run observation",
                  ],
                  data.comparison.differences.map((item) => [
                    esc(item.path) + " / " + esc(item.iteration),
                    esc(stepObservation(item.left)),
                    esc(stepObservation(item.right)),
                  ]),
                )
              : "")
          : ""
      }`,
    ) +
    (data.comparison
      ? `<div class="split">${card("First run", stepView(data.comparison.left))}${card("Compared run", stepView(data.comparison.right))}</div>`
      : card("Run steps and redacted errors", stepView(data.run))) +
    card(
      data.structure_coverage.current_configuration_available
        ? "Current observed automation logic"
        : "Historical trace logic · current configuration unavailable",
      structure
        ? `<p>Retained mode ${badge(structure.mode)}${structure.max_runs ? " · maximum " + esc(structure.max_runs) : ""}</p><p class="muted">${esc(data.configuration_limit)}</p>` +
            table(
              ["Path", "Step", "Safe operands", "Declared references"],
              structure.nodes.map((node) => [
                esc(node.path),
                esc(node.kind) +
                  (node.service ? " · " + esc(node.service) : ""),
                esc(
                  JSON.stringify(
                    node.predicate ||
                      node.timeout ||
                      (node.delay_seconds != null
                        ? { delay_seconds: node.delay_seconds }
                        : {}),
                  ),
                ) +
                  (node.omitted_predicates
                    ? `<br><small>Omitted: ${esc(node.omitted_predicates.join(", "))}</small>`
                    : ""),
                esc(
                  structure.references
                    .filter((ref) => ref.path === node.path)
                    .map((ref) => ref.kind + ":" + ref.id)
                    .join(", "),
                ),
              ]),
            ) +
            `<details><summary>Structure coverage</summary><pre>${esc(JSON.stringify(data.structure_coverage, null, 2))}</pre></details>`
        : empty(
            "No structural configuration available; predicates and targets remain unknown.",
          ),
    ) +
    card(
      "Local findings",
      data.local_cases.length
        ? data.local_cases
            .map(
              (item) =>
                `<p>${issueLink(item.key, item.title)} ${badge(item.active ? "Source active" : "Source inactive")}</p>`,
            )
            .join("")
        : empty("No retained local cases for this automation."),
    ) +
    card("Dependency impact", impactView(data.impact)) +
    card(
      "Observed configuration changes",
      table(
        ["Observed", "Kind / source", "Before → after"],
        data.configuration_changes.map((change) => [
          esc(date(change.observed_at)),
          esc(change.kind + " · " + change.source),
          deltaView(change.delta) +
            `<details><summary>Configuration digests</summary><code>${esc(change.before_digest || "No baseline")} → ${esc(change.after_digest)}</code></details>`,
        ]),
      ),
    )
  );
}
async function issues(route) {
  if (route && !route.startsWith("?")) {
    const data = await api(
        "cases/" + encodeURIComponent(decodeURIComponent(route)),
      ),
      item = data.case;
    return (
      `<p><a href="#issues">← All cases</a></p>` +
      card(
        item.title,
        `<p>${badge(item.severity, item.severity)} ${badge(item.status)} ${badge(item.source_active ? "Source active" : "Source inactive")}</p><p>First observed ${esc(date(item.first_seen))} · Last observed ${esc(date(item.last_seen))}</p><p>${esc(data.recurrence.meaning)} Reported: ${esc(data.recurrence.reported)}${data.recurrence.retained_runs != null ? " · Retained runs: " + esc(data.recurrence.retained_runs) + " · Runs with error observations: " + esc(data.recurrence.retained_error_runs) : ""}</p>${data.affected.map((entity) => (entity.startsWith("automation.") ? autoLink(entity, entity, data.run?.run_id) : `<a href="#devices/${encodeURIComponent(entity)}">${esc(entity)}</a>`)).join(" · ")}`,
      ) +
      `<div class="split">${card("Observed facts", list(data.facts))}${card("Unknowns and hypotheses", list(data.unknowns) + list(data.hypotheses))}</div>` +
      card("Manual checks", list(data.manual_checks)) +
      card(
        "Local attention status",
        `<p>This changes Vision's attention queue. The underlying observation and its original dates stay intact.</p><form id="case-status-form" data-key="${esc(item.key)}"><label>Status<select name="status">${["review", "known", "expected", "snoozed"].map((status) => `<option ${item.local_status === status ? "selected" : ""}>${status}</option>`).join("")}</select></label><label>Note<input name="note" maxlength="300" value="${esc(item.note || "")}"></label><label>Snooze hours<input name="hours" type="number" min="1" max="8760" value="24" required></label><button type="submit">Save local status</button></form>${item.expires ? `<p>Attention resumes ${esc(date(item.expires))}.</p>` : ""}`,
      ) +
      card(
        "Observation timeline",
        table(
          ["Time", "Observation", "Provenance"],
          data.timeline.map((event) => [
            esc(date(event.at)),
            esc(event.kind + " · " + event.summary) +
              (event.run_id && data.affected[0]?.startsWith("automation.")
                ? `<br><a href="#automations/${encodeURIComponent(data.affected[0])}?run_id=${encodeURIComponent(event.run_id)}">Inspect this run</a>`
                : ""),
            esc(event.source) +
              (event.uncertain ? " · Gap / uncertain boundary" : ""),
          ]),
        ) +
          `<p class="muted">Last observation gap ${esc(date(data.last_observation_gap))}. Unknown run times cannot establish ordering.</p>`,
      ) +
      (data.run ? card("Linked execution evidence", stepView(data.run)) : "") +
      card("Affected relations", impactView(data.impact)) +
      `<details><summary>Retained redacted source detail</summary><pre>${esc(JSON.stringify(item.detail, null, 2))}</pre></details>`
    );
  }
  const params = new URLSearchParams((route || "").replace(/^\?/, ""));
  const data = await api("cases?" + params);
  const select = (name, values) =>
    `<label>${esc(name)}<select name="${esc(name)}">${values.map((value) => `<option ${value === (params.get(name) || (name === "status" ? "attention" : "all")) ? "selected" : ""}>${esc(value)}</option>`).join("")}</select></label>`;
  const pageLink = (page, text) => {
    const next = new URLSearchParams(params);
    next.set("page", page);
    return `<a class="button" href="#issues/?${next}">${esc(text)}</a>`;
  };
  return card(
    "Cases requiring investigation",
    `<form id="case-filter"><label>Search<input name="q" maxlength="200" value="${esc(params.get("q") || "")}"></label>${select("status", ["attention", "all", "known", "expected", "snoozed", "resolved", "limited"])}${select("source", ["all", "automation", "automation_step", "repair", "log", "static", "availability"])}<button type="submit">Apply filters</button></form><p>${esc(data.total)} matching cases · Page ${esc(data.page)}</p>${caseCards(data.items)}<div class="toolbar">${data.page > 1 ? pageLink(data.page - 1, "Previous") : ""}${data.has_more ? pageLink(data.page + 1, "Next") : ""}</div>`,
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
async function history(route) {
  const [kind = "runs", query = ""] = (route || "runs").split("?"),
    params = new URLSearchParams(query);
  params.set("kind", kind);
  const data = await api("history/page?" + params);
  const rows = data.items.map((item) => {
    if (kind === "runs")
      return [
        esc(date(item.started)),
        autoLink(item.entity_id),
        badge(item.outcome, item.outcome),
        esc(item.start_source),
        `<a href="#automations/${encodeURIComponent(item.entity_id)}?run_id=${encodeURIComponent(item.run_id)}">Inspect run</a>`,
      ];
    if (kind === "availability")
      return [
        esc(date(item.started)),
        esc(item.entity_id),
        esc(item.state),
        esc(date(item.ended)),
        item.uncertain ? "Gap / uncertain" : "Observed",
      ];
    if (kind === "issues")
      return [
        esc(date(item.last_seen)),
        issueLink(item.key, item.title),
        esc(item.source),
        esc(item.severity),
        esc(item.occurrences),
      ];
    if (kind === "changes")
      return [
        esc(date(item.observed_at)),
        autoLink(item.entity_id),
        esc(item.kind),
        esc(item.source),
        deltaView(item.delta),
      ];
    if (kind === "analyses")
      return [
        esc(date(item.created)),
        esc(item.kind),
        esc(item.provider),
        esc(item.model),
        findings(item),
      ];
    return [
      esc(date(item.created)),
      esc(item.provider),
      esc(item.model),
      esc(item.status),
      esc(Number(item.cost_usd).toFixed(6)),
    ];
  });
  const headers = {
    runs: ["Started", "Automation", "Outcome", "Time source", "Evidence"],
    availability: ["Started", "Entity", "State", "Ended", "Coverage"],
    issues: ["Observed", "Case", "Source", "Severity", "Reported count"],
    changes: ["Observed", "Automation", "Kind", "Source", "Evidence"],
    usage: ["Time", "Provider", "Model", "Status", "Estimated USD"],
    analyses: ["Time", "Task", "Provider", "Model", "Retained findings"],
  }[kind];
  const next = new URLSearchParams(params);
  if (data.next_cursor) next.set("cursor", data.next_cursor);
  return card(
    "Search retained history",
    `<form id="history-filter"><label>Section<select name="kind">${["runs", "availability", "issues", "changes", "usage", "analyses"].map((value) => `<option ${value === kind ? "selected" : ""}>${value}</option>`).join("")}</select></label><label>Search<input name="q" maxlength="200" value="${esc(params.get("q") || "")}"></label><label>Entity (runs / availability / changes)<input name="entity" maxlength="200" value="${esc(params.get("entity") || "")}"></label><label>Outcome / state / source<input name="outcome" maxlength="100" value="${esc(params.get("outcome") || "")}"></label><label>Day (UTC)<input name="day" type="date" value="${esc(params.get("day") || "")}"></label><button type="submit">Search history</button></form><p class="muted">${esc(data.coverage)} Structural baselines record observation time, not HA edit time. Costs include conservative uncertain reservations.</p>${table(headers, rows)}${data.next_cursor ? `<a class="button" href="#history/${kind}?${next}">Next observations →</a>` : ""}<p><a href="#history/${kind}">Start of this section</a></p>`,
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
      `<p>Reduce attention for expected availability observations while preserving source facts. This changes only Vision's database. Reasons are redacted before storage.</p><form id="exception-form"><label>Entity<select name="entity_id" required>${devices.entities.map((e) => `<option value="${esc(e.entity_id)}">${esc(e.name)} (${esc(e.entity_id)})</option>`).join("")}</select></label><label>Reason<input name="reason" maxlength="300" required placeholder="For example, a battery device sleeps overnight"></label><label>Expires after hours<input name="hours" type="number" min="1" max="8760" value="24" required></label><button type="submit">Save exception</button></form>` +
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
    if (health.configuration_error)
      notice.textContent = health.configuration_error;
    $("#connection").textContent =
      (health.connected ? "Connected" : "Disconnected") + " · Read only";
    const views = {
      overview,
      devices: () => devices(encoded || null),
      automations: () => automations(encoded || null),
      issues: () => issues(encoded || null),
      intelligence,
      history: () => history(encoded || null),
      settings,
    };
    const html = await views[active]();
    if (id !== generation) return;
    content.innerHTML = html;
    searchTable();
    bindAnalysis();
    const localStatus = $("#case-status-form");
    if (localStatus)
      localStatus.addEventListener("submit", async (event) => {
        event.preventDefault();
        const fields = new FormData(localStatus);
        try {
          await api(
            "cases/" + encodeURIComponent(localStatus.dataset.key) + "/status",
            {
              method: "POST",
              body: JSON.stringify({
                status: fields.get("status"),
                note: fields.get("note"),
                hours: Number(fields.get("hours")),
              }),
            },
          );
          notice.textContent =
            "Local attention status saved; source observation preserved.";
          render();
        } catch (error) {
          notice.textContent = error.message;
        }
      });
    for (const [selector, page] of [
      ["#case-filter", "issues"],
      ["#history-filter", "history"],
    ]) {
      const filter = $(selector);
      if (filter)
        filter.addEventListener("submit", (event) => {
          event.preventDefault();
          const fields = new FormData(filter),
            query = new URLSearchParams();
          for (const [key, value] of fields)
            if (value && key !== "kind") query.set(key, value);
          location.hash =
            "#" +
            page +
            "/" +
            (page === "history" ? fields.get("kind") : "") +
            "?" +
            query;
        });
    }
    const runForm = $("#run-form");
    if (runForm)
      runForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const fields = new FormData(runForm),
          query = new URLSearchParams();
        for (const [key, value] of fields) if (value) query.set(key, value);
        location.hash =
          "#automations/" +
          encodeURIComponent(runForm.dataset.entity) +
          "?" +
          query;
      });
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
