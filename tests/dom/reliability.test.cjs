"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { JSDOM } = require("jsdom");
const root = resolve(__dirname, "../..");
const html = readFileSync(resolve(root, "vision/static/index.html"), "utf8");
const script = readFileSync(resolve(root, "vision/static/app.js"), "utf8");
const start = 1_000_000,
  end = start + 86400;
const response = (data) => ({ ok: true, json: async () => data });
async function until(predicate) {
  const deadline = performance.now() + 1500;
  while (!predicate()) {
    if (performance.now() >= deadline)
      assert.fail("Actual reliability UI did not reach expected DOM state");
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}
function metric(window = "24h") {
  return {
    window,
    start,
    end,
    coverage_start: start,
    as_of: end,
    reliable_now: true,
    device_hours: 12,
    known_device_hours: 72,
    unknown_device_hours: 4,
    covered_hours: 24,
    meaning: "Device-hours are interval unions clipped to coverage.",
    power_expectation: "Explicit local declarations only.",
    counts: { offline: 3, partial: 1, unknown: 2, excluded: 1, online: 4 },
    known_offline: 1,
    expected_offline: 1,
    inventory_coverage: { unmapped_entities: 7 },
    burden: { direction: "unknown", comparable_devices: 0 },
    trend: { uncompared_devices: 6 },
    points: [
      {
        start,
        end: start + 43200,
        coverage: 0.5,
        persistent: 1,
        new: 1,
        expected: 1,
        unknown: 2,
      },
      {
        start: start + 43200,
        end,
        coverage: 1,
        persistent: 1,
        new: 2,
        expected: 1,
        unknown: 0,
      },
    ],
    priorities: Array.from({ length: 4 }, (_, i) => ({
      key: "device-" + i,
      kind: "new_device",
      title: "<Lamp " + i + ">",
      impact: "Meaningful signals unavailable",
      manual_step: "Manually inspect power and expected sleep",
      validation: "Inspect later covered observations",
      href: "#devices/reliability?device=device-" + i,
    })),
    integrations: {
      total: 1,
      items: [
        {
          platform: "synthetic",
          devices: 4,
          offline: 3,
          points: [
            { start, end, offline: 0, unknown: 2, partial: 0, coverage: 1 },
          ],
        },
      ],
    },
  };
}
function device() {
  return {
    device_id: "device-0",
    name: "<Synthetic lamp>",
    state: "offline",
    attention: "review",
    power: "unknown",
    reliable_now: true,
    reason: "observed",
    evidence: {
      rule: "Only enabled primary signals establish offline evidence.",
      meaningful: 2,
      unavailable: 2,
      unknown: 0,
    },
    history: [
      {
        state: "offline",
        started: start,
        ended: null,
        attention: "review",
        reason: "observed",
      },
    ],
    checks: [],
    members: [
      {
        entity_id: "light.synthetic",
        role: "primary",
        availability: "unavailable",
      },
      {
        entity_id: "update.synthetic",
        role: "ancillary",
        availability: "unknown",
      },
    ],
    member_count: 2,
  };
}
async function load({
  hash = "#overview",
  empty = false,
  duration = null,
  countPeak = null,
  metricPatch = {},
  devicePatch = {},
  overviewPatch = {},
} = {}) {
  const dom = new JSDOM(html, {
    url: "http://vision/" + hash,
    runScripts: "outside-only",
  });
  const calls = [],
    value = Object.assign(device(), devicePatch);
  let interval;
  dom.window.setInterval = (callback) => {
    interval = callback;
    return 1;
  };
  dom.window.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url === "api/health")
      return response({ connected: true, read_only: true });
    if (url === "api/overview") {
      const m = metric();
      if (countPeak !== null)
        m.points[1] = {
          ...m.points[1],
          persistent: countPeak,
          new: 0,
          expected: 0,
        };
      if (duration !== null) {
        m.device_hours = duration;
        m.points = m.points.map((p) => ({
          ...p,
          persistent: 0,
          new: 0,
          expected: 0,
        }));
      }
      if (empty)
        Object.assign(m, {
          coverage_start: null,
          reliable_now: false,
          priorities: [],
          points: m.points.map((p) => ({
            ...p,
            coverage: 0,
            persistent: null,
            new: null,
            expected: null,
            unknown: null,
          })),
          device_hours: 0,
          counts: { offline: 0, unknown: 0, excluded: 0, partial: 0, online: 0 },
          integrations: { items: [], total: 0 },
        });
      Object.assign(m, metricPatch);
      return response({ reliability: m, ...overviewPatch });
    }
    if (url.startsWith("api/reliability?"))
      return response(
        metric(new URLSearchParams(url.split("?")[1]).get("window")),
      );
    if (url === "api/reliability/devices/device-0") return response(value);
    if (url.endsWith("/checks") || url.endsWith("/policy")) {
      const body = JSON.parse(options.body);
      if (url.endsWith("/checks"))
        value.checks.push({
          created: end,
          kind: body.kind,
          note: body.note,
          validation: "unknown",
          meaning: "Later observations only; not causation.",
        });
      else {
        Object.assign(value, body);
        value.policy = { ...value.policy, note: body.note };
        if (body.acknowledge_worsening) value.policy.worsened_at = null;
      }
      return response(value);
    }
    if (url.startsWith("api/reliability/devices?"))
      return response({
        items: [value],
        total: 1,
        page: 1,
        limit: 25,
        has_more: false,
        reliable_now: true,
      });
    if (url.startsWith("api/cases?"))
      return response({ items: [], total: 0, page: 1 });
    if (url.startsWith("api/history/page?")) return response({ items: [] });
    if (url === "api/devices") return response({ devices: [], entities: [{entity_id:"light.synthetic",name:"Synthetic",availability:"unavailable",device_id:"device-0",outages:{episodes:1,seconds:100}}] });
    if (url === "api/entities/light.synthetic/investigation") return response({cases:[],impact:{relations:[],affected_automations:[]}});
    if (url.startsWith("api/dependencies?")) return response({relations:[],affected_automations:[]});
    throw Error("Unexpected synthetic route: " + url);
  };
  dom.window.eval(script);
  await until(
    () => dom.window.document.querySelector("#content").children.length > 0,
  );
  return { dom, calls, value, refresh: () => interval() };
}

