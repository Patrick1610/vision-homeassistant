"use strict";
const pages = [
  "Today",
  "Problems",
  "Devices",
  "History",
  "Settings",
  "Overview",
  "Automations",
  "Issues",
  "Intelligence",
  "Intake",
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
pages.filter(p=>p!=="Intake").forEach((p,index) => {
  const a = document.createElement("a");
  a.href = "#" + p.toLowerCase();
  a.dataset.label = p;
  a.textContent = window.VisionHome?.label(p) || p;
  $(index<5?"#nav":"#expert-links").append(a);
});
window.VisionHome?.applyLocale();
let generation = 0,
  lastRefreshFailure = "",
  lastRenderedRoute = null;
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
const plain = (value) => String(value ?? "");
const short = (value, count = 180) => {
  const chars = Array.from(plain(value));
  return chars.length > count
    ? chars.slice(0, count).join("").trimEnd() + "…"
    : chars.join("");
};
function prose(value, count = 220, label = "Full text") {
  const text = plain(value);
  return `<p>${esc(short(text, count))}</p>${Array.from(text).length > count ? `<details><summary>${esc(label)}</summary><p class="evidence-text">${esc(text)}</p></details>` : ""}`;
}
function unknownView(items, heading = "What remains unknown") {
  const rows = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!rows.length) return "";
  const expanded =
    rows.length > 2 ||
    rows.some((item) => Array.from(plain(item)).length > 180);
  return `<aside class="coverage-note"><strong>${esc(heading)}</strong>${list(rows.slice(0, 2).map((item) => short(item, 180)))}${expanded ? `<details><summary>All limitations</summary>${list(rows)}</details>` : ""}</aside>`;
}
function externalSource(source) {
  try {
    const url = new URL(source.url);
    if (url.protocol !== "https:" || url.username || url.password || !["github.com", "www.home-assistant.io", "contributors.home-assistant.io"].includes(url.hostname)) return esc(source.title || "Source");
    return `<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${esc(source.title || "Source")}</a>`;
  } catch { return esc(source.title || "Unknown source"); }
}
function sourceLinks(refs, research) {
  return (refs || []).map(ref => {
    const source = (research?.sources || []).find(s => (s.excerpts || []).some(e => e.ref === ref));
    if (!source) return esc(ref);
    return externalSource(source);
  }).join(" · ");
}
function researchView(research) {
  if (!research) return "";
  return `<details class="research-sources"><summary>Public sources & version limits (${(research.sources || []).length})</summary><p>Current authenticated Core: ${esc(research.technical_context?.core_version || "Unknown")}. Historical run version remains unknown. Public reports and closed issues do not establish a local cause or installed fix.</p>${(research.sources || []).map(s => `<article><strong>${esc(s.kind)}</strong> · ${externalSource(s)}<small>Retrieved ${esc(date(s.retrieved_at))} · ${esc(s.applicability)}${s.thread_complete === false ? " · incomplete comment thread" : ""}</small><details><summary>Retained passages, content hash & provenance</summary><pre>${esc(JSON.stringify(s,null,2))}</pre></details></article>`).join("")}${list((research.gaps || []).map(g => `${g.adapter}: ${g.reason.replaceAll("_", " ")}${g.host ? ` · ${g.host} until ${date(g.until)}` : ""}`))}<details><summary>Exact public query plan & coverage limits</summary><pre>${esc(JSON.stringify({plan:research.query_plan,coverage:research.coverage},null,2))}</pre></details></details>`;
}
function findingCard(item, index, research) {
  const plan = item.manual_plan;
  const manual = plan ? `${plan.prerequisites?.length ? `<details><summary>Before starting</summary>${list(plan.prerequisites)}</details>` : ""}<ol class="manual-steps">${plan.steps.map(step => `<li>${prose(step.instruction,160,"Full manual step")}<small>${sourceLinks(step.source_refs,research)}</small></li>`).join("")}</ol>` : `<p>${esc(short(item.next_step,140))}</p>`;
  return `<article class="finding-card"><div class="card-topline"><span class="step-number">Proposal ${index + 1}</span>${badge(item.severity || "info", item.severity || "info")}</div><h3>${esc(short(item.finding, 120))}</h3><div class="plan-block"><span class="overline">MANUAL SOLUTION / CHECK</span>${manual}</div><div class="validation-block"><span class="overline">VALIDATION</span><p>${esc(short(item.validation, 110))}</p></div><p class="uncertainty"><strong>Uncertainty:</strong> ${esc(short(item.uncertainty, 100))}</p>${item.unknowns?.length ? `<p class="muted">Missing evidence: ${esc(short(item.unknowns[0], 90))}</p>` : ""}<details class="finding-detail"><summary>Full proposal, evidence & alternatives</summary><dl><dt>Proposed explanation</dt><dd>${esc(item.finding)}</dd><dt>Manual solution / check</dt><dd>${esc(item.next_step)}</dd><dt>Validation method</dt><dd>${esc(item.validation)}</dd><dt>Supporting references</dt><dd>${esc((item.evidence || []).join(", "))}</dd><dt>Counterevidence</dt><dd>${esc((item.counter_evidence || []).join(", ") || "None retained")}</dd><dt>Confidence</dt><dd>${esc(item.confidence || "Unknown")}</dd><dt>Uncertainty</dt><dd>${esc(item.uncertainty)}</dd></dl>${list(item.unknowns || [])}</details></article>`;
}
function findings(analysis) {
  if (!analysis)
    return empty(
      "No retained AI investigation. Local evidence is available without AI.",
    );
  const result = parse(analysis.result) || {},
    entries = Array.isArray(result.diagnoses) ? result.diagnoses : [],
    research = parse(analysis.evidence)?.research;
  const cards = (rows, offset = 0) =>
    `<div class="finding-grid">${rows.map((item, index) => findingCard(item, index + offset, research)).join("")}</div>`;
  return (
    `<div class="analysis-intro"><span class="overline">AI PROPOSALS · MANUAL VALIDATION NEEDED</span>${prose(result.summary, 180, "Full investigation summary")}<small>${esc(analysis.provider)} · ${esc(analysis.model)} · ${esc(date(analysis.created))}</small></div>` +
    (entries.length
      ? cards(entries.slice(0, 3)) +
        (entries.length > 3
          ? `<details class="more-findings"><summary>${entries.length - 3} more retained proposals</summary>${cards(entries.slice(3), 3)}</details>`
          : "")
      : empty(
          "No supported finding returned. Review the unknowns before drawing a conclusion.",
        )) +
    researchView(research) +
    unknownView(result.unknowns) +
    (result.requested_sections?.length
      ? `<details><summary>Suggested local evidence for a reviewed follow-up</summary><p>${esc(result.requested_sections.join(", "))}. Nothing is fetched automatically.</p></details>`
      : "")
  );
}

const investigationLink = (
  kind,
  target = null,
  run = null,
  compare = null,
  text = "Preview focused AI investigation",
  targetType = "entity",
) => {
  const params = new URLSearchParams({ task: kind });
  if (target) params.set("target", target);
  if (targetType === "device") params.set("target_type", "device");
  if (run) params.set("run_id", run);
  if (compare) params.set("compare", compare);
  return `<a class="button" href="#intelligence/?${params}">${esc(text)}</a>`;
};
function investigationFocus(data) {
  const item = data.case,
    errors = data.run?.evidence?.errors || [];
  const focus = (kind, evidence = null) => ({
    kind,
    path:
      typeof evidence?.path === "string" &&
      evidence.path &&
      evidence.path !== "unknown"
        ? evidence.path
        : null,
  });
  if (item.source === "availability") return focus("availability");
  if (item.detail?.rule === "missing_target") return focus("missing_target");
  if (item.detail?.rule === "mode_conflict" || data.run?.outcome === "blocked")
    return focus("mode_conflict");
  const template = errors.find((error) => error.kind === "template_error");
  if (template) return focus("template_error", template);
  const communication = errors.find(
    (error) =>
      error.kind !== "template_error" &&
      /did not respond|failed to send|communication (?:error|failed|failure|timeout)|no response|device.{0,30}timed? out/i.test(
        error.message || "",
      ),
  );
  if (communication) return focus("device_communication", communication);
  const waitPaths = new Set(
    (data.run?.configuration?.nodes || [])
      .filter((node) =>
        ["wait_template", "wait_for_trigger"].includes(node.kind),
      )
      .map((node) => node.path),
  );
  const timeout =
    errors.find(
      (error) => error.kind === "timeout" && waitPaths.has(error.path),
    ) ||
    (data.run?.evidence?.steps || []).find(
      (step) => step.wait_timed_out || step.timeout,
    );
  if (timeout) return focus("timeout", timeout);
  // False branch observations alone cannot identify the condition that stopped a
  // whole run. Do not borrow a generic case/error path for that instruction.
  if (data.run?.outcome === "condition_stopped") return focus("condition_stop");
  return focus("incident");
}
function suggestedTask(data) {
  return investigationFocus(data).kind;
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
    ? `<details class="structure-digest"><summary>Run's retained structure · ${esc(run.configuration_digest.slice(0, 10))}</summary><code>${esc(run.configuration_digest)}</code><p>Digest of the safe structural projection. Raw templates, action payloads and omitted predicates are outside this comparison.</p></details>`
    : `<p class="muted">Run-bound structure is unknown.</p>`;
}
function runEvidence(run) {
  const value = run?.evidence;
  return value &&
    Array.isArray(value.steps) &&
    Array.isArray(value.errors) &&
    value.coverage &&
    typeof value.coverage === "object" &&
    !Array.isArray(value.coverage) &&
    value.steps.every((item) => item && typeof item.path === "string") &&
    value.errors.every(
      (item) =>
        item &&
        typeof item.path === "string" &&
        typeof item.message === "string",
    )
    ? value
    : null;
}
function startLabel(step) {
  if (
    typeof step.offset_seconds === "number" &&
    Number.isFinite(step.offset_seconds)
  )
    return (
      "+" +
      step.offset_seconds.toLocaleString(undefined, {
        maximumFractionDigits: 3,
      }) +
      " s"
    );
  return step.observed_at ? date(step.observed_at) : "Start unknown";
}
function stepView(run) {
  if (!run) return empty("Choose a retained run to inspect its evidence.");
  const evidence = runEvidence(run),
    completedErrors = evidence?.completed_with_errors;
  const outcome =
    completedErrors && run.outcome === "succeeded"
      ? "Succeeded with step errors"
      : run.outcome;
  const nodes = new Map(
    (run.configuration?.nodes || []).map((node) => [node.path, node]),
  );
  const limitations = [];
  if (!evidence)
    limitations.push(
      run.evidence_unknown_reason ||
        "Step evidence is unavailable or has unknown coverage.",
    );
  if (!["ha_trace", "event"].includes(run.start_source))
    limitations.push(
      "Run start is unverified. Its position in history is uncertain.",
    );
  if (evidence?.coverage.error_count_is_lower_bound)
    limitations.push(
      "Coverage is incomplete. Counts are lower bounds; omitted steps cannot be called error-free.",
    );
  if (evidence?.coverage.details_compacted)
    limitations.push("Step details were compacted under the storage budget.");
  if (evidence?.coverage.abort_reason_unknown)
    limitations.push(
      "The abort cause is unknown; parallel step starts cannot establish completion order.",
    );
  const ordered = (evidence?.steps || [])
    .slice()
    .sort(
      (a, b) =>
        (a.observed_at == null) - (b.observed_at == null) ||
        (a.observed_at || 0) - (b.observed_at || 0) ||
        a.path.localeCompare(b.path) ||
        (a.iteration || 0) - (b.iteration || 0),
    );
  const referenceLink = (ref) =>
    ref.kind === "entity"
      ? nodeLink("entity:" + ref.id)
      : esc(ref.kind + ":" + ref.id);
  const observations = (items) =>
    `<ol class="trace-timeline">${items
      .map((step) => {
        const node = nodes.get(step.path),
          errors = evidence.errors.filter(
            (error) =>
              error.path === step.path && error.iteration === step.iteration,
          );
        const kind = node?.kind || "Declared logic not retained";
        const refs = (run.configuration?.references || []).filter(
          (ref) => ref.path === step.path,
        );
        return `<li class="trace-step ${step.errors || errors.length ? "has-error" : step.timeout || step.wait_timed_out ? "has-warning" : ""}"><div class="trace-clock">${esc(startLabel(step))}</div><div class="trace-body"><strong>${esc(kind.replaceAll("_", " "))}</strong><p>${esc(stepObservation({ ...step, offset_seconds: null }))}</p><small class="trace-path">${esc(step.path)} · observation ${esc(step.iteration)}</small>${
          refs.length
            ? `<div class="affected-links">${refs
                .slice(0, 4)
                .map(referenceLink)
                .join(
                  " · ",
                )}${refs.length > 4 ? `<details><summary>${refs.length - 4} more declared references</summary><div class="affected-links">${refs.slice(4).map(referenceLink).join(" · ")}</div></details>` : ""}</div>`
            : ""
        }${
          errors.length
            ? errors
                .slice(0, 1)
                .map(
                  (error) =>
                    `<div class="error-excerpt">${prose(error.message, 180, "Full redacted error text")}</div>`,
                )
                .join("")
            : ""
        }</div></li>`;
      })
      .join("")}</ol>`;
  return (
    `<div class="run-summary">${badge(outcome, completedErrors ? "warning" : run.outcome)}<span>Run start ${esc(date(run.started))}</span>${typeof evidence?.duration_seconds === "number" && Number.isFinite(evidence.duration_seconds) && evidence.duration_seconds >= 0 ? `<span>Recorded duration ${esc(duration(evidence.duration_seconds))}</span>` : ""}</div>${unknownView(limitations, "Execution coverage")}${runDigest(run)}` +
    (evidence
      ? `<p class="trace-caption">${esc(evidence.step_count)} step observations · ${esc(evidence.error_count)} error observations${evidence.coverage.error_count_is_lower_bound ? " or more" : ""}. Times below are step starts.</p>${observations(ordered.slice(0, 6))}${ordered.length > 6 ? `<details><summary>${ordered.length - 6} more retained step starts</summary>${observations(ordered.slice(6))}</details>` : ""}${!ordered.length ? empty("No per-step records retained; execution details remain unknown.") : ""}<details><summary>All retained errors & coverage</summary>${evidence.errors.map((error) => `<article class="row"><strong>${esc(error.kind || "Unknown error")} · ${esc(error.path)}</strong><p class="evidence-text">${esc(error.message)}</p></article>`).join("")}<pre>${esc(JSON.stringify(evidence.coverage, null, 2))}</pre></details>`
      : "")
  );
}

