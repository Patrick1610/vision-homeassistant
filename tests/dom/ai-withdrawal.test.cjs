"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { JSDOM } = require("jsdom");

// Execute the shipped HTML and complete application, including its real event
// handlers. All transport is synthetic; jsdom does not load external resources.
const root = resolve(__dirname, "../..");
const html = readFileSync(resolve(root, "vision/static/index.html"), "utf8");
const script = readFileSync(resolve(root, "vision/static/app.js"), "utf8");
const id = "a".repeat(32);
const frozenBody = '{"synthetic":"exact-reviewed-body"}';
const response = (data, ok = true) => ({ ok, json: async () => data });
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function until(predicate) {
  const deadline = performance.now() + 1000;
  while (!predicate()) {
    if (performance.now() >= deadline)
      assert.fail("Actual application did not reach the expected DOM state");
    // JSDOM queues history traversal through timers; a fast setImmediate loop
    // can exhaust a fixed iteration budget before those timer tasks execute.
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}
async function load({
  running = false,
  revokeError = false,
  pendingSend = null,
  conversation = false,
  rejectedSend = false,
  statusMode = "sending",
  initialStatus = "preview",
  initialAnalysis = null,
  completeAfterSend = false,
} = {}) {
  const dom = new JSDOM(html, {
    url: conversation
      ? "http://vision/#intelligence/?conversation=synthetic"
      : `http://vision/#intelligence/?request=${id}`,
    runScripts: "outside-only",
  });
  const calls = [];
  let statusReads = 0;
  dom.window.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url === "api/intelligence/conversations/synthetic")
      return response({
        rounds: [
          {
            request_id: id,
            round: 1,
            kind: "audit",
            profile: "compact",
            status: "completed",
            result: JSON.stringify({
              summary: "Original conclusion",
              diagnoses: [],
            }),
          },
          {
            request_id: "b".repeat(32),
            round: 2,
            kind: "audit",
            profile: "compact",
            status: "revoked",
            result: JSON.stringify({
              summary: "Withdrawn received conclusion",
              diagnoses: [],
            }),
          },
        ],
      });
    if (url === "api/health") return response({ connected: true });
    if (url === "api/intelligence/analyses/42")
      return response({
        id: 42,
        result: JSON.stringify({
          summary: "Finished after uncertain transport",
          diagnoses: [],
        }),
        evidence: "{}",
        can_continue: false,
      });
    if (url === "api/intelligence" && options.method === "POST") {
      if (rejectedSend)
        return response({ detail: "Synthetic send rejected" }, false);
      if (pendingSend) return pendingSend;
      return response({ request_id: id });
    }
    if (url === "api/intelligence")
      return response({
        enabled: true,
        running,
        privacy: "compact",
        tasks: { audit: { title: "Audit" } },
        analyses: [],
        usage: [],
      });
    if (url.endsWith("/revoke"))
      return revokeError
        ? response({ detail: "Synthetic withdrawal unavailable" }, false)
        : response({ revoked: true });
    if (url.endsWith("/status")) {
      statusReads++;
      if (statusMode === "unavailable")
        throw Error("Synthetic status unavailable");
      if (statusMode === "preview")
        return response({
          request_id: id,
          status: "preview",
          in_flight: false,
        });
      if (
        statusMode === "completed" ||
        (statusMode === "completion" && statusReads > 1)
      )
        return response({
          request_id: id,
          status: "completed",
          in_flight: false,
          analysis_id: 42,
        });
      return response({ request_id: id, status: "sending", in_flight: true });
    }
    if (url === `api/intelligence/requests/${id}`)
      return response({
        request_id: id,
        digest: "d".repeat(64),
        status: running
          ? "sending"
          : completeAfterSend &&
              calls.some(
                ({ url, options }) =>
                  url === "api/intelligence" && options.method === "POST",
              )
            ? "completed"
            : initialStatus,
        in_flight: running,
        error:
          initialStatus === "failed" ? "Synthetic safe failure reason" : null,
        analysis_id: completeAfterSend ? 42 : initialAnalysis,
        local_selection: {},
        local_mapping: {},
        local_aliases: {},
        preview: {
          round: 1,
          diagnostic_consent: false,
          task: "audit",
          profile: "compact",
          bundle: { captured_at: 1 },
          readiness: { supported: true },
          policy: { providers: { anthropic: { model: "synthetic" } } },
          requests: {
            anthropic: {
              url: "https://synthetic.invalid",
              body_utf8: frozenBody,
            },
          },
        },
      });
    throw Error(`Unmocked application request: ${url}`);
  };
  dom.window.eval(script);
  await until(() =>
    dom.window.document.querySelector(conversation ? "#ai-form" : "#revoke-ai"),
  );
  // bindIntelligence attaches the form listener after displaying the request.
  await tick();
  const document = dom.window.document;
  const edit = () => {
    const question = document.querySelector('[name="question"]');
    question.value += "Synthetic edit";
    question.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  };
  return {
    dom,
    document,
    calls,
    edit,
    revoked: () => calls.filter(({ url }) => url.endsWith("/revoke")).length,
    notice: () => document.querySelector("#notice").textContent,
  };
}