test("primary manual check precedes the mobile trend, with three priorities, one primary link and readable axes", async () => {
  const { dom } = await load();
  try {
    const doc = dom.window.document;
    assert.equal(doc.querySelectorAll(".priority-card").length, 3);
    assert.equal(
      doc.querySelectorAll("[data-primary-investigation]").length,
      1,
    );
    assert.ok(
      doc
        .querySelector(".reliability-next")
        .compareDocumentPosition(doc.querySelector(".device-chart")) &
        dom.window.Node.DOCUMENT_POSITION_FOLLOWING,
    );
    assert.equal(doc.querySelectorAll(".chart-scale span").length, 3);
    assert.equal(
      doc.querySelectorAll(".device-chart figcaption span").length,
      4,
    );
    assert.match(doc.querySelector(".chart-scale").textContent, /devices/);
    assert.match(
      doc.querySelector(".burden-narrative").textContent,
      /unknown|not comparable|not yet/i,
    );
    assert.match(doc.querySelector("h3").textContent, /<Lamp 0>/);
    assert.equal(doc.querySelector("main script"), null);
    const heat = doc.querySelector(".heatmap-row rect");
    assert.equal(heat.getAttribute("class"), "chart-gap"); // Unknown is not mint/healthy.
  } finally {
    dom.window.close();
  }
});

test("period selection loads the selected real window and preserves the chosen route", async () => {
  const { dom, calls } = await load();
  try {
    dom.window.document.querySelector('a[href="#overview/?window=7d"]').click();
    await until(() => calls.some((c) => c.url === "api/reliability?window=7d"));
    await until(
      () =>
        dom.window.document.querySelector('[aria-current="true"]')
          .textContent === "7d",
    );
    assert.equal(dom.window.location.hash, "#overview/?window=7d");
  } finally {
    dom.window.close();
  }
});