function overviewCases(items, availability = null) {
  const grouped = [],
    seen = new Map();
  const availabilitySample = items.filter(
    (item) => item.source === "availability",
  );
  for (const item of items) {
    if (item.source === "availability") continue;
    const detail = item.detail || {},
      key =
        detail.entity_id && detail.run_id != null
          ? JSON.stringify([detail.entity_id, String(detail.run_id)])
          : item.key;
    const related = Array.isArray(item.related_case_keys)
      ? item.related_case_keys
      : [];
    if (seen.has(key)) {
      const first = seen.get(key);
      first.related_case_keys = [
        ...new Set([...first.related_case_keys, item.key, ...related]),
      ].filter((value) => value !== first.key);
      continue;
    }
    const entry = {
      ...item,
      related_case_keys: [...new Set(related)].filter(
        (value) => value !== item.key,
      ),
      href: "#issues/" + encodeURIComponent(item.key),
    };
    seen.set(key, entry);
    grouped.push(entry);
  }
  if (availability?.total || availabilitySample.length) {
    const first = availability?.items?.[0] || availabilitySample[0] || {};
    const count = availability?.total > 0 ? availability.total : null;
    grouped.push({
      key: "availability-group",
      source: "availability",
      severity: first.severity || "warning",
      priority: first.priority ?? 6,
      title: count
        ? count + " entities need availability review"
        : "Availability observations need review",
      status: "review",
      detail: {},
      summary: count
        ? "Retained unavailable or unknown observations. A shared cause has not been established."
        : "Availability observations are present in the priority sample; the full attention count is unknown or changed between reads.",
      manual_check:
        "Start with one affected entity. Check expected sleep, power, connectivity and observation gaps.",
      href: "#issues/?source=availability&status=attention",
      group_count: count,
    });
  }
  return grouped
    .sort((a, b) => (a.priority ?? 8) - (b.priority ?? 8))
    .slice(0, 3);
}

function priorityCards(items, incomplete = false) {
  if (!items.length && incomplete)
    return `<div class="calm-state"><span class="calm-mark" aria-hidden="true">…</span><div><h3>Priority coverage is incomplete</h3><p>Supporting observations could not be loaded. No complete absence of issues is established.</p><a href="#issues">Review retained attention cases →</a></div></div>`;
  if (!items.length)
    return `<div class="calm-state"><span class="calm-mark" aria-hidden="true">✓</span><div><h3>No cases in the attention queue</h3><p>Keep an eye on fresh observations, coverage and the retained history below.</p><a href="#history">Open observation history →</a></div></div>`;
  return `<div class="priority-grid">${items.map((item, index) => `<article class="priority-card ${index === 0 ? "featured" : ""}" data-priority-key="${esc(item.key)}"><div class="card-topline">${badge(item.severity, item.severity)}<span class="source-label">${esc((item.source || "unknown").replaceAll("_", " "))}</span></div><h3>${esc(short(item.title, 95))}</h3>${Array.from(plain(item.title)).length > 95 ? `<details><summary>Full problem title</summary><p>${esc(item.title)}</p></details>` : ""}${prose(item.summary, 160, "Full observed summary")}<div class="next-check"><span class="overline">NEXT MANUAL CHECK</span>${prose(item.manual_check, 150, "Full manual check")}</div>${item.detail?.entity_id ? `<small class="affected-id">${esc(short(item.detail.entity_id, 85))}</small>` : ""}${item.related_case_keys?.length ? `<details class="related-cases"><summary>${item.related_case_keys.length} related source observations</summary>${item.related_case_keys.map((key) => `<p>${issueLink(key, key)}</p>`).join("")}</details>` : ""}<a href="${esc(item.href)}" aria-label="${esc((index === 0 ? "Open investigation: " : "View evidence: ") + item.title)}" class="${index === 0 ? "button primary" : "quiet-link"}" ${index === 0 ? 'data-primary-investigation="true"' : ""}>${index === 0 ? "Open investigation" : "View evidence"}<span aria-hidden="true"> ↗</span></a></article>`).join("")}</div>`;
}
function latestAuditSummary(audit) {
  if (!audit)
    return `<p class="muted">No retained AI audit. Local investigation works without AI.</p>`;
  const result = parse(audit.result) || {},
    first = result.diagnoses?.[0];
  return `<span class="overline">OPTIONAL AI PROPOSALS</span>${prose(result.summary, 180, "Complete audit summary")}${first?.next_step ? `<p><strong>Proposed check:</strong> ${esc(short(first.next_step, 150))}</p>` : ""}<a href="#intelligence/?analysis=${encodeURIComponent(audit.id)}">Review proposals and validation →</a><small class="block">${esc(date(audit.created))} · Requires manual validation</small>`;
}
const number = (value, digits = 1) =>
  Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : "Unknown";
function deviceDuration(hours) {
  if (!Number.isFinite(hours)) return "Unknown device-hours";
  if (hours > 0 && hours < 1 / 60)
    return hours * 3600 < 0.1
      ? "less than 0.1 device-second"
      : number(hours * 3600) + " device-seconds";
  if (hours > 0 && hours < 0.1) return number(hours * 60) + " device-minutes";
  return number(hours) + " device-hours";
}
const coverageLabel = (fraction) => Number.isFinite(fraction)
  ? Math.round(fraction * 100) + "%" : "Unknown";