test("editing a running request keeps its exact request and requires explicit withdrawal", async () => {
  const app = await load({ running: true });
  try {
    const panel = app.document.querySelector("#ai-preview");
    app.edit();
    await tick();
    assert.equal(app.revoked(), 0);
    assert.match(app.notice(), /Use its Revoke button/);
    assert.equal(app.document.querySelector("#ai-preview"), panel);
    assert.ok(app.document.querySelector("#send-ai").disabled);
    app.document.querySelector("#revoke-ai").click();
    await until(
      () => app.revoked() === 1 && /Request revoked/.test(app.notice()),
    );
    assert.equal(app.revoked(), 1);
  } finally {
    app.dom.window.close();
  }
});

test("editing an unused preview revokes it and disables its old send control", async () => {
  const app = await load();
  try {
    assert.equal(app.document.querySelector("#send-ai").disabled, false);
    const button = app.document.querySelector("#send-ai");
    app.edit();
    assert.ok(button.disabled);
    await until(() =>
      /unused preview revoked/.test(
        app.document.querySelector("#ai-preview").textContent,
      ),
    );
    assert.equal(app.revoked(), 1);
    assert.equal(
      app.document.querySelector('[name="question"]').value,
      "Synthetic edit",
    );
    app.edit();
    await tick();
    assert.equal(app.revoked(), 1);
  } finally {
    app.dom.window.close();
  }
});

test("unused-preview withdrawal failures are visible with sending disabled", async () => {
  const app = await load({ revokeError: true });
  try {
    app.edit();
    await until(() => /Synthetic withdrawal unavailable/.test(app.notice()));
    assert.equal(app.revoked(), 1);
    assert.ok(app.document.querySelector("#send-ai").disabled);
    assert.ok(app.document.querySelector("#revoke-ai"));
    assert.match(app.notice(), /retry its explicit Revoke/);
  } finally {
    app.dom.window.close();
  }
});

test("pending send and a lost 202 response never turn a claimed job back into an unused preview", async () => {
  let rejectSend;
  const pendingSend = new Promise((_, reject) => {
    rejectSend = reject;
  });
  const app = await load({ pendingSend });
  try {
    app.document.querySelector("#send-ai").click();
    await until(() =>
      app.calls.some(
        ({ url, options }) =>
          url === "api/intelligence" && options.method === "POST",
      ),
    );
    app.edit();
    await tick();
    assert.equal(app.revoked(), 0);
    assert.match(app.notice(), /Use its Revoke button/);
    rejectSend(Error("Synthetic transport lost after server claim"));
    await until(() => app.calls.some(({ url }) => url.endsWith("/status")));
    app.edit();
    await tick();
    assert.equal(app.revoked(), 0);
    assert.ok(app.document.querySelector("#send-ai").disabled);
    assert.ok(app.document.querySelector("#revoke-ai"));
  } finally {
    app.dom.window.close();
  }
});