test("integration drilldown and device filters navigate only to the bounded local device API", async () => {
  const { dom, calls } = await load();
  try {
    dom.window.document.querySelector(".integration-heatmap").open = true;
    dom.window.document.querySelector(".heatmap-row a").click();
    await until(() => dom.window.document.querySelector("#device-filter"));
    assert.ok(
      calls.some(
        (c) =>
          c.url.includes("reliability/devices?") &&
          c.url.includes("platform=synthetic"),
      ),
    );
    const form = dom.window.document.querySelector("#device-filter");
    form.elements.state.value = "unknown";
    form.dispatchEvent(
      new dom.window.Event("submit", { bubbles: true, cancelable: true }),
    );
    await until(() =>
      calls.some(
        (c) =>
          c.url.includes("state=unknown") &&
          c.url.includes("platform=synthetic"),
      ),
    );
    assert.ok(dom.window.document.querySelector('a[href="#devices/entities"]'));
  } finally {
    dom.window.close();
  }
});

test("manual check and persistent policy save locally, retain escaped notes and show observation validation", async () => {
  const { dom, calls } = await load({
    hash: "#devices/reliability?device=device-0",
  });
  try {
    const doc = dom.window.document;
    const check = doc.querySelector("#device-check-form");
    check.elements.note.value = "<img src=x onerror=alert(1)>";
    check.dispatchEvent(
      new dom.window.Event("submit", { bubbles: true, cancelable: true }),
    );
    await until(() =>
      doc
        .querySelector(".observation-timeline")
        .textContent.includes("Manual check"),
    );
    assert.ok(
      doc
        .querySelector(".observation-timeline")
        .textContent.includes("<img src=x"),
    );
    assert.equal(doc.querySelector("main img"), null);
    assert.ok(
      doc
        .querySelector(".observation-timeline")
        .textContent.includes("unknown"),
    );
    const policy = doc.querySelector("#device-policy-form");
    policy.closest("details").open = true;
    policy.elements.attention.value = "known";
    policy.elements.power.value = "battery";
    policy.elements.note.value = "Durable local expectation";
    policy.dispatchEvent(
      new dom.window.Event("submit", { bubbles: true, cancelable: true }),
    );
    await until(() => calls.some((c) => c.url.endsWith("/policy")));
    await until(
      () =>
        doc.querySelector("#device-policy-form").elements.attention.value ===
        "known",
    );
    const posts = calls.filter((c) => c.options.method === "POST");
    assert.equal(posts.length, 2);
    assert.ok(
      posts.every(
        (c) =>
          c.url.startsWith("api/reliability/devices/device-0/") &&
          c.options.headers["X-Vision-Request"] === "1",
      ),
    );
    assert.equal(JSON.parse(posts[1].options.body).power, "battery");
    assert.match(doc.querySelector("#notice").textContent, /no HA action/);
  } finally {
    dom.window.close();
  }
});

test("no device history is explicit unknown coverage without a healthy score or invented trend", async () => {
  const { dom } = await load({ empty: true });
  try {
    const text = dom.window.document.querySelector("main").textContent;
    assert.match(text, /measurement has not started/i);
    assert.match(text, /no healthy-device claim/i);
    assert.equal(
      dom.window.document.querySelectorAll(
        ".series-new,.series-persistent,.series-expected",
      ).length,
      0,
    );
    assert.equal(
      dom.window.document.querySelectorAll(".priority-card").length,
      0,
    );
  } finally {
    dom.window.close();
  }
});

test("source archive defaults to all observations and does not present normal diagnostics as pending actions", async () => {
  const { dom, calls } = await load({ hash: "#issues" });
  try {
    const text = dom.window.document.querySelector("main").textContent;
    assert.match(text, /Retained source observations/);
    assert.match(text, /not automatically pending actions/);
    assert.ok(calls.some((c) => c.url === "api/cases?status=all"));
    assert.ok(dom.window.document.querySelector('a[href="#overview"]'));
  } finally {
    dom.window.close();
  }
});

test("new window background refresh retains open method evidence and focus", async () => {
  const { dom, calls, refresh } = await load({ hash: "#overview/?window=7d" });
  try {
    await until(() => dom.window.document.querySelector(".coverage-panel"));
    const panel = dom.window.document.querySelector(".coverage-panel");
    panel.open = true;
    const link = panel.querySelector("a");
    link.focus();
    const reads = calls.length;
    await refresh();
    assert.equal(dom.window.document.querySelector(".coverage-panel"), panel);
    assert.equal(dom.window.document.activeElement, link);
    assert.equal(calls.length, reads); // Existing engagement guard avoids a refresh entirely.
  } finally {
    dom.window.close();
  }
});