function deviceStorageView(storage) {
  if (!storage) return "";
  const summary = `${number(storage.records, 0)} / ${number(storage.row_limit, 0)} intervals · ${number(storage.bytes / 1048576)} / ${number(storage.encoded_byte_limit / 1048576)} MiB encoded`,
    eligibility = Number.isFinite(storage.earliest_retention_eligible_at)
      ? `Earliest ordinary-retention eligibility after ${date(storage.earliest_retention_eligible_at)} (${storage.retention_days} days). This is not a guaranteed resumption time; sufficient complete-cohort headroom is still required.`
      : "Ordinary-retention eligibility is unknown until a cached snapshot identifies an eligible closed interval; no resumption time is promised.";
  return `${storage.blocked ? `<p class="coverage-note">Device-history capacity reached: ${esc(summary)}. Existing history remains preserved. Uncaptured time and new worsening cannot be proved while history capture is blocked. Current evidence remains inspectable. ${esc(eligibility)}</p>` : ""}<details class="history-capacity"><summary>Device-history capacity</summary><p>${esc(summary)}.</p><p>${number(storage.remaining_rows, 0)} rows and ${number(storage.remaining_encoded_bytes / 1048576)} MiB encoded headroom. Encoded fields exclude SQLite/index/WAL overhead; this is not a file-size limit.</p><p>${esc(eligibility)}</p><p>Eligibility snapshot ${esc(date(storage.retention_estimate_as_of))}. Configured retention only; history is not evicted to make room.</p></details>`;
}
function deviceChart(data, locale = null) {
  const nl = locale === "nl";
  const label = {persistent:nl?"Aanhoudend / basis":"Persistent / baseline",new:nl?"Nieuwe waargenomen overgangen":"New observed transitions",expected:nl?"Verwacht":"Expected"};
  const points = data.points || [],
    width = 640,
    height = 140;
  const max = Math.max(
    2,
    2 *
      Math.ceil(
        Math.max(
          0,
          ...points.map(
            (p) => (p.persistent || 0) + (p.new || 0) + (p.expected || 0),
          ),
        ) / 2,
      ),
  );
  const bar = width / Math.max(1, points.length);
  const bars = points
    .map((p, i) => {
      let y = height;
      const stacks = ["persistent", "new", "expected"]
        .map((kind) => {
          const value = p[kind];
          if (value == null) return "";
          const h = (value / max) * height;
          y -= h;
          return `<rect class="series-${kind}" x="${i * bar + 1}" y="${y}" width="${Math.max(1, bar - 2)}" height="${h}"><title>${esc(label[kind])}: ${esc(value)} ${nl?"apparaten":"devices"}</title></rect>`;
        })
        .join("");
      return `${p.coverage < 1 || p.observed === 0 || p.observed === null || p.selection_limited || p.persistent == null ? `<rect class="chart-gap" x="${i * bar}" y="0" width="${bar}" height="${height}"><title>${esc(date(p.start))}: ${coverageLabel(p.coverage)} ${nl?"meetdekking; ontbrekende leden of weggelaten gegevens blijven onbekend":"monitoring coverage; missing membership or omitted evidence remains unknown"}</title></rect>` : ""}${stacks}`;
    })
    .join("");
  const ticks = [
    data.start,
    data.start + (data.end - data.start) / 3,
    data.start + (2 * (data.end - data.start)) / 3,
    data.end,
  ];
  const tickLabel = (at) =>
    new Date(at * 1000).toLocaleString(locale === "nl" ? "nl-NL" : locale === "en" ? "en-GB" : undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  return `<figure class="device-chart"><div class="chart-plot"><div class="chart-scale" aria-label="${nl?"Niet-beschikbare geregistreerde apparaten":"Unavailable registered devices"}"><span>${esc(max)} ${nl?"apparaten":"devices"}</span><span>${number(Math.floor(max / 2), 0)}</span><span>0</span></div><svg viewBox="0 0 ${width} ${height + 12}" role="img" aria-label="${nl?"Unieke waargenomen niet-beschikbare apparaten aan het einde van meetvakken. Grijs betekent ontbrekende dekking.":"Unique observed unavailable devices at bucket ends. Grey marks missing coverage."}">${bars}<line class="chart-axis" x1="0" x2="${width}" y1="${height}" y2="${height}"/></svg></div><figcaption>${ticks.map((at) => `<span>${esc(tickLabel(at))}</span>`).join("")}</figcaption><div class="chart-legend"><span class="legend-persistent">${esc(label.persistent)}</span><span class="legend-new">${esc(label.new)}</span><span class="legend-expected">${esc(label.expected)}</span><span class="legend-gap">${nl?"Onbekende dekking":"Unknown coverage"}</span></div></figure>`;
}
function deviceActions(items, primary = true) {
  if (!items.length)
    return `<div class="calm-state"><div><h3>No current investigation selected</h3><p>Known and expected backlog remains visible below. Missing coverage does not establish healthy devices.</p></div></div>`;
  return `<div class="priority-grid">${items
    .slice(0, 3)
    .map((item, index) => {
      const featured = primary && index === 0;
      const otherDevices = (item.related_devices || []).filter(
        (device) => device.device_id !== item.device_id,
      );
      return `<article class="priority-card ${featured ? "featured" : ""}"><span class="overline">${esc(item.kind.replaceAll("_", " "))}</span><h3>${esc(item.title)}</h3>${prose(item.impact, 110, "Full affected scope")}${item.evidence_since ? `<small class="affected-id">Retained evidence from ${esc(date(item.evidence_since))}${item.new_device_count ? ` · ${esc(item.new_device_count)} observed transitions in 24 h` : ""}</small>` : ""}<div class="next-check"><span class="overline">NEXT MANUAL CHECK</span>${prose(item.manual_step, 120, "Full check")}</div><a class="${featured ? "button primary" : "quiet-link"}" ${featured ? 'data-primary-investigation="true"' : ""} href="${esc(item.href)}" aria-label="${esc(item.action_label || "Open investigation")}: ${esc(item.title)}">${esc(item.action_label || (featured ? "Open investigation" : "View evidence"))} ↗</a>${otherDevices.length ? `<details><summary>Other affected devices (${esc(item.device_count - 1)})</summary><ul>${otherDevices.map((device) => `<li><a href="#devices/reliability?device=${encodeURIComponent(device.device_id)}">${esc(device.name)}</a></li>`).join("")}</ul>${item.related_devices_limited ? "<p>Only the first eight affected members are listed. Full integration inventory remains available separately.</p>" : ""}</details>` : ""}<details><summary>Evidence & validation</summary>${item.scope_note ? `<p>${esc(item.scope_note)}</p>` : ""}<p>${esc(item.validation)}</p></details></article>`;
    })
    .join("")}</div>`;
}
function heatmapUnknown(point) {
  return point.offline == null || point.observed == null || point.observed === 0 ||
    point.selection_limited || point.coverage < 1;
}
function heatmapDescription(point) {
  const coverage = `Monitoring coverage ${coverageLabel(point.coverage)}`,
    subset = point.selection_limited
      ? " Retained device-history subset only; omitted devices remain unknown."
      : "";
  if (point.observed == null || point.observed === 0)
    return `Unknown: no observed device membership at this bucket end. ${coverage}.${subset}`;
  if (point.offline == null)
    return `Unavailable-device count unknown. ${coverage}.${subset}`;
  return `${point.offline} unavailable devices; ${point.unknown ?? "Unknown"} unassessed, ${point.partial ?? "Unknown"} partial; ${point.observed} observed devices. ${coverage}.${point.coverage < 1 ? " Uncovered time remains unknown." : ""}${subset}`;
}
function integrationLabel(platform) {
  return {zha:"Zigbee (ZHA)",zwave_js:"Z-Wave JS",mqtt:"MQTT",esphome:"ESPHome",music_assistant:"Music Assistant"}[platform] || platform;
}
function integrationMap(data) {
  const groups = data.integrations || { items: [] };
  return `<details class="integration-heatmap"><summary>Integration observations (${esc(groups.total || 0)})</summary><p class="muted">Each cell is an observed device count at a bucket end. Grey is unknown, gold is partial evidence, burgundy marks device-wide unavailable. Shared membership is correlation, not a network diagnosis; group totals can overlap for devices with multiple integrations.</p>${(groups.items || []).map((item) => `<div class="heatmap-row"><a href="#devices/reliability?platform=${encodeURIComponent(item.platform)}">${esc(integrationLabel(item.platform))}</a><svg viewBox="0 0 360 22" role="img" aria-label="${esc(item.platform)} unavailable-device history">${(item.points || []).map((point, i, points) => `<rect x="${(i * 360) / points.length}" y="1" width="${Math.max(1, 360 / points.length - 2)}" height="20" class="${heatmapUnknown(point) || (point.offline === 0 && point.unknown > 0) ? "chart-gap" : point.offline > 0 ? "heatmap-bad" : point.partial > 0 ? "series-new" : "heatmap-observed"}"><title>${esc(date(point.end))}: ${esc(heatmapDescription(point))}</title></rect>`).join("")}</svg><small>${esc(item.devices)} devices · ${item.offline == null ? "Unknown current state" : esc(item.offline) + " unavailable"}</small></div>`).join("")}${groups.limited ? "<p>Only 12 integration groups are shown; other observed groups remain available in the device list.</p>" : ""}</details>`;
}
function reliabilityOverview(data) {
  const counts = data.counts || {},
    burden = data.burden || {},
    trend = data.trend || {};
  const narrative =
    burden.direction === "unknown"
      ? "Outage-burden trend is unknown: no fully covered, stable comparison cohort yet."
      : `For the stable observed subset (${burden.comparable_devices} comparable; ${burden.excluded_devices ?? trend.uncompared_devices ?? 0} excluded of ${burden.total_devices ?? burden.comparable_devices} devices), outage burden ${burden.direction}: ${deviceDuration(burden.before_device_hours)} → ${deviceDuration(burden.after_device_hours)} across equal halves. Other devices remain unassessed for this comparison.`;
  const comparison =
    burden.direction === "unknown"
      ? "Burden comparison unknown · no stable, fully covered cohort"
      : `First → second half: ${{ increased: "↑", decreased: "↓", unchanged: "→" }[burden.direction] || "?"} ${deviceDuration(burden.before_device_hours)} → ${deviceDuration(burden.after_device_hours)} · ${burden.comparable_devices}/${burden.total_devices ?? burden.comparable_devices} comparable`;
  const priorities = (data.priorities || []).slice(0, 3);
  return `<div class="reliability-workspace"><section class="reliability-next" aria-label="Primary manual check"><p class="overline">YOUR NEXT MANUAL CHECK</p>${deviceActions(priorities.slice(0, 1))}</section><section class="reliability-hero"><div class="section-heading"><div><p class="overline">DEVICE RELIABILITY</p><h2>What changed in the house</h2></div><div class="period-picker" aria-label="Observation window">${["24h", "7d", "30d"].map((window) => `<a href="#overview/?window=${window}" ${window === data.window ? 'aria-current="true"' : ""}>${window}</a>`).join("")}</div></div>${deviceChart(data)}<p class="burden-signal">${esc(comparison)}</p><details class="burden-proof"><summary>Comparison evidence & limits</summary><p class="burden-narrative">${esc(narrative)}</p></details><div class="context-strip"><span><strong>${deviceDuration(data.device_hours)}</strong> observed unavailable</span><span><strong>${number(counts.offline, 0)}</strong> devices unavailable</span><span>${number(counts.partial, 0)} partial</span><span>${number(counts.unknown, 0)} unknown / unassessed · ${number(counts.excluded, 0)} disabled</span></div></section></div>${data.coverage_start == null ? `<p class="coverage-note">Device measurement has not started. Waiting for registry and state coverage; no healthy-device claim is possible.</p>` : `<p class="muted">Device measurement started ${esc(date(data.coverage_start))}. Earlier device history is unknown; retained entity history remains available.</p>`}${data.cache_as_of == null ? `<p class="coverage-note">${data.cache_state === "failed" ? "No chart snapshot is available: capture or compilation failed." : "No chart snapshot has been compiled yet."} Duration and coverage values remain unknown until a snapshot succeeds.</p>` : data.cache_pending ? `<p class="coverage-note">Chart snapshot from ${esc(date(data.cache_as_of))}; an updated snapshot is pending. Current checks use the latest local attention.</p>` : ""}${data.cache_state === "failed" && data.cache_as_of != null ? '<p class="coverage-note">Chart refresh failed. The last loaded snapshot does not establish fresh coverage.</p>' : ""}${!data.reliable_now ? '<p class="coverage-note">Current device coverage is unavailable. Last observations do not establish current health.</p>' : ""}${data.selection?.excluded_devices ? `<p class="coverage-note">This window includes ${esc(data.selection.included_devices)} of ${esc(data.selection.total_devices)} device histories; ${esc(data.selection.excluded_devices)} are omitted by the whole-device selection bound. Their state and duration remain unknown.</p>` : ""}${deviceStorageView(data.storage)}${data.limited || data.inventory_coverage?.limited ? '<p class="coverage-note">Observation selection is bounded; omitted records remain unknown and no complete trend is claimed.</p>' : ""}${priorities.length > 1 ? `<section class="secondary-checks"><div class="section-heading"><h2>Other manual checks</h2><a class="quiet-link" href="#devices/reliability">All observed devices →</a></div>${deviceActions(priorities.slice(1), false)}</section>` : `<p><a href="#devices/reliability">All observed devices →</a></p>`}<div class="backlog-strip"><span>${esc(data.known_offline || 0)} known unavailable · ${esc(data.expected_offline || 0)} expected unavailable</span><p>These remain in the observed backlog without weekly acknowledgment. A known partial→offline worsening can return to the action queue.</p><a href="#devices/reliability?state=offline">Inspect device backlog →</a></div>${integrationMap(data)}<details class="coverage-panel"><summary>Evidence, coverage & comparison method</summary><p>${esc(data.meaning)}</p><p>${number(data.covered_hours)} monitored wall-hours · ${deviceDuration(data.known_device_hours)} of known state · ${deviceDuration(data.unknown_device_hours)} of unknown state.</p><p>Unavailable-duration totals and burden include expected observations; ${deviceDuration(data.expected_device_hours)} is the expected portion. These are availability observations, not proof of a physical outage.</p><p>First/last status only: ${esc(trend.improved || 0)} improved, ${esc(trend.worsened || 0)} worsened, ${esc(trend.unchanged || 0)} unchanged; ${esc(trend.uncompared_devices || 0)} not comparable. This does not measure failure frequency or prove a cause.</p><p>Changed membership or classification makes comparisons and manual-check validation unknown across that change.</p><p>${esc(data.power_expectation)}</p><p>${esc(data.inventory_coverage?.unmapped_entities || 0)} entities have no current registered device association. Disabled, diagnostic-only and unclassified devices are not counted as healthy.</p><p><a href="#history/availability">Older entity observations</a> · <a href="#issues">All retained source observations</a></p>${table(
    ["Bucket end", "Persistent", "New", "Expected", "Coverage"],
    (data.points || []).map((p) => [
      esc(date(p.end)),
      esc(p.persistent ?? "Unknown"),
      esc(p.new ?? "Unknown"),
      esc(p.expected ?? "Unknown"),
      coverageLabel(p.coverage),
    ]),
  )}</details>`;
}
function deviceTimeline(item) {
  const events = [
    ...(item.coverage_gaps || []).map((row) => ({
      at: row.started,
      title: "Unknown observation gap",
      detail: "No covered device observations until " + date(row.ended),
      end: row.ended,
    })),
    ...(item.history || []).map((row) => ({
      at: row.started,
      title: row.state,
      detail: row.reason + " · " + row.attention,
      end: row.ended,
    })),
    ...(item.checks || []).map((row) => ({
      at: row.created,
      title: "Manual check · " + row.kind,
      detail: row.note,
      validation: row.validation,
    })),
  ].sort((a, b) => b.at - a.at);
  return `<ol class="observation-timeline">${events.map((event) => `<li><time>${esc(date(event.at))}</time><div><strong>${esc(event.title)}</strong><p>${esc(event.detail)}</p>${event.validation ? badge(event.validation) + "<small>Later observations; no causal attribution.</small>" : `<small>${event.end ? "Interval ended " + esc(date(event.end)) : "Coverage watermark limits observed duration"}</small>`}</div></li>`).join("")}</ol>`;
}
async function reliabilityDevices(route = "reliability") {
  const params = new URLSearchParams(route.split("?")[1] || "");
  const id = params.get("device");
  if (id) {
    const item = await api("reliability/devices/" + encodeURIComponent(id));
    return `<p><a href="#devices/reliability">← Observed devices</a></p><section class="problem-hero"><span class="overline">DEVICE OBSERVATIONS</span><h2>${esc(item.name)}</h2>${badge(item.reliable_now ? item.state : "unknown")}${badge(item.attention)}<p>${esc(item.evidence.rule)}</p><p>Locally declared power expectation: ${esc(item.power)} · ${esc(item.evidence.meaningful)} meaningful signals · ${esc(item.evidence.unavailable)} unavailable · ${esc(item.evidence.unknown)} unknown · ${esc(item.evidence.unassessed_members ?? item.evidence.unknown)} unassessed members. <span class="evidence-recorded-at" title="When retained member details changed; not a monitoring-sync timestamp">Evidence details last recorded: ${Number.isFinite(item.evidence_at) ? esc(new Date(item.evidence_at * 1000).toLocaleString()) : "Unknown (no retained timestamp)"}.</span></p></section>${!item.reliable_now || item.reason === "removed_from_registry" ? '<p class="coverage-note">Current membership/coverage is uncertain. Removal or silence is not recovery.</p>' : ""}${investigationLink("availability",id,null,null,"Investigate this device with optional AI","device")}${card("Manual check and follow-through", `<p>Perform a check yourself, then record it locally. Vision does not ping, repair or control the device.</p><form id="device-check-form" data-device="${esc(id)}"><label>Check performed<select name="kind"><option value="power">Power / expected sleep</option><option value="integration">Integration status</option><option value="connection">Connection evidence</option><option value="other">Other manual check</option></select></label><label>Local note<input name="note" maxlength="400"></label><button type="submit">Record performed check</button></form>${(item.checks || []).map((check) => `<article class="row"><strong>${esc(date(check.created))} · ${esc(check.kind)}</strong><p>${esc(check.note)}</p>${badge(check.validation)}<small>${esc(check.meaning)}</small></article>`).join("") || empty("No performed checks recorded yet.")}`)}${card("Observed device timeline", `${deviceTimeline(item)}<p>Latest 30 state/coverage transitions and 20 local check markers. Intervals are observations, not physical outage start/repair proof.</p>`)}<details class="coverage-panel"><summary>Durable local attention and power expectations</summary><p>Known/expected does not erase observed outage evidence. These settings stay until you change them; no weekly acknowledgment is required.</p><form id="device-policy-form" data-device="${esc(id)}"><label>Attention<select name="attention">${["review", "known", "expected"].map((value) => `<option ${value === item.attention ? "selected" : ""}>${value}</option>`).join("")}</select></label><label>Declared power expectation<select name="power">${["unknown", "battery", "mains"].map((value) => `<option ${value === item.power ? "selected" : ""}>${value}</option>`).join("")}</select></label><label>Local note<input name="note" maxlength="300" value="${esc(item.policy?.note || "")}"></label><button type="submit">Save in Vision</button>${item.policy?.worsened_at ? '<button type="submit" name="acknowledge_worsening" value="true">Acknowledge this worsening in Vision</button><small>A note or power edit keeps the prior baseline. This explicit action accepts the current observed state as the new local baseline.</small>' : ""}</form></details>${card(
      "Retained primary and ancillary evidence",
      table(
        ["Entity", "Role", "Availability"],
        (item.members || []).map((member) => [
          `<a href="#devices/${encodeURIComponent(member.entity_id)}">${esc(member.entity_id)}</a>`,
          esc(member.role),
          esc(member.availability),
        ]),
      ) +
        `<p>${esc(item.member_count)} current members; at most 64 shown. No numeric states are retained.</p>`,
    )}`;
  }
  const query = new URLSearchParams({
    state: params.get("state") || "all",
    platform: params.get("platform") || "",
    page: params.get("page") || "1",
  });
  const data = await api("reliability/devices?" + query);
  const next = new URLSearchParams(query);
  next.set("page", data.page + 1);
  return `<div class="section-heading"><h2>Observed registered devices</h2><a class="quiet-link" href="#devices/entities">Entity inventory →</a></div><p>${esc(data.total)} device observations. Partial, unknown, disabled and removed membership are distinct from device-wide unavailable evidence.</p>${!data.reliable_now ? '<p class="coverage-note">Current coverage is unavailable; retained states are historical evidence.</p>' : ""}<form id="device-filter"><label>Observed state<select name="state">${["all", "offline", "partial", "unknown", "excluded", "online"].map((state) => `<option value="${state}" ${state === query.get("state") ? "selected" : ""}>${state}</option>`).join("")}</select></label><label>Integration<input name="platform" maxlength="100" value="${esc(query.get("platform"))}"></label><button type="submit">Filter devices</button></form>${table(
    ["Device", "Observed state", "Attention", "Power"],
    data.items.map((item) => [
      `<a href="#devices/reliability?device=${encodeURIComponent(item.device_id)}">${esc(item.name)}</a>`,
      badge(data.reliable_now ? item.state : "unknown"),
      badge(item.attention),
      esc(item.power),
    ]),
  )}${data.has_more ? `<a class="button" href="#devices/reliability?${next}">Next devices →</a>` : ""}<p><a href="#overview">Return to device trend</a> · <a href="#issues">All retained source observations</a></p>`;
}
function bindReliability() {
  const filter = $("#device-filter");
  if (filter)
    filter.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = new FormData(filter);
      const next =
        "#devices/reliability?" +
        new URLSearchParams({
          state: value.get("state"),
          platform: value.get("platform"),
          page: "1",
        });
      if (location.hash === next) render();
      else location.hash = next;
    });
  for (const [selector, suffix, fields] of [
    ["#device-check-form", "checks", ["kind", "note"]],
    ["#device-policy-form", "policy", ["attention", "power", "note"]],
  ]) {
    const form = $(selector);
    if (!form) continue;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = new FormData(form),
        body = {};
      for (const field of fields) body[field] = input.get(field);
      if (suffix === "policy" && event.submitter?.name === "acknowledge_worsening")
        body.acknowledge_worsening = true;
      const button = form.querySelector("button");
      button.disabled = true;
      try {
        await api(
          "reliability/devices/" +
            encodeURIComponent(form.dataset.device) +
            "/" +
            suffix,
          { method: "POST", body: JSON.stringify(body) },
        );
        notice.textContent =
          "Saved only in Vision. Later covered observations determine validation; no HA action was performed.";
        await render();
      } catch (error) {
        notice.textContent = error.message;
        button.disabled = false;
      }
    });
  }
}

