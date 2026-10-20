"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { JSDOM } = require("jsdom");
const root = resolve(__dirname, "../..");
const html = readFileSync(resolve(root, "vision/static/index.html"), "utf8");
const script = readFileSync(resolve(root, "vision/static/app.js"), "utf8");
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function until(predicate) {
  for (let i = 0; i < 100; i++) {
    if (predicate()) return;
    await tick();
  }
  assert.fail("Shipped interface did not reach the expected state");
}
function item(key, source = "repair", priority = 0, detail = {}) {
  return {
    key,
    source,
    priority,
    severity: priority === 0 ? "critical" : "warning",
    title: "Observed " + key,
    summary: "Retained observation " + key,
    manual_check: "Inspect the declared evidence manually.",
    status: "review",
    local_status: "review",
    source_active: true,
    first_seen: 1,
    last_seen: 2,
    detail,
  };
}
function overview(items, total = items.length) {
  return {
    health: { version: "0.2.0", connected: true, last_sync: 3, capabilities: {} },
    entities: 5200,
    automations: 200,
    unavailable: 37,
    coverage_started: 1,
    last_gap: null,
    latest_audit: null,
    local: {
      cases: { items, total, rule_coverage: {} },
      structural_changes_24h: 2,
      availability_count: 37,
    },
  };
}
function run({
  outcome = "succeeded",
  unknown = false,
  continued = false,
  digest = "digest",
  error = "",
} = {}) {
  return {
    run_id: "selected",
    outcome,
    started: unknown ? null : 100,
    start_source: unknown ? "unknown" : "ha_trace",
    configuration_digest: digest,
    configuration: {
      nodes: [{ path: "action/0", kind: "wait_template" }],
      references: [],
    },
    evidence: {
      steps: [
        {
          path: "action/0",
          iteration: 0,
          observed_at: unknown ? null : 101,
          offset_seconds: unknown ? null : 1,
          wait_completed: !error,
          timeout: !!error,
        },
      ],
      errors: error
        ? [{ path: "action/0", iteration: 0, kind: "timeout", message: error }]
        : [],
      coverage: { error_count_is_lower_bound: unknown },
      completed_with_errors: continued,
      step_count: 1,
      error_count: error ? 1 : 0,
      duration_seconds: unknown ? null : 4,
    },
  };
}
function dossier(
  source = "automation",
  selected = run({ outcome: "failed", error: "Timeout waiting" }),
  rule = null,
) {
  const value = item("case", source, 1, {
    entity_id: "automation.example",
    run_id: "selected",
    rule,
  });
  return {
    case: value,
    run: selected,
    affected: ["automation.example"],
    facts: [value.summary, "Source is active."],
    unknowns: ["Observation gaps remain unknown."],
    manual_checks: ["Review retained source evidence."],
    hypotheses: [],
    recurrence: {
      reported: 2,
      meaning:
        "Retained reopen segments; repeated polls are not new occurrences.",
    },
    timeline: [
      {
        kind: "automation_run",
        summary: "Unknown run",
        at: 123,
        source: "legacy_unverified",
        run_id: "old",
      },
    ],
    impact: null,
  };
}
async function boot(route, fixtures, fallback = null) {
  const dom = new JSDOM(html, {
    url: "http://vision/#" + route,
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const calls = [],
    intervals = [];
  dom.window.setInterval = (callback) => {
    intervals.push(callback);
    return intervals.length;
  };
  dom.window.fetch = async (url, options) => {
    calls.push({ url, options });
    let data;
    if (url === "api/health") data = { connected: true };
    else if (Object.hasOwn(fixtures, url))
      data =
        typeof fixtures[url] === "function"
          ? await fixtures[url](options)
          : fixtures[url];
    else if (fallback) data = await fallback(url, options);
    else throw Error("Unexpected test request: " + url);
    return { ok: true, json: async () => data };
  };
  dom.window.eval(script);
  await until(
    () => dom.window.document.querySelector("#content").children.length,
  );
  await tick();
  assert.doesNotMatch(
    dom.window.document.querySelector("#notice").textContent,
    /Unexpected test request|Unable to load/,
  );
  return {
    dom,
    document: dom.window.document,
    calls,
    refresh: () => intervals[0](),
  };
}
const overviewFixtures = (
  items = [],
  availability = { total: 0, items: [] },
) => ({
  "api/overview": overview(items),
  "api/cases?source=availability&status=attention&limit=1": availability,
  "api/history/page?kind=changes&outcome=changed&limit=3": { items: [] },
});
const intelligence = {
  enabled: false,
  running: false,
  privacy: "compact",
  tasks: { audit: { title: "Audit" } },
  usage: [],
  analyses: [],
};

test("zero and one attention groups show truthful empty state or one working primary dossier link", async () => {
  for (const rows of [[], [item("repair:first")]]) {
    const fixture = overviewFixtures(rows),
      data = dossier("repair");
    fixture["api/cases/repair%3Afirst"] = data;
    const app = await boot("overview", fixture);
    try {
      assert.equal(
        app.document.querySelectorAll(".priority-card").length,
        rows.length,
      );
      assert.equal(
        app.document.querySelectorAll("[data-primary-investigation]").length,
        rows.length,
      );
      if (!rows.length)
        assert.match(
          app.document.querySelector("#content").textContent,
          /No cases in the attention queue/,
        );
      else {
        app.document.querySelector("[data-primary-investigation]").click();
        await until(() => app.document.querySelector(".problem-hero"));
        assert.match(
          app.document.querySelector("#content").textContent,
          /03 · Manual investigation plan/,
        );
        assert.match(
          app.document.querySelector(".manual-plan").textContent,
          /Open the matching Home Assistant Repair/,
        );
      }
      assert.equal(
        app.calls.filter(({ options }) => options.method === "POST").length,
        0,
      );
    } finally {
      app.dom.window.close();
    }
  }
});

test("duplicate run observations group before the three-card cap; availability volume is one group", async () => {
  const rows = [
    item("repair:old"),
    item("run:error", "automation", 1, {
      entity_id: "automation.example",
      run_id: 0,
    }),
    item("run:step", "automation_step", 3, {
      entity_id: "automation.example",
      run_id: 0,
    }),
    item("offline", "availability", 6),
  ];
  const app = await boot(
    "overview",
    overviewFixtures(rows, { total: 37, items: [rows[3]] }),
  );
  try {
    const cards = [...app.document.querySelectorAll(".priority-card")];
    assert.equal(cards.length, 3);
    assert.equal(cards[0].dataset.priorityKey, "repair:old");
    assert.equal(cards[1].dataset.priorityKey, "run:error");
    assert.match(cards[2].textContent, /37 entities need availability review/);
    assert.equal(
      app.document.querySelectorAll("[data-primary-investigation]").length,
      1,
    );
    assert.match(
      cards[2].querySelector("a").hash,
      /source=availability&status=attention/,
    );
  } finally {
    app.dom.window.close();
  }
});

test("many cases retain server severity order with at most three cards; availability-only has one", async () => {
  for (const only of [false, true]) {
    const offline = item("offline", "availability", 6);
    const rows = only
      ? [offline]
      : [
          item("critical:older"),
          ...Array.from({ length: 7 }, (_, i) =>
            item("failure:" + i, "automation", 1, {
              entity_id: "automation." + i,
              run_id: "r",
            }),
          ),
        ];
    const fixtures = overviewFixtures(rows, { total: 1200, items: [offline] });
    fixtures["api/overview"].local.cases.total = only ? 1200 : 1400;
    const app = await boot("overview", fixtures);
    try {
      assert.equal(
        app.document.querySelectorAll(".priority-card").length,
        only ? 1 : 3,
      );
      assert.equal(
        app.document.querySelectorAll("[data-primary-investigation]").length,
        1,
      );
      assert.match(
        app.document.querySelector(".section-heading").textContent,
        only ? /1200/ : /1400/,
      );
      if (!only)
        assert.equal(
          app.document.querySelector(".priority-card").dataset.priorityKey,
          "critical:older",
        );
    } finally {
      app.dom.window.close();
    }
  }
});

test("AI results show three short proposals, keep full escaped text and older legacy mapping on demand", async () => {
  const long = "A long manual proposal <img src=x onerror=alert(1)> ".repeat(
    30,
  );
  const findings = Array.from({ length: 12 }, (_, i) => ({
    finding: "Proposal " + i,
    evidence: ["E1"],
    severity: "warning",
    confidence: "low",
    uncertainty: "Not a proven cause",
    next_step: long,
    validation: "Inspect a later retained run",
  }));
  const analysis = {
    id: 7,
    provider: "synthetic",
    model: "legacy",
    created: 1,
    result: JSON.stringify({ summary: "Legacy summary", diagnoses: findings }),
    evidence: JSON.stringify({ mapping: { E1: "local.entity" } }),
    can_continue: false,
  };
  const app = await boot("intelligence/?analysis=7", {
    "api/intelligence": {
      ...intelligence,
      analyses: [{ id: 7, summary: "Legacy summary" }],
    },
    "api/intelligence/analyses/7": analysis,
  });
  try {
    const cards = [...app.document.querySelectorAll(".finding-card")];
    assert.equal(cards.length, 12);
    assert.equal(
      cards.filter((card) => !card.closest("details:not([open])")).length,
      3,
    );
    assert.equal(app.document.querySelector(".more-findings").open, false);
    assert.ok(
      cards[0].querySelector(".finding-detail").textContent.includes(long),
    );
    assert.equal(cards[0].querySelector(".finding-detail").open, false);
    assert.equal(app.document.querySelectorAll("img").length, 0);
    assert.equal(
      app.calls.filter(({ url }) => url === "api/intelligence").length,
      1,
    );
    assert.equal(
      app.calls.filter(({ url }) => url === "api/intelligence/analyses/7")
        .length,
      1,
    );
    assert.match(
      app.document.querySelector("#content").textContent,
      /local.entity/,
    );
    assert.ok(!app.document.querySelector(".ai-setup").open);
  } finally {
    app.dom.window.close();
  }
});

test("dossier evidence, targeted manual plan, truthful start timeline and validation stay connected", async () => {
  const unsafe =
    "Device timeout <img src=x onerror=alert(1)> " + "deep/".repeat(80);
  const app = await boot("issues/case", {
    "api/cases/case": dossier(
      "automation",
      run({ outcome: "failed", error: unsafe }),
    ),
  });
  try {
    assert.match(
      app.document.querySelector(".manual-plan").textContent,
      /timeout and continue-on-timeout/,
    );
    assert.match(
      app.document.querySelector("#content").textContent,
      /02 · Retained evidence/,
    );
    assert.match(
      app.document.querySelector("#content").textContent,
      /04 · How to validate/,
    );
    assert.match(
      app.document.querySelector(".observation-timeline time").textContent,
      /Start unverified/,
    );
    assert.match(
      app.document.querySelector(".trace-clock").textContent,
      /\+1 s/,
    );
    assert.match(
      app.document.querySelector(".trace-caption").textContent,
      /Times below are step starts/,
    );
    assert.equal(app.document.querySelectorAll("img").length, 0);
    assert.ok(
      app.document
        .querySelector(".error-excerpt details")
        .textContent.includes(unsafe),
    );
    const href = app.document.querySelector('a[href*="task=timeout"]').hash;
    assert.match(href, /task=timeout/);
    assert.match(href, /run_id=selected/);
    assert.equal(
      app.document.querySelector("#case-status-form").closest("details").open,
      false,
    );
  } finally {
    app.dom.window.close();
  }
});

test("unknown runs have no fabricated duration; completed-with-errors stays separate from failed", async () => {
  for (const options of [
    { unknown: true, outcome: "unknown" },
    { continued: true, outcome: "succeeded", error: "continued error" },
  ]) {
    const app = await boot("issues/case", {
      "api/cases/case": dossier("automation_step", run(options)),
    });
    try {
      const summary = app.document.querySelector(".run-summary").textContent;
      if (options.unknown) {
        assert.match(summary, /Not observed/);
        assert.doesNotMatch(summary, /Recorded duration/);
        assert.match(
          app.document.querySelector(".trace-clock").textContent,
          /Start unknown/,
        );
      } else {
        assert.match(summary, /Succeeded with step errors/);
        assert.doesNotMatch(summary, /failed/);
      }
    } finally {
      app.dom.window.close();
    }
  }
});

test("selected run and comparison remain in navigation, evidence and focused AI links", async () => {
  const first = run({ error: "wait timeout", outcome: "failed" }),
    second = { ...run(), run_id: "success" };
  const data = {
    name: "Synthetic automation",
    enabled: true,
    coverage: "Retained evidence",
    runs: [first, second],
    run: first,
    structure: null,
    structure_coverage: { current_configuration_available: false },
    configuration_limit: "Unknown predicates remain omitted.",
    local_cases: [],
    impact: null,
    configuration_changes: [],
    comparison: {
      left: first,
      right: second,
      comparable: true,
      limitation:
        "Same retained structure; source-specific server limit remains visible.",
      coverage_limited: false,
      differences: [
        {
          path: "action/0",
          iteration: 0,
          left: first.evidence.steps[0],
          right: second.evidence.steps[0],
        },
      ],
    },
  };
  const app = await boot(
    "automations/automation.example?run_id=selected&compare=success",
    {
      "api/investigation/automation.example?run_id=selected&compare=success":
        data,
    },
  );
  try {
    assert.equal(
      app.document.querySelector('[name="run_id"]').value,
      "selected",
    );
    assert.equal(
      app.document.querySelector('[name="compare"]').value,
      "success",
    );
    assert.match(
      app.document.querySelector(".callout").textContent,
      /Same retained structure; source-specific server limit remains visible/,
    );
    const links = [...app.document.querySelectorAll('a[href*="task="]')];
    assert.equal(links.length, 2);
    for (const link of links) {
      assert.match(link.hash, /run_id=selected/);
      assert.match(link.hash, /compare=success/);
    }
    assert.equal(app.document.querySelectorAll(".trace-timeline").length, 2);
    assert.doesNotMatch(
      app.document.querySelector(".callout").textContent,
      /same configuration/i,
    );
  } finally {
    app.dom.window.close();
  }
});

test("background refresh preserves focus and open details, including engagement during a pending read", async () => {
  let release,
    reads = 0;
  const fixtures = overviewFixtures([item("repair:one")]);
  const snapshot = fixtures["api/overview"];
  fixtures["api/overview"] = async () => {
    reads++;
    return reads === 2
      ? await new Promise((resolve) => {
          release = () => resolve(snapshot);
        })
      : snapshot;
  };
  const app = await boot("overview", fixtures);
  try {
    const first = app.document.querySelector(".priority-card"),
      link = first.querySelector("a");
    link.focus();
    app.refresh();
    await tick();
    assert.equal(reads, 1);
    link.blur();
    const details = app.document.querySelector(".coverage-panel");
    details.open = true;
    app.refresh();
    await tick();
    assert.equal(reads, 1);
    details.open = false;
    app.refresh();
    await until(() => release);
    link.focus();
    release();
    await tick();
    assert.equal(app.document.querySelector(".priority-card"), first);
    assert.equal(app.document.activeElement, link);
    link.blur();
    app.refresh();
    await tick();
    assert.notEqual(app.document.querySelector(".priority-card"), first);
  } finally {
    app.dom.window.close();
  }
});

test("AI headroom remains visible without suggesting eviction or selective deletion", async () => {
  const app = await boot("intelligence", {
    "api/intelligence": {
      ...intelligence,
      storage: {
        available_payload_bytes: 2097152,
        available_request_slots: 7,
        stored_bytes: 62914560,
        promised_result_bytes: 2097152,
        max_storage_bytes: 67108864,
        max_requests: 512,
      },
    },
  });
  try {
    assert.match(
      app.document.querySelector(".ai-setup").textContent,
      /2.0 MiB · 7 request slots/,
    );
    assert.match(
      app.document.querySelector(".ai-setup").textContent,
      /Existing history is preserved/,
    );
    assert.match(
      app.document.querySelector(".ai-setup").textContent,
      /no selective deletion control/,
    );
  } finally {
    app.dom.window.close();
  }
});

test("mixed errors bind the manual instruction and task link to the same relevant step", async () => {
  const errors = [
    {
      path: "action/0",
      iteration: 0,
      kind: "timeout",
      message: "Timeout waiting",
    },
    {
      path: "action/1",
      iteration: 0,
      kind: "template_error",
      message: "Template input undefined",
    },
    {
      path: "action/2",
      iteration: 0,
      kind: "step_error",
      message: "Device did not respond",
    },
  ];
  for (const [retained, task, path, steps] of [
    [errors, "template_error", "action/1"],
    [[errors[0], errors[2]], "device_communication", "action/2"],
    [[errors[0]], "timeout", "action/0"],
    [
      [
        { path: "action/0", kind: "step_error", message: "ValueError" },
        { ...errors[0], path: "action/1" },
      ],
      "timeout",
      "action/1",
      [{ path: "action/1", iteration: 0, wait_timed_out: true }],
    ],
    [
      [],
      "timeout",
      "action/1",
      [{ path: "action/1", iteration: 0, wait_timed_out: true }],
    ],
    [[{ ...errors[1], path: "unknown" }], "template_error", null],
  ]) {
    const selected = run({ outcome: "failed" });
    selected.configuration.nodes = [
      { path: "action/0", kind: "wait_template" },
      { path: "action/1", kind: "template" },
      { path: "action/2", kind: "service" },
    ];
    selected.evidence.errors = retained;
    selected.evidence.steps = steps || [
      {
        path: "action/0",
        iteration: 0,
        wait_timed_out: retained.some((e) => e.kind === "timeout"),
      },
    ];
    if (path === "action/1" && task === "timeout")
      selected.configuration.nodes[1].kind = "wait_for_trigger";
    selected.evidence.error_count = retained.length;
    selected.evidence.step_count = selected.evidence.steps.length;
    const data = dossier("automation", selected);
    data.case.step_path = path === "action/0" ? "action/2" : "action/0";
    const app = await boot("issues/case", { "api/cases/case": data });
    try {
      const instruction =
        app.document.querySelector(".manual-plan").textContent;
      const link = app.document.querySelector('a[href*="task="]');
      assert.equal(
        new URLSearchParams(link.hash.split("?")[1]).get("task"),
        task,
      );
      if (path) {
        assert.ok(instruction.includes(" at " + path));
        assert.ok(!instruction.includes(" at " + data.case.step_path));
      } else {
        assert.match(instruction, /exact path unknown/);
        assert.doesNotMatch(instruction, / at action\/0/);
      }
    } finally {
      app.dom.window.close();
    }
  }
});

test("supporting overview failures retain primary priorities and disclose missing coverage", async () => {
  const availability = "api/cases?source=availability&status=attention&limit=1";
  const changes = "api/history/page?kind=changes&outcome=changed&limit=3";
  for (const failed of [[availability], [changes], [availability, changes]]) {
    const fixtures = overviewFixtures([item("critical:retained")]);
    for (const key of failed)
      fixtures[key] = () => {
        throw Error("Synthetic supporting read failed");
      };
    const app = await boot("overview", fixtures);
    try {
      assert.equal(
        app.document.querySelector(".priority-card").dataset.priorityKey,
        "critical:retained",
      );
      assert.equal(
        app.document.querySelectorAll("[data-primary-investigation]").length,
        1,
      );
      assert.match(
        app.document.querySelector(".coverage-note").textContent,
        /could not be loaded/,
      );
      assert.doesNotMatch(
        app.document.querySelector("#content").textContent,
        /No cases in the attention queue/,
      );
      if (failed.includes(changes))
        assert.match(
          app.document.querySelector("#content").textContent,
          /Change history unavailable/,
        );
    } finally {
      app.dom.window.close();
    }
  }
});

test("partial or disagreeing availability reads never invent zero coverage or hide known observations", async () => {
  const availability = "api/cases?source=availability&status=attention&limit=1";
  const offline = item("offline", "availability", 6);
  for (const variant of ["failed", "zero", "only-counter", "empty-failed"]) {
    const fixtures = overviewFixtures(
      variant.includes("empty") || variant === "only-counter" ? [] : [offline],
      { total: 0, items: [] },
    );
    if (variant.includes("failed"))
      fixtures[availability] = () => {
        throw Error("Synthetic count failed");
      };
    if (variant === "only-counter")
      fixtures[availability] = { total: 37, items: [offline] };
    const app = await boot("overview", fixtures);
    try {
      const text = app.document.querySelector("#content").textContent;
      assert.doesNotMatch(text, /No cases in the attention queue/);
      if (variant === "empty-failed") {
        assert.match(text, /Priority coverage is incomplete/);
        assert.equal(app.document.querySelectorAll(".priority-card").length, 0);
      } else {
        assert.equal(app.document.querySelectorAll(".priority-card").length, 1);
        assert.match(
          text,
          variant === "only-counter"
            ? /37 entities/
            : /full attention count is unknown/,
        );
        assert.doesNotMatch(
          app.document.querySelector(".priority-card").textContent,
          /0 entities/,
        );
      }
    } finally {
      app.dom.window.close();
    }
  }
});

test("failed background read preserves last-loaded DOM, focus, open details and selected text", async () => {
  let fail,
    reads = 0;
  const fixtures = overviewFixtures([item("repair:retained")]),
    snapshot = fixtures["api/overview"];
  fixtures["api/overview"] = async () => {
    reads++;
    return reads === 2
      ? await new Promise((_, reject) => {
          fail = () => reject(Error("Synthetic primary refresh failure"));
        })
      : snapshot;
  };
  const app = await boot("overview", fixtures);
  try {
    const card = app.document.querySelector(".priority-card"),
      link = card.querySelector("a"),
      details = app.document.querySelector(".coverage-panel");
    app.refresh();
    await until(() => fail);
    details.open = true;
    link.focus();
    const selection = app.dom.window.getSelection();
    selection.selectAllChildren(card.querySelector("h3"));
    const selected = selection.toString();
    fail();
    await until(() =>
      /Refresh failed; last loaded observations remain visible/.test(
        app.document.querySelector("#notice").textContent,
      ),
    );
    assert.equal(app.document.querySelector(".priority-card"), card);
    assert.equal(app.document.activeElement, link);
    assert.equal(details.open, true);
    assert.equal(selection.toString(), selected);
  } finally {
    app.dom.window.close();
  }
});

test("initial primary failure is explicit and never claims an empty attention queue", async () => {
  const fixtures = overviewFixtures([]);
  fixtures["api/overview"] = () => {
    throw Error("Synthetic primary unavailable");
  };
  const app = await boot("overview", fixtures);
  try {
    assert.match(
      app.document.querySelector("#content").textContent,
      /Unable to load current observations/,
    );
    assert.match(
      app.document.querySelector("#notice").textContent,
      /Synthetic primary unavailable/,
    );
    assert.doesNotMatch(
      app.document.querySelector("#content").textContent,
      /No cases in the attention queue/,
    );
  } finally {
    app.dom.window.close();
  }
});

test("all declared references, retained manual guidance, gap dates and related cases remain reachable", async () => {
  const selected = run({ outcome: "failed", error: "Timeout waiting" });
  selected.configuration.references = Array.from({ length: 7 }, (_, i) => ({
    kind: "entity",
    path: "action/0",
    id: "light.target_" + i,
  }));
  const data = dossier("automation", selected);
  data.manual_checks = [
    "Specific source check to retain.",
    "Specific source check to retain.",
  ];
  data.last_observation_gap = 1000;
  const app = await boot("issues/case", { "api/cases/case": data });
  try {
    const references = app.document.querySelector(
      ".trace-body .affected-links",
    );
    assert.equal(references.querySelectorAll(":scope > a").length, 4);
    assert.match(
      references.querySelector("details summary").textContent,
      /3 more declared references/,
    );
    assert.equal(references.querySelectorAll("a").length, 7);
    assert.equal(
      app.document.querySelectorAll(".source-guidance li").length,
      1,
    );
    assert.match(
      app.document.querySelector(".source-guidance").textContent,
      /Specific source check to retain/,
    );
    assert.ok(
      app.document
        .querySelector(".last-gap")
        .textContent.includes(new Date(1000000).toLocaleString()),
    );
  } finally {
    app.dom.window.close();
  }
  const first = item("run:failure", "automation", 1, {
    entity_id: "automation.example",
    run_id: "same",
  });
  first.related_case_keys = ["run:other"];
  const fixtures = overviewFixtures([
    first,
    item("run:step", "automation_step", 3, {
      entity_id: "automation.example",
      run_id: "same",
    }),
  ]);
  const grouped = await boot("overview", fixtures);
  try {
    const card = grouped.document.querySelector(".priority-card");
    assert.equal(card.querySelectorAll(".related-cases a").length, 2);
    assert.match(
      card
        .querySelector("[data-primary-investigation]")
        .getAttribute("aria-label"),
      /Observed run:failure/,
    );
    assert.ok(
      [...card.querySelectorAll(".related-cases a")].some(
        (link) => link.hash === "#issues/run%3Astep",
      ),
    );
  } finally {
    grouped.dom.window.close();
  }
});

test("long identifiers retain exact related routes and a wrapping un-clipped affected label", async () => {
  const entity = "automation." + "nested_path_".repeat(16);
  const related = "automation_step:" + entity;
  const row = item("automation:" + entity, "automation", 1, {
    entity_id: entity,
    run_id: "selected",
  });
  row.related_case_keys = [related];
  const app = await boot("overview", overviewFixtures([row]));
  try {
    const style = app.document.createElement("style");
    style.textContent = readFileSync(
      resolve(root, "vision/static/style.css"),
      "utf8",
    );
    app.document.head.append(style);
    const affected = app.document.querySelector(".affected-id");
    const computed = app.dom.window.getComputedStyle(affected);
    assert.equal(computed.minWidth, "0");
    assert.equal(computed.maxWidth, "100%");
    assert.equal(computed.overflowWrap, "anywhere");
    assert.ok(!["hidden", "clip"].includes(computed.overflowX));
    assert.ok(!["hidden", "clip"].includes(computed.overflowY));
    assert.match(affected.textContent, /^automation\.nested_path_/);
    const disclosure = app.document.querySelector(".related-cases");
    disclosure.open = true;
    const link = disclosure.querySelector("a");
    assert.equal(link.textContent, related);
    assert.equal(link.hash, "#issues/" + encodeURIComponent(related));
    link.focus();
    assert.equal(app.document.activeElement, link);
  } finally {
    app.dom.window.close();
  }
});

test("selected analysis links its exact sent request while legacy mapping needs no request metadata", async () => {
  for (const requestId of [null, "c".repeat(32)]) {
    const analysis = {
      id: 7,
      provider: "synthetic",
      model: "retained",
      created: 1,
      result: JSON.stringify({ summary: "Received proposal", diagnoses: [] }),
      evidence: JSON.stringify({
        mapping: { E1: "retained.local.mapping" },
        ...(requestId ? { request_id: requestId } : {}),
      }),
      can_continue: false,
    };
    const app = await boot("intelligence/?analysis=7", {
      "api/intelligence": intelligence,
      "api/intelligence/analyses/7": analysis,
    });
    try {
      const links = [...app.document.querySelectorAll("#content a")].filter(
        (link) => link.textContent === "Inspect exact sent request",
      );
      assert.equal(links.length, requestId ? 1 : 0);
      if (requestId)
        assert.equal(links[0].hash, "#intelligence/?request=" + requestId);
      assert.match(
        app.document.querySelector("#content").textContent,
        /retained.local.mapping/,
      );
      assert.equal(
        app.calls.filter(({ url }) => url === "api/intelligence/analyses/7")
          .length,
        1,
      );
    } finally {
      app.dom.window.close();
    }
  }
});

test("a changes-only read failure keeps a known empty attention queue distinct from missing history", async () => {
  const fixtures = overviewFixtures([]);
  fixtures["api/history/page?kind=changes&outcome=changed&limit=3"] = () => {
    throw Error("Synthetic history unavailable");
  };
  const app = await boot("overview", fixtures);
  try {
    const text = app.document.querySelector("#content").textContent;
    assert.match(text, /No cases in the attention queue/);
    assert.match(text, /Change history unavailable/);
    assert.match(text, /absence of changes is unknown/);
    assert.doesNotMatch(text, /Priority coverage is incomplete/);
    assert.equal(
      app.document.querySelectorAll("[data-primary-investigation]").length,
      0,
    );
  } finally {
    app.dom.window.close();
  }
});

test("larger availability totals disclose different read moments without relabelling the primary total", async () => {
  const offline = item("offline", "availability", 6);
  const app = await boot(
    "overview",
    overviewFixtures([item("repair:known")], { total: 37, items: [offline] }),
  );
  try {
    const heading = app.document.querySelector(".section-heading");
    assert.match(heading.textContent, /1 attention cases as of this read/);
    assert.doesNotMatch(heading.textContent, /loaded snapshot|37 attention/);
    assert.match(
      app.document.querySelector(".coverage-note").textContent,
      /different observation moments/,
    );
    assert.match(
      app.document.querySelector("#content").textContent,
      /37 entities need availability review/,
    );
    assert.equal(
      app.document.querySelectorAll("[data-primary-investigation]").length,
      1,
    );
  } finally {
    app.dom.window.close();
  }
});

test("background failure streak deduplicates its warning and preserves later unrelated user notices", async () => {
  let reads = 0;
  const fixtures = overviewFixtures([item("repair:retained")]),
    initial = fixtures["api/overview"];
  fixtures["api/overview"] = () => {
    reads++;
    if (reads > 1) throw Error("Synthetic refresh unavailable");
    return initial;
  };
  const app = await boot("overview", fixtures);
  try {
    const notice = app.document.querySelector("#notice");
    app.refresh();
    await until(() => /Refresh failed/.test(notice.textContent));
    const warning = notice.firstChild;
    app.refresh();
    await until(() => reads === 3);
    await tick();
    assert.equal(notice.firstChild, warning);
    notice.textContent =
      "Local attention status saved; source observation preserved.";
    const saved = notice.firstChild;
    app.refresh();
    await until(() => reads === 4);
    await tick();
    assert.equal(notice.firstChild, saved);
    assert.match(notice.textContent, /^Local attention status saved/);
  } finally {
    app.dom.window.close();
  }
});

test("long retained trace paths, strong labels and times receive the same non-clipping wrap contract", async () => {
  const selected = run({ outcome: "failed", error: "Timeout waiting" });
  const path = "action/0/" + "nested_sequence_".repeat(40);
  selected.evidence.steps[0].path = path;
  selected.configuration.nodes[0].path = path;
  const app = await boot("issues/case", {
    "api/cases/case": dossier("automation", selected),
  });
  try {
    const style = app.document.createElement("style");
    style.textContent = readFileSync(
      resolve(root, "vision/static/style.css"),
      "utf8",
    );
    app.document.head.append(style);
    for (const selector of [
      ".trace-path",
      ".observation-timeline time",
      ".observation-timeline strong",
    ]) {
      const element = app.document.querySelector(selector);
      assert.ok(element, selector);
      const computed = app.dom.window.getComputedStyle(element);
      assert.equal(computed.overflowWrap, "anywhere");
      assert.ok(!["hidden", "clip"].includes(computed.overflowX));
      assert.ok(!["hidden", "clip"].includes(computed.overflowY));
    }
    assert.equal(
      app.document.querySelector(".trace-path").textContent,
      path + " · observation 0",
    );
  } finally {
    app.dom.window.close();
  }
});

test("only the explicit published 0.2.0 overview shape uses legacy compatibility; malformed modern snapshots fail unknown", async () => {
  for (const shape of ["current-missing", "null", "malformed", "bad-counts"]) {
    const fixtures=overviewFixtures([]),data=fixtures["api/overview"];
    if(shape==="current-missing") data.health.version="0.2.1-dev.1";
    else data.reliability=shape==="null"?null:shape==="bad-counts"?{window:"24h",start:100,end:200,points:[],counts:{offline:0}}:{points:"not-an-array",counts:{}};
    const app=await boot("overview",fixtures);
    try {
      const text=app.document.querySelector("#content").textContent + app.document.querySelector("#notice").textContent;
      assert.match(text,/Device reliability snapshot unavailable/);
      assert.doesNotMatch(text,/No cases in the attention queue|0 device-hours/);
      assert.equal(app.calls.filter(call=>call.url.includes("cases?source=availability")).length,0);
    } finally {app.dom.window.close();}
  }
});