test("short between-bucket outages retain visible nonzero duration instead of rounding to zero hours", async () => {
  for (const [duration, expected] of [
    [0.01 / 3600, "less than 0.1 device-second"],
    [10 / 3600, "10 device-seconds"],
    [120 / 3600, "2 device-minutes"],
  ]) {
    const { dom } = await load({ duration });
    try {
      assert.ok(
        dom.window.document
          .querySelector(".context-strip")
          .textContent.includes(expected),
      );
      assert.ok(
        [
          ...dom.window.document.querySelectorAll(
            ".series-persistent,.series-new,.series-expected",
          ),
        ].every((rect) => rect.getAttribute("height") === "0"),
      );
    } finally {
      dom.window.close();
    }
  }
});

test("primary action is before chart and disclosures, while desktop has adjacent named grid areas", async () => {
  const { dom } = await load();
  try {
    const doc = dom.window.document,
      workspace = doc.querySelector(".reliability-workspace"),
      primary = doc.querySelector("[data-primary-investigation]");
    assert.equal(workspace.firstElementChild.className, "reliability-next");
    assert.ok(
      primary.compareDocumentPosition(
        primary.closest("article").querySelector("details"),
      ) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING,
    );
    const proof = doc.querySelector(".burden-proof");
    assert.equal(proof.open, false);
    assert.ok(doc.querySelector(".burden-signal").textContent.length < 130);
    const css = readFileSync(resolve(root, "vision/static/style.css"), "utf8");
    assert.match(css, /grid-template-areas:\s*"next trend"/);
    assert.match(css, /grid-template-areas:\s*"next" "trend"/);
    primary.click();
    await until(() => doc.querySelector("#device-check-form"));
    assert.equal(
      dom.window.location.hash,
      "#devices/reliability?device=device-0",
    );
  } finally {
    dom.window.close();
  }
});

test("an odd unavailable-device peak uses integer count-axis labels", async () => {
  const { dom } = await load({ countPeak: 5 });
  try {
    const labels = [
      ...dom.window.document.querySelectorAll(".chart-scale span"),
    ].map((n) => n.textContent);
    assert.deepEqual(labels, ["6 devices", "3", "0"]);
  } finally {
    dom.window.close();
  }
});


test("missing membership and fully-covered limited evidence are shaded unknown, while actual online membership is observed", async () => {
  for (const [observed, limited, expected] of [[0,false,"chart-gap"],[null,true,"chart-gap"],[1,false,"heatmap-observed"]]) {
    const m = metric();
    m.points = m.points.map(p => ({...p, coverage:1, observed, persistent:limited?null:0,new:limited?null:0,expected:limited?null:0,selection_limited:limited}));
    m.integrations.items[0].points = [{start,end,coverage:1,observed,offline:limited?null:0,unknown:0,partial:0,selection_limited:limited}];
    const {dom} = await load({metricPatch:m});
    try {
      const doc = dom.window.document;
      assert.equal(doc.querySelector(".heatmap-row rect").getAttribute("class"),expected);
      assert.equal(doc.querySelectorAll(".device-chart .chart-gap").length, observed===0||limited?2:0);
    } finally { dom.window.close(); }
  }
});

test("modern overview does not fetch dead entity counters and keeps monitoring gaps, trace coverage and audit links", async () => {
  const {dom,calls} = await load({overviewPatch:{last_gap:100, health:{last_sync:200,capabilities:{registry:"permission_unknown"},trace_detail_coverage:{pending:7}},local:{cases:{rule_coverage:{truncated:true,retained:20,omitted:500}}},latest_audit:{id:17,created:190,result:JSON.stringify({summary:"Retained audit"})}},metricPatch:{cache_state:"pending",cache_pending:true,cache_as_of:100,selection:{included_devices:2,excluded_devices:1,total_devices:3}}});
  try {
    const doc = dom.window.document;
    assert.equal(calls.filter(c=>c.url.startsWith("api/cases?")||c.url.startsWith("api/history/page?")).length,0);
    const panel = doc.querySelector(".monitoring-evidence");
    panel.open = true;
    assert.match(panel.textContent,/Last monitoring gap/);
    assert.match(panel.textContent,/500 additional checks omitted/);
    assert.match(panel.textContent,/permission_unknown/);
    assert.ok(panel.querySelector('a[href="#intelligence/?analysis=17"]'));
    assert.ok(panel.querySelector('a[href="#history/changes?outcome=changed"]'));
    assert.match(doc.querySelector("main").textContent,/updated snapshot is pending/);
    assert.match(doc.querySelector("main").textContent,/2 of 3 device histories/);
  } finally { dom.window.close(); }
});