function overviewEvidence(data) {
  const health = data.health || {}, coverage = data.local?.cases?.rule_coverage;
  return `<details class="monitoring-evidence"><summary>Monitoring sources & retained investigations</summary>${data.last_gap ? `<p>Last monitoring gap ${esc(date(data.last_gap))}. Missing observations remain unknown.</p>` : ""}${coverage?.truncated ? `<p>Static checks are bounded: ${esc(coverage.retained)} retained; ${esc(coverage.omitted)} additional checks omitted.</p>` : ""}<p>Last sync ${esc(date(health.last_sync))}. Registry permissions and trace-detail coverage can limit local conclusions.</p><details><summary>Capability and trace coverage</summary><pre>${esc(JSON.stringify({capabilities:health.capabilities, traces:health.trace_detail_coverage},null,2))}</pre></details>${latestAuditSummary(data.latest_audit)}<p><a href="#history/changes?outcome=changed">Observed structural changes</a> · <a href="#automations">Automation investigations</a> · <a href="#devices/entities">Entity inventory</a> · <a href="#history">Retained history</a></p></details>`;
}

async function overview() {
  const data = await api("overview");
  const r = data.reliability;
  if (r && typeof r === "object" && Array.isArray(r.points) &&
      ["24h", "7d", "30d"].includes(r.window) && Number.isFinite(r.start) &&
      Number.isFinite(r.end) && r.end > r.start && r.counts &&
      ["online", "offline", "partial", "unknown", "excluded"].every(
        (key) => Number.isInteger(r.counts[key]) && r.counts[key] >= 0)) {
    const primaryData = data;
    const window =
      new URLSearchParams(location.hash.split("?")[1] || "").get("window") ||
      "24h";
    const metricData =
      window === "24h"
        ? primaryData.reliability
        : await api("reliability?window=" + encodeURIComponent(window));
    return reliabilityOverview(metricData) + overviewEvidence(primaryData);
  }
  const knownLegacy = !Object.hasOwn(data, "reliability") &&
    data.health?.version === "0.2.0" && Array.isArray(data.local?.cases?.items) &&
    Number.isFinite(data.local.cases.total) && Number.isFinite(data.coverage_started);
  if (!knownLegacy) throw Error("Device reliability snapshot unavailable; no complete healthy or zero-duration conclusion is established.");
  // Compatibility with the published 0.2.0 shape only; modern device views do not
  // fetch secondary entity counts/history that cannot affect their device priorities.
  const [availableResult, changeResult] = await Promise.allSettled([
    api("cases?source=availability&status=attention&limit=1"),
    api("history/page?kind=changes&outcome=changed&limit=3"),
  ]);
  const availability =
      availableResult.status === "fulfilled" ? availableResult.value : null,
    changes = changeResult.status === "fulfilled" ? changeResult.value : null,
    local = data.local,
    health = data.health,
    visible = overviewCases(local.cases.items, availability);
  const gaps = [];
  if (!availability)
    gaps.push(
      "Availability attention count could not be loaded; the retained priority sample may be incomplete.",
    );
  else if (
    (availability.total === 0 &&
      local.cases.items.some((item) => item.source === "availability")) ||
    availability.total > local.cases.total
  )
    gaps.push(
      "Availability and primary counts reflect different observation moments; current totals are uncertain.",
    );
  if (!changes)
    gaps.push(
      "Recent structural changes could not be loaded; absence of changes is unknown.",
    );
  if (!health.connected)
    gaps.push("Home Assistant is disconnected. Observations may be stale.");
  if (data.last_gap)
    gaps.push(
      "Last monitoring gap " +
        date(data.last_gap) +
        ". Missing events remain unknown.",
    );
  if (local.cases.rule_coverage?.truncated)
    gaps.push(
      "Static checks are bounded: " +
        local.cases.rule_coverage.retained +
        " retained; " +
        local.cases.rule_coverage.omitted +
        " additional checks omitted.",
    );
  return (
    `<div class="section-heading"><div><p class="overline">YOUR NEXT INVESTIGATION</p><h2>What needs attention</h2></div><a class="quiet-link" href="#issues">${esc(local.cases.total)} attention cases as of this read · Review queue →</a></div>${priorityCards(visible, !availability)}${unknownView(gaps, "Observation limits")}` +
    `<div class="context-strip"><span><strong>${esc(data.entities)}</strong> entities</span><span><strong>${esc(data.automations)}</strong> automations</span><span><strong>${esc(local.structural_changes_24h)}</strong> structural changes observed in 24 h</span><span>Last sync ${esc(date(health.last_sync))}</span></div>` +
    `<div class="split">${card("Latest retained changes", !changes ? empty("Change history unavailable; no absence of changes is established.") : changes.items.length ? `<ul class="change-list">${changes.items.map((change) => `<li><span class="change-dot" aria-hidden="true"></span><div>${autoLink(change.entity_id, short(change.entity_id, 90))}<small>${esc(date(change.observed_at))} · structural projection observed</small></div></li>`).join("")}</ul><p><a href="#history/changes?outcome=changed">Explore change history →</a></p>` : empty("No retained structural changes. A first observation is only a baseline."))}${card("Latest optional audit", latestAuditSummary(data.latest_audit))}</div>` +
    `<details class="coverage-panel"><summary>Monitoring coverage & active source counts</summary><p>${esc(local.availability_count)} active availability observations; expected, known and snoozed cases keep their source facts. ${esc(data.unavailable)} inventory entities are unexpected offline.</p><p>Monitoring began ${esc(date(data.coverage_started))}. Last sync ${esc(date(health.last_sync))}.</p><pre>${esc(JSON.stringify({ capabilities: health.capabilities, traces: health.trace_detail_coverage }, null, 2))}</pre></details>`
  );
}