test("withdrawn received conversation rounds remain visible with continuations disabled", async () => {
  const app = await load({ conversation: true });
  try {
    assert.match(
      app.document.querySelector("#content").textContent,
      /Withdrawn; received result retained/,
    );
    assert.match(
      app.document.querySelector("#content").textContent,
      /Withdrawn received conclusion/,
    );
    assert.ok(
      app.document.querySelector('#ai-form button[type="submit"]').disabled,
    );
    assert.equal(
      app.calls.filter(({ options }) => options.method === "POST").length,
      0,
    );
  } finally {
    app.dom.window.close();
  }
});

test("a rejected send becomes reusable only after a light server-confirmed unused status", async () => {
  const app = await load({ rejectedSend: true, statusMode: "preview" });
  try {
    app.document.querySelector("#send-ai").click();
    await until(() =>
      /Server confirms this request is unused/.test(app.notice()),
    );
    assert.equal(app.document.querySelector("#send-ai").disabled, false);
    assert.equal(
      app.calls.filter(({ url }) => url.endsWith("/status")).length,
      1,
    );
    assert.equal(
      app.calls.filter(({ url }) => url === `api/intelligence/requests/${id}`)
        .length,
      1,
    );
    app.edit();
    await until(() => app.revoked() === 1);
  } finally {
    app.dom.window.close();
  }
});

test("a rejected send with unavailable status remains conservative during later edits", async () => {
  const app = await load({ rejectedSend: true, statusMode: "unavailable" });
  try {
    app.document.querySelector("#send-ai").click();
    await until(() =>
      /Server status could not be confirmed/.test(app.notice()),
    );
    assert.ok(app.document.querySelector("#send-ai").disabled);
    app.edit();
    await tick();
    assert.equal(app.revoked(), 0);
    assert.equal(
      app.calls.filter(({ url }) => url.endsWith("/status")).length,
      1,
    );
  } finally {
    app.dom.window.close();
  }
});

test("lost send response followed by running status watches completion without another send", async () => {
  const app = await load({ rejectedSend: true, statusMode: "completion" });
  try {
    app.document.querySelector("#send-ai").click();
    await until(() =>
      /Finished after uncertain transport/.test(
        app.document.querySelector("#content").textContent,
      ),
    );
    assert.equal(app.dom.window.location.hash, "#intelligence/?analysis=42");
    assert.equal(
      app.calls.filter(
        ({ url, options }) =>
          url === "api/intelligence" && options.method === "POST",
      ).length,
      1,
    );
    assert.equal(app.revoked(), 0);
  } finally {
    app.dom.window.close();
  }
});

test("fast completion before the first retained-request GET opens its analysis without polling or a second POST", async () => {
  const app = await load({ completeAfterSend: true });
  try {
    app.document.querySelector("#send-ai").click();
    await until(
      () => app.dom.window.location.hash === "#intelligence/?analysis=42",
    );
    await until(() =>
      /Finished after uncertain transport/.test(
        app.document.querySelector("#content").textContent,
      ),
    );
    assert.equal(
      app.calls.filter(({ url }) => url.endsWith("/status")).length,
      0,
    );
    assert.equal(
      app.calls.filter(
        ({ url, options }) =>
          url === "api/intelligence" && options.method === "POST",
      ).length,
      1,
    );
    app.dom.window.history.back();
    await until(
      () =>
        app.dom.window.location.hash === `#intelligence/?request=${id}` &&
        app.document.querySelector("#revoke-ai"),
    );
    await tick();
    assert.equal(app.dom.window.location.hash, `#intelligence/?request=${id}`);
    assert.ok(
      [...app.document.querySelectorAll("pre")].some(
        (node) => node.textContent === frozenBody,
      ),
    );
  } finally {
    app.dom.window.close();
  }
});