test("note-only save never implies acknowledgement, while the explicit worsening button sends that action", async () => {
  const {dom,calls} = await load({hash:"#devices/reliability?device=device-0",devicePatch:{attention:"known",policy:{worsened_at:100,note:"Existing baseline"}}});
  try {
    let form = dom.window.document.querySelector("#device-policy-form");
    form.elements.note.value = "Only edit a note";
    form.dispatchEvent(new dom.window.SubmitEvent("submit",{bubbles:true,cancelable:true,submitter:form.querySelector("button")}));
    await until(()=>calls.some(c=>c.url.endsWith("/policy")));
    assert.equal(JSON.parse(calls.find(c=>c.url.endsWith("/policy")).options.body).acknowledge_worsening,undefined);
    await until(()=>dom.window.document.querySelector("#device-policy-form")!==form);
    form = dom.window.document.querySelector("#device-policy-form");
    const button = form.querySelector('button[name="acknowledge_worsening"]');
    assert.ok(button);
    form.dispatchEvent(new dom.window.SubmitEvent("submit",{bubbles:true,cancelable:true,submitter:button}));
    await until(()=>calls.filter(c=>c.url.endsWith("/policy")).length===2);
    assert.equal(JSON.parse(calls.filter(c=>c.url.endsWith("/policy"))[1].options.body).acknowledge_worsening,true);
  } finally { dom.window.close(); }
});

test("entity and dependency backlinks return to actual entity inventory, not the device reliability route", async () => {
  for (const hash of ["#devices/light.synthetic","#devices/device%3Asynthetic"]) {
    const {dom,calls} = await load({hash});
    try {
      const link=dom.window.document.querySelector('a[href="#devices/entities"]');
      assert.ok(link);
      link.click();
      await until(()=>dom.window.location.hash==="#devices/entities" && dom.window.document.querySelector('input[type="search"]'));
      assert.equal(calls.filter(c=>c.url.startsWith("api/reliability/devices?")).length,0);
    } finally { dom.window.close(); }
  }
});

test("real API note redaction survives SQLite and the shipped DOM without executing markup", async () => {
  const { execFileSync } = require("node:child_process");
  const { existsSync } = require("node:fs");
  const python = existsSync(resolve(root, ".venv/bin/python")) ? resolve(root,".venv/bin/python") : "python3";
  const program = `
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from vision.app import create_app
from vision.config import Settings
canaries=["secret-value-canary","auth-canary-123","private.invalid/canary","synthetic/canary","192.0.2.77","pw-canary","sk-syn-canary12345"]
note='<script>window.executed=true</script> {"token":"secret-value-canary"} Bearer auth-canary-123 https://private.invalid/canary '+'/'+'Users/synthetic/canary '+ '192.0.2.77 password="pw-canary" sk-syn-canary12345'
assert len(note)<300
with tempfile.TemporaryDirectory() as folder:
 app=create_app(SimpleNamespace(supervised=False,data=Path(folder),token=""),Settings(),connect=False)
 with TestClient(app,client=("127.0.0.1",123)) as client:
  monitor=app.state.monitor
  monitor.devices=[{"id":"device-0","name":"Synthetic"}]
  monitor.registry={"light.synthetic":{"device_id":"device-0","platform":"synthetic"}}
  monitor.observe_state({"entity_id":"light.synthetic","state":"unavailable"},100,track_device=False)
  monitor.reliability.refresh(100)
  headers={"x-vision-request":"1"}
  for suffix,body in [("checks",{"kind":"power","note":note}),("policy",{"attention":"known","note":note})]:
   result=client.post("/api/reliability/devices/device-0/"+suffix,json=body,headers=headers)
   assert result.status_code==200
  records={"checks":app.state.store.rows("SELECT note FROM device_checks"),"policy":app.state.store.rows("SELECT note FROM device_policies")}
  for canary in canaries:
   assert canary not in json.dumps(records) and canary not in result.text
  assert not app.state.store.rows("SELECT * FROM usage")
  print(json.dumps(result.json()))
`;
  const value = JSON.parse(execFileSync(python,["-c",program],{cwd:root,encoding:"utf8"}));
  const {dom} = await load({hash:"#devices/reliability?device=device-0",devicePatch:value});
  try {
    const doc=dom.window.document;
    assert.match(doc.querySelector(".observation-timeline").textContent, /\[REDACTED\]/);
    assert.match(doc.querySelector("main").textContent, /<script>window.executed=true<\/script>/);
    assert.equal(doc.querySelector("main script"),null);
    assert.equal(dom.window.executed,undefined);
    assert.ok(!doc.querySelector("main").textContent.includes("secret-value-canary"));
    assert.ok(!doc.querySelector("#device-policy-form").elements.note.value.includes("pw-canary"));
  } finally {dom.window.close();}
});