async function devices(route) {
  if (!route || route.startsWith("reliability"))
    return reliabilityDevices(route || "reliability");
  if (route === "entities") route = null;
  const data = await api("devices");
  if (route && /^(device|integration)%3A/i.test(route)) {
    const key = decodeURIComponent(route),
      [kind, ...parts] = key.split(":"),
      identifier = parts.join(":");
    const impact = await api(
      "dependencies?" + new URLSearchParams({ kind, identifier }),
    );
    return (
      `<p><a href="#devices/entities">← Entity inventory</a></p>` +
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
      `<p><a href="#devices/entities">← Entity inventory</a></p>` +
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
    `<details class="history-disclosure"><summary>Optional AI automation proposals</summary>${card(
      "Optional automation investigation",
      `<div class="toolbar">${investigationLink("automation", entity, selected, params.get("compare"), "Preview automation logic investigation")}${investigationLink("optimization", entity, selected, params.get("compare"), "Preview evidence-based optimization")}</div><p class="muted">The selected runs are carried into the request preview. Optimization requires comparable retained evidence.</p>`,
    )}</details>` +
    card(
      "Retained execution comparison",
      `<form id="run-form" data-entity="${esc(entity)}"><label>Inspect run<select name="run_id" required>${options(selected)}</select></label><label>Compare with<select name="compare">${options(params.get("compare"))}</select></label><button type="submit">Inspect evidence</button></form><p>Each run is bound to its retained structural projection. Raw payloads and omitted predicates are not compared.</p>${
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
            `<details><summary>Inspect ${esc(structure.nodes.length)} retained logic nodes</summary>${table(
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
            )}</details>` +
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
      "Observed structure changes",
      table(
        ["Observed", "Kind / source", "Before → after"],
        data.configuration_changes.map((change) => [
          esc(date(change.observed_at)),
          esc(change.kind + " · " + change.source),
          deltaView(change.delta) +
            `<details><summary>Structure digests</summary><code>${esc(change.before_digest || "No baseline")} → ${esc(change.after_digest)}</code></details>`,
        ]),
      ),
    )
  );
}
function manualPlan(data) {
  const item = data.case,
    detail = item.detail || {},
    { kind, path } = investigationFocus(data);
  const place = path
    ? " at " + path
    : " in the retained run (exact path unknown)";
  const existing = (data.manual_checks || []).filter(Boolean);
  const plans = {
    template_error: [
      "Review the failing template step" +
        place +
        " in Home Assistant. Its raw expression is not retained here.",
      "Check the referenced inputs and handling of missing values before proposing a manual edit.",
    ],
    device_communication: [
      "Inspect the failing action and its declared target" + place + ".",
      "Check that device's power, availability and integration diagnostics around the error. Compare healthy siblings before assigning a cause.",
    ],
    timeout: [
      "Inspect the wait condition" +
        place +
        ", its timeout and continue-on-timeout setting.",
      "Compare a completed retained run. Review whether the expected event or condition was actually observed before changing a timeout.",
    ],
    mode_conflict: [
      "Review the actual refused-start evidence and the retained mode/max-runs setting.",
      "Compare overlapping retained runs and trigger timing. Check intended concurrency before proposing a manual mode change.",
    ],
    condition_stop: [
      "Review the stopped condition" +
        place +
        " and the available typed operands.",
      "Check whether the gate was intended to be false at that time. A condition stop alone is not an execution failure.",
    ],
    missing_target: [
      "Locate the explicit reference " +
        (detail.target || "at the reported path") +
        " in the current observed structure.",
      "Check the registry for removal, replacement or disabling. If a change is needed, update the reference manually in Home Assistant.",
    ],
    availability: [
      "Check whether this entity is intentionally asleep, disconnected or powered down.",
      "Inspect its retained availability segments and related devices, then check power/connectivity manually. A shared integration does not establish a cause.",
    ],
  };
  if (item.source === "repair")
    return [
      "Open the matching Home Assistant Repair" +
        (detail.domain || detail.issue_id
          ? " (" +
            [detail.domain, detail.issue_id].filter(Boolean).join(" / ") +
            ")"
          : "") +
        ".",
      "Read its instructions and prerequisites before making any manual change.",
    ];
  return (
    plans[kind] ||
    existing
      .concat(
        "Compare the observation with its retained context before proposing a manual correction.",
      )
      .slice(0, 3)
  );
}
function validationPlan(data) {
  const item = data.case,
    entity = data.affected?.[0];
  if (item.source === "availability")
    return {
      text: "Look for a later available segment without an intervening observation gap. Local expected/known status alone does not show recovery.",
      href: entity
        ? "#history/availability?entity=" + encodeURIComponent(entity)
        : "#history/availability",
      label: "Inspect availability history",
    };
  if (item.source === "static")
    return {
      text: "Inspect a later current structural observation and registry coverage. Verify whether the explicit reference or reported rule changed.",
      href: entity?.startsWith("automation.")
        ? "#automations/" + encodeURIComponent(entity)
        : "#history/changes",
      label: "Inspect observed logic",
    };
  if (entity?.startsWith("automation."))
    return {
      text: "Choose a later retained run and compare the same retained structure where available. Check the failed boundary and continued errors; a trigger alone is not completion.",
      href: "#automations/" + encodeURIComponent(entity),
      label: "Choose a retained run to compare",
    };
  return {
    text: "Inspect a later retained source observation and its coverage. A local attention change does not prove that the underlying issue was repaired.",
    href: "#issues/?status=all&source=" + encodeURIComponent(item.source),
    label: "Review retained source cases",
  };
}
function observationTimeline(data) {
  const rows = data.timeline || [],
    entity = data.affected?.[0];
  const events = (items) =>
    `<ol class="observation-timeline">${items.map((event) => `<li><time>${esc(event.kind === "automation_run" && !["ha_trace", "event"].includes(event.source) ? "Start unverified" : date(event.at))}</time><div><strong>${esc(event.kind.replaceAll("_", " "))}</strong>${prose(event.summary, 180, "Full observation")}<small>${esc(event.source)}${event.uncertain ? " · Uncertain boundary / observation gap" : ""}</small>${event.run_id && entity?.startsWith("automation.") ? `<p>${autoLink(entity, "Inspect this retained run", event.run_id)}</p>` : ""}</div></li>`).join("")}</ol>`;
  return `${data.last_observation_gap != null ? `<p class="last-gap">Last retained observation gap: ${esc(date(data.last_observation_gap))}. Missing events remain unknown.</p>` : ""}${rows.some((event) => event.kind === "automation_run" && !["ha_trace", "event"].includes(event.source)) ? '<p class="muted">Unverified run starts have unknown chronological order.</p>' : ""}${events(rows.slice(0, 6))}${rows.length > 6 ? `<details><summary>${rows.length - 6} more retained observations</summary>${events(rows.slice(6))}</details>` : ""}${data.timeline_truncated ? `<p class="muted">Timeline is bounded; further records may exist in History.</p>` : ""}`;
}
function dossierView(data) {
  const item = data.case,
    plan = manualPlan(data),
    validation = validationPlan(data);
  const normalize = (text) =>
    plain(text).trim().replace(/\s+/g, " ").toLowerCase();
  const planned = new Set(plan.map(normalize));
  const guidance = [...new Set(data.manual_checks || [])].filter(
    (text) => text && !planned.has(normalize(text)),
  );
  const affected = (data.affected || [])
    .map((entity) =>
      entity.startsWith("automation.")
        ? autoLink(entity, entity, data.run?.run_id)
        : `<a href="#devices/${encodeURIComponent(entity)}">${esc(entity)}</a>`,
    )
    .join(" · ");
  return (
    `<p class="breadcrumb"><a href="#issues">← All cases</a></p><section class="problem-hero"><p class="overline">01 · PROBLEM</p><div class="card-topline">${badge(item.severity, item.severity)}${badge(item.status)}<span class="source-label">${esc(item.source)} · ${item.source_active ? "source active" : "source inactive"}</span></div><h2>${esc(short(item.title, 140))}</h2>${Array.from(plain(item.title)).length > 140 ? `<details><summary>Full problem title</summary><p>${esc(item.title)}</p></details>` : ""}${prose(item.summary, 240, "Full observed summary")}<div class="affected-links">${affected}</div><ol class="workflow"><li>Problem</li><li>Evidence</li><li>Manual plan</li><li>Validation</li></ol></section>` +
    unknownView(data.unknowns) +
    `<div class="investigation-layout"><div>${card("02 · Retained evidence", `${list(data.facts.filter((fact) => fact !== item.summary).map((fact) => short(fact, 180)))}<details><summary>Full observed facts</summary>${list(data.facts)}</details><details><summary>Observation dates & recurrence</summary><dl><dt>First observed by Vision</dt><dd>${esc(date(item.first_seen))}</dd><dt>Last observed by Vision</dt><dd>${esc(date(item.last_seen))}</dd><dt>Recurrence</dt><dd>${esc(data.recurrence.reported)} · ${esc(data.recurrence.meaning)}</dd>${data.recurrence.retained_runs != null ? `<dt>Retained runs</dt><dd>${esc(data.recurrence.retained_runs)}</dd><dt>Runs with error observations</dt><dd>${esc(data.recurrence.retained_error_runs)}</dd>` : ""}</dl></details>${data.run ? `<details class="execution-disclosure"><summary>Selected execution · ${esc(data.run.outcome)} · ${esc(data.run.run_id)}</summary>${stepView(data.run)}</details>` : ""}`)}${card("03 · Manual investigation plan", `<ol class="manual-plan">${plan.map((step) => `<li>${prose(step, 200, "Full manual instruction")}</li>`).join("")}</ol>${guidance.length ? `<details class="source-guidance"><summary>Additional retained source checks</summary>${list(guidance)}</details>` : ""}<details><summary>Optional focused AI proposal</summary><p>Review the exact request before sending. Proposals need owner review and manual validation.</p>${investigationLink(suggestedTask(data), item.key, data.run?.run_id)}</details>`)}${card("04 · How to validate", `${prose(validation.text, 180, "Full validation criteria")}<a class="button" href="${esc(validation.href)}">${esc(validation.label)} →</a>`)}${card("Observation timeline", observationTimeline(data))}</div><div>${card("Attention in Vision", `<p>Source observations remain unchanged.</p><details><summary>Manage local attention · ${esc(item.local_status)}</summary><form id="case-status-form" data-key="${esc(item.key)}"><label>Status<select name="status">${["review", "known", "expected", "snoozed"].map((status) => `<option ${item.local_status === status ? "selected" : ""}>${status}</option>`).join("")}</select></label><label>Note<input name="note" maxlength="300" value="${esc(item.note || "")}"></label><label>Snooze hours<input name="hours" type="number" min="1" max="8760" value="24" required></label><button type="submit">Save local attention</button></form>${item.expires ? `<p>Attention resumes ${esc(date(item.expires))}.</p>` : ""}</details>`)}<details class="card"><summary>Affected relations</summary>${impactView(data.impact)}</details><details class="card"><summary>Retained redacted source detail</summary><pre>${esc(JSON.stringify(item.detail, null, 2))}</pre></details></div></div>`
  );
}

async function issues(route) {
  if (route && !route.startsWith("?")) {
    const data = await api(
      "cases/" + encodeURIComponent(decodeURIComponent(route)),
    );
    return dossierView(data);
  }
  const params = new URLSearchParams((route || "").replace(/^\?/, ""));
  if (!params.has("status")) params.set("status", "all");
  const data = await api("cases?" + params);
  const select = (name, values) =>
    `<label>${esc(name)}<select name="${esc(name)}">${values.map((value) => `<option ${value === (params.get(name) || "all") ? "selected" : ""}>${esc(value)}</option>`).join("")}</select></label>`;
  const pageLink = (page, text) => {
    const next = new URLSearchParams(params);
    next.set("page", page);
    return `<a class="button" href="#issues/?${next}">${esc(text)}</a>`;
  };
  return card(
    "Retained source observations",
    `<form id="case-filter"><label>Search<input name="q" maxlength="200" value="${esc(params.get("q") || "")}"></label>${select("status", ["attention", "all", "known", "expected", "snoozed", "resolved", "limited"])}${select("source", ["all", "automation", "automation_step", "repair", "log", "static", "availability"])}<button type="submit">Apply filters</button></form><p>${esc(data.total)} retained source observations · Page ${esc(data.page)}. Normal condition stops, intentional mode limits and static diagnostics are evidence, not automatically pending actions. <a href="#overview">Current manual-check priorities →</a></p>${caseCards(data.items)}<div class="toolbar">${data.page > 1 ? pageLink(data.page - 1, "Previous") : ""}${data.has_more ? pageLink(data.page + 1, "Next") : ""}</div>`,
  );
}
function requestView(data, enabled) {
  const value = data.preview,
    selection = data.local_selection;
  return `<h3>Frozen request · round ${esc(value.round)}</h3><p class="request-state">${badge(data.status || "preview")} ${data.in_flight ? "· response pending" : ""}</p>${value.readiness?.supported === false ? `<p class="warning">${esc(value.readiness.reason)} This local preview cannot be sent.</p>` : ""}<p>Task ${esc(value.task)} · Profile ${esc(value.profile)} · Captured ${esc(date(value.bundle.captured_at))}</p><p class="evidence-text">Local target ${esc(selection.target || selection.entity || selection.device || "System")} · Run ${esc(selection.run_id || "None")} · Compare ${esc(selection.compare || "None")} · Selection ${esc(selection.basis || selection.selection_basis)}</p><p class="muted">${esc(value.privacy_notice)} This preview covers this round only; follow-ups require their own preview and send.</p><p class="evidence-text">SHA-256 <code>${esc(data.digest)}</code></p><details><summary>Coverage, provenance & selected evidence</summary><pre>${esc(JSON.stringify(value.bundle, null, 2))}</pre></details>${Object.entries(
    value.requests,
  )
    .map(
      ([provider, request]) =>
        `<details><summary>Exact ${esc(provider)} request body · ${esc(value.policy.providers[provider].model)}</summary><p>${esc(request.url)} · credential headers excluded</p><pre>${esc(request.body_utf8)}</pre></details>`,
    )
    .join(
      "",
    )}${researchView(value.research)}${data.status === "preview" && value.round === 1 && value.task !== "audit" && value.profile !== "local_only" && !value.research && value.readiness?.supported !== false ? `<section class="research-prepare"><h4>Optional public-source research</h4><p>Preview generic public queries before fetching. No household identifiers or questions enter public searches. AI sending stays separate.</p><button type="button" id="plan-research">Preview public query plan</button><div id="public-research" aria-live="polite"></div></section>` : ""}<details><summary>Exact preview envelope, policy & bounded prior context</summary><pre>${esc(JSON.stringify(value, null, 2))}</pre></details><details><summary>Local evidence and identifier mapping · stays in Vision</summary><pre>${esc(JSON.stringify({ evidence: data.local_mapping, identifiers: data.local_aliases }, null, 2))}</pre></details><div class="toolbar"><button id="send-ai" class="primary" ${!enabled || data.in_flight || value.readiness?.supported === false || value.profile === "local_only" || !Object.keys(value.requests).length || (data.status && data.status !== "preview") ? "disabled" : ""}>Send this exact reviewed request</button><button id="revoke-ai">Revoke this request</button></div><p class="muted">Every attempt has its own conservative cost reservation. Technical failover can use only the exact configured alternative shown above, at these rates and limits. Budget failover requires separate configured consent. Local-only never sends.</p>`;
}
async function intelligence(route) {
  const params = new URLSearchParams((route || "").replace(/^\?/, ""));
  const data = await api("intelligence");
  let rounds = [],
    initial = null;
  const selectedId = params.get("analysis") || (!params.get("request") && !params.get("conversation") && !params.get("task") && !params.get("target") ? data.analyses[0]?.id : null);
  const selectedAnalysis = selectedId ? await api("intelligence/analyses/" + encodeURIComponent(selectedId)) : null;
  if (params.get("conversation")) {
    const conversation = await api(
      "intelligence/conversations/" +
        encodeURIComponent(params.get("conversation")),
    );
    rounds = conversation.rounds;
    initial = rounds[0];
  }
  const kind = initial?.kind || params.get("task") || "audit";
  const target = initial?.target || params.get("target") || "";
  const targetType = initial?.target_type || params.get("target_type") || "entity";
  const profile =
    initial?.profile ||
    (data.privacy === "local_only" ? "local_only" : "compact");
  return (
    (selectedAnalysis
      ? card(
          "Retained investigation",
          findings(selectedAnalysis) +
            `<details><summary>Retained local evidence mapping</summary><pre>${esc(JSON.stringify(parse(selectedAnalysis.evidence), null, 2))}</pre></details>${parse(selectedAnalysis.evidence)?.request_id ? `<p><a href="#intelligence/?request=${encodeURIComponent(parse(selectedAnalysis.evidence).request_id)}">Inspect exact sent request</a></p>` : ""}` +
            (selectedAnalysis.can_continue &&
            (parse(selectedAnalysis.evidence) || {}).conversation_id
              ? `<a class="button" href="#intelligence/?conversation=${encodeURIComponent(parse(selectedAnalysis.evidence).conversation_id)}">Continue scoped investigation</a>`
              : `<p>Historical analysis · original mapping retained. Start a new reviewed investigation for follow-up.</p>`),
        )
      : "") +
    (rounds.length
      ? card(
          "Scoped conversation",
          rounds
            .slice()
            .reverse()
            .map(
              (row, index) =>
                `<details class="conversation-round" ${index === 0 ? "open" : ""}><summary>Round ${esc(row.round)}${row.status === "revoked" ? " · Withdrawn; received result retained" : ""} · ${esc(short((parse(row.result) || {}).summary, 100))}</summary>${findings(row)}<a href="#intelligence/?request=${encodeURIComponent(row.request_id)}">Inspect retained exact request</a></details>`,
            )
            .join(""),
        )
      : "") +
    `<details class="ai-setup" ${selectedAnalysis || rounds.length ? "" : "open"}><summary>${rounds.length ? "Prepare a scoped follow-up" : "Prepare an optional AI investigation"}</summary>${card(
      "Focused AI investigation",
      `<p>${badge(data.enabled ? "AI opted in" : "AI disabled", data.enabled ? "success" : "warning")} ${badge(data.running ? "Analysis running" : "Idle")} · Configured privacy ceiling ${esc(data.privacy)}</p>${data.storage ? `<p class="muted">AI history headroom: ${esc((data.storage.available_payload_bytes / 1048576).toFixed(1))} MiB · ${esc(data.storage.available_request_slots)} request slots.</p><details><summary>AI storage limits</summary><p>${esc((data.storage.stored_bytes / 1048576).toFixed(1))} MiB retained payloads + ${esc((data.storage.promised_result_bytes / 1048576).toFixed(1))} MiB promised results; limit ${esc(data.storage.max_storage_bytes / 1048576)} MiB and ${esc(data.storage.max_requests)} requests. Existing history is preserved when admission stops. Ordinary retention applies across local history; there is no selective deletion control.</p></details>` : ""}<p>Each task uses its own instructions and relevant local evidence. Preview is local; sending requires configured AI opt-in, a model, prices and budget. Diagnostic consent applies to one reviewed request only.</p>${data.last_error ? `<p class="warning">${esc(data.last_error)}</p>` : ""}${data.daily ? `<p class="muted">Daily compact audit: ${esc(data.daily.day)} · ${esc(data.daily.status)}</p>` : ""}<form id="ai-form" data-enabled="${data.enabled}" data-running="${data.running}" data-conversation="${esc(params.get("conversation") || "")}"><label>Investigation<select name="kind" ${initial ? "disabled" : ""}>${Object.entries(
        data.tasks,
      )
        .map(
          ([key, task]) =>
            `<option value="${esc(key)}" ${key === kind ? "selected" : ""}>${esc(task.title)}</option>`,
        )
        .join(
          "",
        )}</select></label><label>Target scope<select name="target_type" ${initial ? "disabled" : ""}><option value="entity" ${targetType === "entity" ? "selected" : ""}>Entity or retained dossier</option><option value="device" ${targetType === "device" ? "selected" : ""}>Exact registered device · availability only</option></select></label><label>Local target<input name="target" maxlength="500" value="${esc(target)}" ${initial ? "readonly" : ""} placeholder="System audit uses no target"></label><label>Exact selected run<input name="run_id" maxlength="200" value="${esc(initial?.run_id || params.get("run_id") || "")}" ${initial ? "readonly" : ""} ${targetType === "device" ? "disabled" : ""}></label><label>Exact comparison run<input name="compare" maxlength="200" value="${esc(initial?.compare_id || params.get("compare") || "")}" ${initial ? "readonly" : ""} ${targetType === "device" ? "disabled" : ""}></label><label>Privacy profile<select name="profile" ${initial ? "disabled" : ""}>${[...new Set(["local_only", "compact", ...(data.privacy === "diagnostic" ? ["diagnostic"] : []), ...(initial ? [profile] : [])])].map((value) => `<option ${value === profile ? "selected" : ""}>${value}</option>`).join("")}</select></label><label>Follow-up focus<select name="followup_focus">${["clarify", "manual_solution", "counterevidence", "validation"].map((value) => `<option>${value}</option>`).join("")}</select></label><label class="wide">Optional question · diagnostic only<textarea name="question" maxlength="800" rows="3" placeholder="Compact investigations use the focus selector. No raw templates, credentials or personal details."></textarea></label><label class="check wide"><input type="checkbox" name="diagnostic_consent">I explicitly allow sanitized diagnostic identifiers, errors and safe structural operands for this preview. Redaction cannot guarantee removal of all personal data; I will inspect every body before sending.</label>${initial ? `<fieldset class="wide"><legend>One reviewed local evidence expansion</legend><p>Only initially frozen sections of this dossier can be added. No HA refetch, tools or free-form evidence requests.</p>${(data.tasks[kind]?.extra_sections || []).map((section) => `<label class="check"><input type="checkbox" name="sections" value="${esc(section)}">${esc(section)}</label>`).join("")}</fieldset>` : ""}<button type="submit" ${rounds.some((row) => row.status === "revoked") ? "disabled" : ""}>Prepare exact local preview</button>${rounds.some((row) => row.status === "revoked") ? '<p class="warning">This conversation includes a withdrawn round. Inspect its retained result below; start a new reviewed investigation to continue.</p>' : ""}</form><div id="ai-preview" aria-live="polite"></div>`,
    )}</details>` +
    `<details class="history-disclosure"><summary>Provider usage & estimated costs</summary>${card(
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
    )}</details>` +
    `<details class="history-disclosure"><summary>Retained analysis history</summary>${card(
      "Retained analyses",
      `<p><a href="#history/analyses">Search all retained analysis history →</a></p>` +
        (data.analyses.filter((a) => a.id !== selectedAnalysis?.id).length
          ? data.analyses
              .filter((a) => a.id !== selectedAnalysis?.id)
              .map((a) => {
                return `<article class="row"><p>${esc(a.summary)}</p><p class="muted">${esc(a.provider)} · ${esc(a.model)} · ${esc(date(a.created))}</p><a class="button" href="#intelligence/?analysis=${encodeURIComponent(a.id)}">Open findings and retained evidence</a>${a.can_continue && a.conversation_id ? ` · <a href="#intelligence/?conversation=${encodeURIComponent(a.conversation_id)}">Continue scoped investigation</a>` : `<p class="muted">Historical analysis · original evidence mapping available in detail.</p>`}</article>`;
              })
              .join("")
          : empty("No AI analysis yet. Local monitoring works without AI.")),
    )}</details>`
  );
}

async function bindIntelligence(route) {
  const form = $("#ai-form");
  if (!form) return;
  const data = {
    enabled: form.dataset.enabled === "true",
    running: form.dataset.running === "true",
  };
  const params = new URLSearchParams((route || "").replace(/^\?/, ""));
  let prepared = null,
    autoOpen = params.get("watch") === "1";
  const viewGeneration = generation;
  const navigate = (hash) => {
    if (location.hash === hash) render();
    else location.hash = hash;
  };
  const terminal = (status) => {
    if (status.in_flight || status.status === "sending") return false;
    const state = $("#ai-preview .request-state");
    if (state) state.innerHTML = badge(status.status);
    if (status.status === "completed" && status.analysis_id && autoOpen) {
      autoOpen = false;
      const hash =
        "#intelligence/?analysis=" + encodeURIComponent(status.analysis_id);
      // Consume only a one-shot watch entry. A lost POST response can finish
      // while still on the original audit/preparation page; preserve that entry.
      if (params.get("watch") === "1") window.location.replace(hash);
      else navigate(hash);
    } else {
      notice.textContent =
        "Investigation status: " +
        status.status +
        ". " +
        (status.error ||
          (status.status === "revoked"
            ? "Request withdrawn. Any transmitted usage and received result remain retained."
            : "Inspect the retained request before starting another investigation."));
      if (status.analysis_id) {
        $("#ai-preview .received-result")?.remove();
        $("#ai-preview").insertAdjacentHTML(
          "beforeend",
          `<p class="received-result"><a class="button ${status.status === "completed" ? "primary" : ""}" href="#intelligence/?analysis=${encodeURIComponent(status.analysis_id)}">${status.status === "completed" ? "Open received analysis" : "Inspect received result and retained usage"}</a></p>`,
        );
      }
    }
    return true;
  };
  const watch = async (requestId) => {
    try {
      while (
        viewGeneration === generation &&
        form.isConnected &&
        prepared?.request_id === requestId
      ) {
        const status = await api(
          "intelligence/requests/" + encodeURIComponent(requestId) + "/status",
        );
        if (
          viewGeneration !== generation ||
          !form.isConnected ||
          prepared?.request_id !== requestId
        )
          return;
        if (terminal(status)) return;
        notice.textContent =
          status.status === "revoked"
            ? "Request revoked. Waiting only for the already transmitted response; no further attempt is authorized."
            : "Investigation running in Vision. You may leave this page and reopen its retained request.";
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (error) {
      if (viewGeneration === generation)
        notice.textContent =
          error.message +
          " Reopen the retained request to check server status.";
    }
  };
  const bindPublic = (value) => {
    const button = $("#plan-research"), panel = $("#public-research");
    if (!button || !panel) return;
    const watchPublic = async id => {
      $("#send-ai").disabled = true;
      panel.innerHTML = `<p>Public research is running independently in Vision. AI has not been sent.</p><button type="button" id="revoke-research">Revoke public research</button>`;
      $("#revoke-research").onclick = async () => {
        try { await api("intelligence/research/"+id+"/revoke",{method:"POST"}); notice.textContent="Public research withdrawn. No further public GET is authorized."; }
        catch(error) { notice.textContent=error.message; }
      };
      try {
        while (viewGeneration === generation && panel.isConnected) {
          const status = await api("intelligence/research/"+id+"/status");
          if (viewGeneration !== generation || !panel.isConnected) return;
          if (status.status !== "running") {
            const detail = await api("intelligence/research/"+id);
            if (viewGeneration !== generation || !panel.isConnected) return;
            panel.innerHTML = `<p>Public research: ${esc(detail.status)} · ${esc(detail.attempts)} GET attempts. ${esc(detail.error || "")}</p>${researchView(detail.snapshot)}${detail.status === "completed" ? `${value.preview.profile === "diagnostic" ? '<label class="check"><input type="checkbox" id="research-consent">I explicitly allow the diagnostic profile for this new source-bound preview; I will inspect its complete exact bodies before sending.</label>' : ''}<button type="button" id="attach-research">Prepare new exact AI preview with these sources</button><p>No provider call occurs until you inspect and send that new preview.</p>` : '<p>Return to the local selection to prepare a new reviewed investigation.</p>'}`;
            $("#attach-research")?.addEventListener("click",async event => {
              event.target.disabled=true;
              try {
                const prepared = await api("intelligence/research/"+id+"/preview",{method:"POST",body:JSON.stringify({research_digest:detail.research_digest,diagnostic_consent:!!panel.querySelector("#research-consent")?.checked})});
                display(prepared);
                notice.textContent="New frozen preview prepared over the original local snapshot. Inspect source passages, versions, both exact provider bodies and costs before sending.";
              } catch(error) {notice.textContent=error.message;event.target.disabled=false;}
            });
            return;
          }
          await new Promise(resolve=>setTimeout(resolve,1000));
        }
      } catch(error) {if(viewGeneration===generation) notice.textContent=error.message+". Reopen this request to inspect public research status.";}
    };
    button.onclick = async () => {
      button.disabled=true;
      try {
        const plan = await api("intelligence/research/plan",{method:"POST",body:JSON.stringify({request_id:value.request_id,digest:value.digest})});
        panel.innerHTML=`<h4>Review public queries before fetching</h4><p>Only this generic catalog/problem/version plan leaves Vision. It is bounded to 6 GETs, 5 sources and 30 seconds; incomplete sources remain unknown. Reddit is unavailable without authentication.</p><pre>${esc(JSON.stringify(plan.plan,null,2))}</pre><p class="evidence-text">Plan SHA-256 <code>${esc(plan.plan_digest)}</code></p><button type="button" id="start-research">Fetch this public source plan</button>`;
        $("#start-research").onclick=async event=>{
          event.target.disabled=true;
          try {
            const job=await api("intelligence/research",{method:"POST",body:JSON.stringify({plan_id:plan.plan_id,plan_digest:plan.plan_digest})});
            navigate("#intelligence/?request="+encodeURIComponent(value.request_id)+"&research="+encodeURIComponent(job.research_id));
          } catch(error) {notice.textContent=error.message;event.target.disabled=false;}
        };
      } catch(error) {notice.textContent=error.message;button.disabled=false;}
    };
    if(params.get("research")) watchPublic(params.get("research"));
  };
  const display = (value) => {
    prepared = value;
    $("#ai-preview").innerHTML = requestView(
      value,
      data.enabled && !data.running,
    );
    $("#send-ai").addEventListener("click", async (event) => {
      event.target.disabled = true;
      // Freeze withdrawal behavior before waiting for the 202 response. An edit
      // during network transit must not revoke a job that the server has started.
      value.status = "sending";
      value.in_flight = true;
      autoOpen = true;
      notice.textContent =
        "Sending the frozen request. Usage is reserved conservatively while the provider responds.";
      try {
        const result = await api("intelligence", {
          method: "POST",
          body: JSON.stringify({
            request_id: value.request_id,
            digest: value.digest,
          }),
        });
        navigate(
          "#intelligence/?request=" +
            encodeURIComponent(result.request_id) +
            "&watch=1",
        );
      } catch (error) {
        if (viewGeneration !== generation || !form.isConnected) return;
        try {
          const status = await api(
            "intelligence/requests/" +
              encodeURIComponent(value.request_id) +
              "/status",
          );
          if (viewGeneration !== generation || !form.isConnected) return;
          if (status.status === "preview" && !status.in_flight) {
            display({ ...value, status: "preview", in_flight: false });
            notice.textContent =
              error.message +
              " Server confirms this request is unused. Review its frozen preview before retrying or edit the selection to replace it.";
          } else {
            value.status = status.status;
            value.in_flight = !!status.in_flight || status.status === "sending";
            notice.textContent =
              error.message + " Retained server state: " + status.status + ".";
            if (!terminal(status) && value.in_flight) watch(value.request_id);
          }
        } catch (statusError) {
          notice.textContent =
            error.message +
            " Server status could not be confirmed: " +
            statusError.message +
            ". Sending stays disabled; reopen this retained request to check it.";
        }
      }
    });
    bindPublic(value);
    if (value.status === "sending" || value.in_flight) watch(value.request_id);
    else if (value.status && value.status !== "preview") terminal(value);
    $("#revoke-ai").addEventListener("click", async () => {
      try {
        const result = await api(
          "intelligence/requests/" + value.request_id + "/revoke",
          {
            method: "POST",
          },
        );
        $("#send-ai").disabled = true;
        if (result.revoked) value.status = "revoked";
        notice.textContent = result.revoked
          ? "Request revoked. Already transmitted usage remains recorded."
          : "Request already completed or inactive; no unsent attempt was revoked.";
      } catch (error) {
        notice.textContent = error.message;
      }
    });
  };
  if (params.get("request"))
    display(
      await api(
        "intelligence/requests/" + encodeURIComponent(params.get("request")),
      ),
    );
  form.elements.target_type.addEventListener("change", () => {
    const device = form.elements.target_type.value === "device";
    form.elements.run_id.disabled = device;
    form.elements.compare.disabled = device;
  });
  form.addEventListener("input", async () => {
    if (!prepared) return;
    if (prepared.status !== "preview" || prepared.in_flight) {
      notice.textContent =
        "Form edits do not change or withdraw the retained request. Use its Revoke button to stop further attempts; transmitted usage remains recorded.";
      return;
    }
    const previous = prepared;
    prepared = null;
    $("#send-ai").disabled = true;
    try {
      const result = await api(
        "intelligence/requests/" + previous.request_id + "/revoke",
        { method: "POST" },
      );
      if (result.revoked) {
        $("#ai-preview").innerHTML = empty(
          "Selection changed; unused preview revoked. Prepare a new request preview.",
        );
      } else {
        notice.textContent =
          "The previous preview is no longer unused. Inspect its retained status before preparing another request.";
      }
    } catch (error) {
      notice.textContent =
        "Could not revoke the previous preview: " +
        error.message +
        ". Sending is disabled; retry its explicit Revoke button.";
    }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fields = new FormData(form),
      button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const value = {
        kind: form.elements.kind.value,
        target: fields.get("target") || null,
        run_id: fields.get("run_id") || null,
        compare: fields.get("compare") || null,
        profile: form.elements.profile.value,
        diagnostic_consent: fields.has("diagnostic_consent"),
        question: fields.get("question"),
        followup_focus: fields.get("followup_focus"),
        conversation_id: form.dataset.conversation || null,
        sections: fields.getAll("sections"),
      };
      if (form.elements.target_type.value === "device") value.target_type = "device";
      display(
        await api("intelligence/preview", {
          method: "POST",
          body: JSON.stringify(value),
        }),
      );
      notice.textContent =
        "Frozen locally. Inspect each exact provider body before sending.";
    } catch (error) {
      notice.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
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
        `<a href="#automations/${encodeURIComponent(item.entity_id)}?run_id=${encodeURIComponent(item.run_id)}" data-home-shell>Inspect run</a>`,
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
        `<p>${esc((parse(item.result) || {}).summary)}</p><a href="#intelligence/?analysis=${encodeURIComponent(item.id)}" data-home-shell>Open findings and original evidence</a>`,
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
    `<form id="history-filter"><label>Section<select name="kind">${["runs", "availability", "issues", "changes", "usage", "analyses"].map((value) => `<option ${value === kind ? "selected" : ""}>${value}</option>`).join("")}</select></label><label>Search<input name="q" maxlength="200" value="${esc(params.get("q") || "")}"></label><label>Entity (runs / availability / changes)<input name="entity" maxlength="200" value="${esc(params.get("entity") || "")}"></label><label>Outcome / state / source<input name="outcome" maxlength="100" value="${esc(params.get("outcome") || "")}"></label><label>Day (UTC)<input name="day" type="date" value="${esc(params.get("day") || "")}"></label><button type="submit">Search history</button></form><p class="muted">${esc(data.coverage)} <span data-home-shell>Structural baselines record observation time, not HA edit time. Costs include conservative uncertain reservations.</span></p>${table(headers, rows)}${data.next_cursor ? `<a class="button" href="#history/${kind}?${next}" data-home-shell>Next observations →</a>` : ""}<p><a href="#history/${kind}" data-home-shell>Start of this section</a></p>`,
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
      `<p data-home-shell>Configure provider keys, model IDs, opt-in, prices, budgets and the daily schedule in <strong data-home-shell>Settings → Apps → Vision → Configuration</strong>, then restart Vision. Credentials are never returned here. Prices are user supplied in USD per million tokens; a zero rate blocks AI requests.</p><details><summary data-home-shell>Current configuration (secrets excluded)</summary><dl>${Object.entries(
        data,
      )
        .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
        .join(
          "",
        )}</dl></details><p class="muted" data-home-shell>Budget failover needs its own opt-in. Costs are estimates at configured rates; enforce provider-side spending limits too. Anthropic/OpenAI process only opt-in evidence requests.</p>`,
    ) +
    card(
      "Expected offline behavior",
      `<p data-home-shell>Reduce attention for expected availability observations while preserving source facts. This changes only Vision's database. Reasons are redacted before storage.</p><form id="exception-form"><label>Entity<select name="entity_id" required>${devices.entities.map((e) => `<option value="${esc(e.entity_id)}">${esc(e.name)} (${esc(e.entity_id)})</option>`).join("")}</select></label><label>Reason<input name="reason" maxlength="300" required placeholder="For example, a battery device sleeps overnight"></label><label>Expires after hours<input name="hours" type="number" min="1" max="8760" value="24" required></label><button type="submit">Save exception</button></form>` +
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
function backgroundEngaged() {
  const focus = document.activeElement,
    selection = window.getSelection();
  return (
    document.hidden ||
    !!document.querySelector("#content details[open]") ||
    !!(focus && content.contains(focus) && focus !== content) ||
    !!(selection && !selection.isCollapsed)
  );
}
async function render({ background = false } = {}) {
  if (background && backgroundEngaged()) return;
  const id = ++generation;
  const renderRoute = location.hash || "#today";
  const [page, encoded] = location.hash.slice(1).split("/");
  const active = pages.map((p) => p.toLowerCase()).includes(page)
    ? page
    : "today";
  const title = pages.find((p) => p.toLowerCase() === active);
  $("#title").textContent = window.VisionHome?.label(title) || title;
  document
    .querySelectorAll("nav a")
    .forEach((a) => a.classList.toggle("active", a.hash === "#" + active));
  try {
    const health = await api("health");
    await window.VisionHome?.resolveLocale();
    if (id !== generation) return;
    if (health.configuration_error)
      notice.textContent = health.configuration_error;
    $("#connection").dataset.connected = String(health.connected);
    $("#connection").textContent =
      (health.connected ? "Connected" : "Disconnected") + " · Read only";
    const views = {
      today: () => window.VisionHome.today(),
      problems: () => window.VisionHome.problems(encoded || null),
      intake: () => window.VisionHome.intake(encoded || null),
      overview,
      devices: () => !encoded && window.VisionHome ? window.VisionHome.devices(null) : encoded?.startsWith("?") && window.VisionHome ? window.VisionHome.devices(encoded) : devices(encoded || null),
      automations: () => automations(encoded || null),
      issues: () => issues(encoded || null),
      intelligence: () => intelligence(encoded || null),
      history: () => history(encoded || null),
      settings: async () => (window.VisionHome?.settingsLinks() || "") + await settings(),
    };
    const html = await views[active]();
    if (id !== generation) return;
    if (background && backgroundEngaged()) return;
    content.innerHTML = html;
    window.VisionHome?.localizeShell(active, content);
    if (!background) {
      if (lastRenderedRoute !== renderRoute) {
        const main = $("#main");
        if (lastRenderedRoute !== null) main.focus({ preventScroll: true });
        if (lastRenderedRoute !== null || document.activeElement === document.body) {
          main.scrollTop = 0;
          main.scrollIntoView?.({ block: "start", behavior: "auto" });
        }
      }
      lastRenderedRoute = renderRoute;
    }
    searchTable();
    await bindIntelligence(encoded || null);
    bindReliability();
    window.VisionHome?.bind();
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
      if (background) {
        const message =
          "Refresh failed; last loaded observations remain visible. " +
          e.message;
        if (!notice.textContent || notice.textContent === lastRefreshFailure) {
          if (notice.textContent !== message) notice.textContent = message;
          lastRefreshFailure = message;
        }
        return;
      }
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
    ["", "#overview", "#today"].includes(location.hash.split("/")[0]) &&
    !document.querySelector("details[open]")
  )
    render({ background: true });
}, 15000);
render();