test("direct terminal reloads expose state and safe error, with withdrawn received results reachable", async () => {
  for (const status of ["failed", "uncertain", "revoked"]) {
    const app = await load({
      initialStatus: status,
      initialAnalysis: status === "revoked" ? 42 : null,
    });
    try {
      assert.match(app.notice(), new RegExp("Investigation status: " + status));
      assert.ok(app.document.querySelector("#send-ai").disabled);
      assert.equal(
        app.calls.filter(({ url }) => url.endsWith("/status")).length,
        0,
      );
      if (status === "failed")
        assert.match(app.notice(), /Synthetic safe failure reason/);
      if (status === "revoked") {
        assert.match(app.notice(), /withdrawn/);
        assert.equal(
          app.document.querySelector(".received-result a").hash,
          "#intelligence/?analysis=42",
        );
      }
    } finally {
      app.dom.window.close();
    }
  }
});

test("plain completed request links retain exact body, digest and consent without redirecting", async () => {
  const app = await load({ initialStatus: "completed", initialAnalysis: 42 });
  try {
    assert.equal(app.dom.window.location.hash, `#intelligence/?request=${id}`);
    assert.ok(
      [...app.document.querySelectorAll("pre")].some(
        (node) => node.textContent === frozenBody,
      ),
    );
    assert.ok(
      app.document
        .querySelector("#ai-preview")
        .textContent.includes("d".repeat(64)),
    );
    assert.ok(
      app.document
        .querySelector("#ai-preview")
        .textContent.includes('"diagnostic_consent": false'),
    );
    assert.equal(
      app.document.querySelector(".received-result a").textContent,
      "Open received analysis",
    );
    assert.equal(
      app.document.querySelector(".received-result a").hash,
      "#intelligence/?analysis=42",
    );
    assert.ok(app.document.querySelector("#send-ai").disabled);
    assert.equal(
      app.calls.filter(({ url }) => url.endsWith("/status")).length,
      0,
    );
    assert.equal(
      app.calls.filter(({ options }) => options.method === "POST").length,
      0,
    );
  } finally {
    app.dom.window.close();
  }
});

test("a plain running audit can finish polling while keeping its exact-request panel", async () => {
  const app = await load({ running: true, statusMode: "completed" });
  try {
    await until(() => app.document.querySelector(".received-result a"));
    assert.equal(app.dom.window.location.hash, `#intelligence/?request=${id}`);
    assert.ok(
      [...app.document.querySelectorAll("pre")].some(
        (node) => node.textContent === frozenBody,
      ),
    );
    assert.match(app.notice(), /Investigation status: completed/);
    assert.equal(
      app.calls.filter(({ options }) => options.method === "POST").length,
      0,
    );
  } finally {
    app.dom.window.close();
  }
});

test("lost POST response followed by completed status preserves the original audit entry on Back", async () => {
  const app = await load({ rejectedSend: true, statusMode: "completed" });
  try {
    const original = app.dom.window.location.hash;
    app.document.querySelector("#send-ai").click();
    await until(
      () => app.dom.window.location.hash === "#intelligence/?analysis=42",
    );
    await until(() =>
      /Finished after uncertain transport/.test(
        app.document.querySelector("#content").textContent,
      ),
    );
    assert.equal(
      app.calls.filter(({ url }) => url.endsWith("/status")).length,
      1,
    );
    app.dom.window.history.back();
    await until(
      () =>
        app.dom.window.location.hash === original &&
        app.document.querySelector("#revoke-ai"),
    );
    await tick();
    assert.equal(app.dom.window.location.hash, original);
    assert.ok(
      [...app.document.querySelectorAll("pre")].some(
        (node) => node.textContent === frozenBody,
      ),
    );
    assert.equal(
      app.calls.filter(
        ({ url, options }) =>
          url === "api/intelligence" && options.method === "POST",
      ).length,
      1,
    );
    assert.equal(app.revoked(), 0);
  } finally {
    app.dom.window.close();
  }
});