test("heatmap tooltip distinguishes no observations, bounded subsets and a genuinely observed zero", async () => {
  for (const point of [
    {observed:0,offline:0,coverage:1,unknown:0,partial:0},
    {observed:1,offline:0,coverage:1,unknown:0,partial:0},
    {observed:1,offline:0,coverage:1,unknown:0,partial:0,selection_limited:true},
    {observed:null,offline:null,coverage:0,unknown:null,partial:null},
  ]) {
    const m=metric();m.integrations.items[0].points=[{start,end,...point}];
    const {dom}=await load({metricPatch:m});
    try {
      const rect=dom.window.document.querySelector(".heatmap-row rect"),text=rect.querySelector("title").textContent;
      if (!point.observed) {
        assert.equal(rect.getAttribute("class"),"chart-gap");
        assert.match(text,/Unknown: no observed device membership/);
        assert.doesNotMatch(text,/0 unavailable devices/);
      } else if(point.selection_limited) {
        assert.equal(rect.getAttribute("class"),"chart-gap");
        assert.match(text,/subset only; omitted devices remain unknown/);
      } else {
        assert.equal(rect.getAttribute("class"),"heatmap-observed");
        assert.match(text,/0 unavailable devices/);
        assert.match(text,/1 observed devices/);
        assert.doesNotMatch(text,/no observed device membership/);
      }
    } finally {dom.window.close();}
  }
});

test("real API evidence timestamp reaches the DOM as detail recording, with no invented missing-date fallback", async () => {
  const {execFileSync}=require("node:child_process"),{existsSync}=require("node:fs");
  const python=existsSync(resolve(root,".venv/bin/python"))?resolve(root,".venv/bin/python"):"python3";
  const program=`
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from vision.app import create_app
from vision.config import Settings
from vision.reliability import DeviceReliability
with tempfile.TemporaryDirectory() as folder:
 app=create_app(SimpleNamespace(supervised=False,data=Path(folder),token=""),Settings(),connect=False)
 with TestClient(app,client=("127.0.0.1",123)) as client:
  monitor=app.state.monitor
  monitor.devices=[{"id":"device-0","name":"Synthetic"}]
  monitor.registry={"light.synthetic":{"device_id":"device-0","platform":"synthetic"}}
  monitor.observe_state({"entity_id":"light.synthetic","state":"unavailable"},100,track_device=False)
  monitor.reliability.refresh(100)
  monitor.reliability.refresh(200)
  valid=client.get("/api/reliability/devices/device-0").json()
  assert valid["evidence_at"]==100
  app.state.store.execute("UPDATE device_current SET payload=json_set(payload,'$.evidence_at',0)")
  monitor.reliability=DeviceReliability(monitor)
  zero=client.get("/api/reliability/devices/device-0").json()
  assert zero["evidence_at"]==0
  app.state.store.execute("UPDATE device_current SET payload=json_remove(payload,'$.evidence_at')")
  monitor.reliability=DeviceReliability(monitor)
  missing=client.get("/api/reliability/devices/device-0").json()
  assert missing["evidence_at"] is None and missing["started"]==100
  print(json.dumps([valid,zero,missing]))
`;
  const values=JSON.parse(execFileSync(python,["-c",program],{cwd:root,encoding:"utf8"}));
  for (const value of values) {
    const {dom}=await load({hash:"#devices/reliability?device=device-0",devicePatch:value});
    try {
      const text=dom.window.document.querySelector(".evidence-recorded-at").textContent;
      assert.match(text,/Evidence details last recorded:/);
      assert.doesNotMatch(text,/Current evidence observed/);
      if(value.evidence_at===null) assert.match(text,/Unknown \(no retained timestamp\)/);
      else {
        assert.ok(text.includes(new Date(value.evidence_at*1000).toLocaleString()));
        assert.ok(!text.includes(new Date(200*1000).toLocaleString()));
      }
    } finally {dom.window.close();}
  }
});

test("real API heatmap distinguishes absent historical membership, observed zero and a limited device subset", async () => {
  const {execFileSync}=require("node:child_process"),{existsSync}=require("node:fs");
  const python=existsSync(resolve(root,".venv/bin/python"))?resolve(root,".venv/bin/python"):"python3";
  const program=`
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from vision.app import create_app
from vision.config import Settings
import vision.reliability as reliability
with tempfile.TemporaryDirectory() as folder:
 app=create_app(SimpleNamespace(supervised=False,data=Path(folder),token=""),Settings(),connect=False)
 with TestClient(app,client=("127.0.0.1",123)) as client:
  monitor=app.state.monitor;service=monitor.reliability
  start=1000000;end=start+86400
  service.refresh(start)
  for index in range(2):
   device=f"device-{index}";entity=f"light.synthetic_{index}"
   monitor.devices.append({"id":device})
   monitor.registry[entity]={"device_id":device,"platform":"synthetic"}
   monitor.observe_state({"entity_id":entity,"state":"on"},end,track_device=False)
  service.refresh(end)
  empty=client.get("/api/reliability").json()
  assert empty["integrations"]["items"][0]["points"][-1]["observed"]==0
  assert empty["integrations"]["items"][0]["points"][-1]["coverage"]==1
  service.refresh(end+3600)
  healthy=client.get("/api/reliability").json()
  assert healthy["integrations"]["items"][0]["points"][-1]["observed"]==2
  reliability.MAX_INTERVALS=1
  service.build_cache(end+3600)
  limited=client.get("/api/reliability").json()
  assert limited["selection"]["included_devices"]==1 and limited["selection"]["excluded_devices"]==1
  print(json.dumps([empty,healthy,limited]))
`;
  const values=JSON.parse(execFileSync(python,["-c",program],{cwd:root,encoding:"utf8"}));
  for (let index=0;index<values.length;index++) {
    const {dom}=await load({metricPatch:values[index]});
    try {
      const cell=[...dom.window.document.querySelectorAll(".heatmap-row rect")].at(-1);
      const text=cell.querySelector("title").textContent;
      if(index===0) {
        assert.equal(cell.getAttribute("class"),"chart-gap");
        assert.match(text,/Unknown: no observed device membership/);
        assert.doesNotMatch(text,/0 unavailable devices/);
      } else if(index===1) {
        assert.equal(cell.getAttribute("class"),"heatmap-observed");
        assert.match(text,/0 unavailable devices/);
        assert.match(text,/2 observed devices/);
      } else {
        assert.equal(cell.getAttribute("class"),"chart-gap");
        assert.match(text,/subset only; omitted devices remain unknown/);
      }
    } finally {dom.window.close();}
  }
});

test("desktop visual and keyboard order put the primary manual action before the period controls", async () => {
  const {dom}=await load();
  try {
    const focusables=[...dom.window.document.querySelectorAll(".reliability-workspace a,.reliability-workspace button")];
    assert.equal(focusables[0].dataset.primaryInvestigation,"true");
    assert.ok(focusables.indexOf(dom.window.document.querySelector(".period-picker a"))>0);
    const css=readFileSync(resolve(root,"vision/static/style.css"),"utf8");
    assert.match(css,/grid-template-areas:\s*"next trend"/);
    assert.match(css,/grid-template-columns:\s*minmax\(270px, 1fr\) minmax\(0, 1\.4fr\)/);
  } finally {dom.window.close();}
});

test("blocked capacity shows real limits and earliest ordinary eligibility without promising resumption or new worsening proof", async () => {
  const {dom}=await load({metricPatch:{storage:{blocked:true,records:250000,row_limit:250000,bytes:134217728,encoded_byte_limit:134217728,remaining_rows:0,remaining_encoded_bytes:0,retention_days:90,earliest_retention_eligible_at:end+86400,retention_estimate_as_of:end}}});
  try {
    const doc=dom.window.document;
    const notice=[...doc.querySelectorAll(".coverage-note")].find(n=>n.textContent.startsWith("Device-history capacity reached:"));
    assert.ok(notice,"Blocked capacity needs its conditional warning, not only an always-present disclosure");
    const text=notice.textContent;
    assert.match(text,/250,?000 \/ 250,?000 intervals/);
    assert.match(text,/128 \/ 128 MiB encoded/);
    assert.match(text,/new worsening cannot be proved/);
    assert.match(text,/Earliest ordinary-retention eligibility after/);
    assert.match(text,/not a guaranteed resumption time/);
    assert.match(doc.querySelector(".history-capacity").textContent,/not a file-size limit/);
  } finally {dom.window.close();}
});

test("nonblocked history retains capacity details without a capacity-reached warning", async () => {
  const {dom}=await load({metricPatch:{storage:{blocked:false,records:1,row_limit:250000,bytes:1024,encoded_byte_limit:134217728,remaining_rows:249999,remaining_encoded_bytes:134216704,retention_days:90,earliest_retention_eligible_at:null,retention_estimate_as_of:end}}});
  try {
    const doc=dom.window.document;
    assert.ok(doc.querySelector(".history-capacity"));
    assert.ok(![...doc.querySelectorAll(".coverage-note")].some(n=>n.textContent.includes("Device-history capacity reached")));
    assert.doesNotMatch(doc.querySelector("main").textContent,/new worsening cannot be proved/);
  } finally {dom.window.close();}
});

test("burden states first-to-second halves of the selected window and discloses changed classification", async () => {
  const {dom}=await load({metricPatch:{burden:{direction:"increased",comparable_devices:8,total_devices:9,excluded_devices:1,before_device_hours:25,after_device_hours:27.5}}});
  try {
    const doc=dom.window.document;
    assert.match(doc.querySelector(".burden-signal").textContent,/First → second half: ↑ 25 device-hours → 27.5 device-hours/);
    assert.match(doc.querySelector(".burden-signal").textContent,/8\/9 comparable/);
    assert.match(doc.querySelector(".coverage-panel").textContent,/Changed membership or classification makes comparisons and manual-check validation unknown across that change/);
  } finally {dom.window.close();}
});

test("actual first capture failure preserves retained measurement start and renders unknown durations and coverage", async () => {
  const {execFileSync}=require("node:child_process"),{existsSync}=require("node:fs");
  const python=existsSync(resolve(root,".venv/bin/python"))?resolve(root,".venv/bin/python"):"python3";
  const program=`
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from vision.app import create_app
from vision.config import Settings
from vision.store import Store
import vision.reliability as reliability
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)
 store=Store(path/"vision.db")
 store.set_meta("device_measurement_started",1000000)
 store.close()
 capture=reliability.read_cache_input
 def missing(source,end,current):
  return capture(source.with_name("not-present.db"),end,current)
 reliability.read_cache_input=missing
 app=create_app(SimpleNamespace(supervised=False,data=path,token=""),Settings(),connect=False)
 with TestClient(app,client=("127.0.0.1",123)) as client:
  data=client.get("/api/reliability").json()
  assert data["coverage_start"]==1000000 and data["cache_state"]=="failed"
  assert data["device_hours"] is data["covered_hours"] is data["coverage_fraction"] is None
  print(json.dumps(data))
`;
  const value=JSON.parse(execFileSync(python,["-c",program],{cwd:root,encoding:"utf8"}));
  const {dom}=await load({metricPatch:value});
  try {
    const doc=dom.window.document,text=doc.querySelector("main").textContent;
    assert.match(text,/No chart snapshot is available/);
    assert.match(text,/Device measurement started/);
    assert.match(text,/Unknown monitored wall-hours/);
    assert.doesNotMatch(text,/measurement has not started|0 device-hours observed unavailable/);
    assert.equal(doc.querySelector(".context-strip strong").textContent,"Unknown device-hours");
    const titles=[...doc.querySelectorAll(".device-chart .chart-gap title")].map(n=>n.textContent);
    assert.ok(titles.length>0 && titles.every(t=>t.includes("Unknown monitoring coverage")));
    assert.ok(!titles.some(t=>/\b0% monitoring/.test(t)));
  } finally {dom.window.close();}
});
