"use strict";
// One explicit intent starts work. Reload/Back/poll only read its durable status.
window.VisionInvestigation = (() => {
  const active = new Set([
    "admitted",
    "preparing",
    "researching",
    "freezing",
    "sending",
  ]);
  const nl = () => document.documentElement.lang === "nl";
  const text = (en, dutch) => (nl() ? dutch : en);
  const escape = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const version = "vision-oneclick-compact-1";
  let timer = null;
  const label = (state) =>
    ({
      admitted: text("Admitted", "Opdracht bewaard"),
      preparing: text("Freezing local evidence", "Lokaal bewijs vastleggen"),
      researching: text(
        "Reading bounded public sources",
        "Begrensde openbare bronnen lezen",
      ),
      freezing: text("Freezing exact AI bodies", "Exact AI-verzoek vastleggen"),
      sending: text("AI investigation running", "AI-onderzoek loopt"),
      completed: text("Investigation received", "Onderzoek ontvangen"),
      revoked: text(
        "Withdrawn; transmitted usage remains",
        "Ingetrokken; verzonden gebruik blijft bewaard",
      ),
      interrupted: text(
        "Interrupted by restart; no automatic retry",
        "Onderbroken door herstart; geen automatische nieuwe poging",
      ),
      uncertain: text(
        "Interrupted; billing may be uncertain",
        "Onderbroken; kosten mogelijk onzeker",
      ),
      failed: text(
        "Investigation stopped; inspect retained evidence",
        "Onderzoek gestopt; bekijk het bewaarde bewijs",
      ),
    })[state] || text("Status unknown", "Status onbekend");
  const key = (id, pending = false) =>
    "vision.operation." + (pending ? "pending." : "") + id;
  function stored(id, pending = false) {
    try {
      return JSON.parse(localStorage.getItem(key(id, pending)) || "null");
    } catch {
      return null;
    }
  }
  function confirm(id, intent) {
    try {
      const current = stored(id),
        pending = stored(id, true);
      // A late response may not replace a newer other-tab confirmation.
      if (
        !current ||
        current.operation_id === intent.operation_id ||
        current.operation_id === intent.previous_confirmed_id
      )
        localStorage.setItem(key(id), JSON.stringify(intent));
      if (pending?.operation_id === intent.operation_id)
        localStorage.removeItem(key(id, true));
    } catch {
      // The durable pending ID and exact URL still permit status-only recovery.
    }
  }
  function ownsRoute(id, operation) {
    return (
      location.hash.split("?")[0] === "#problems/" + encodeURIComponent(id) &&
      new URLSearchParams(location.hash.split("?")[1] || "").get(
        "operation",
      ) === operation
    );
  }
  function remembered(id) {
    const route = new URLSearchParams(location.hash.split("?")[1] || "").get(
      "operation",
    );
    if (route) return route;
    return stored(id, true)?.operation_id || stored(id)?.operation_id;
  }
  function progress(row, context) {
    const running = active.has(row.status) || row.in_flight;
    return `<div id="home-operation" data-operation="${escape(row.operation_id)}" data-status="${escape(row.status)}"><p role="status"><strong>${escape(label(row.status))}</strong></p>${row.revision !== context?.revision ? `<p class="coverage-note">${escape(text("This retained investigation belongs to an earlier selection.", "Dit bewaarde onderzoek hoort bij een eerdere selectie."))}</p>` : ""}${row.error ? `<small>${escape(row.error)}</small>` : ""}<div class="home-actions">${running ? `<button id="home-operation-revoke">${escape(text("Withdraw further work", "Vervolgwerk intrekken"))}</button>` : ""}${row.final_request_id ? `<a href="#intelligence/?request=${encodeURIComponent(row.final_request_id)}">${escape(text("Inspect exact sent request", "Exact verzonden verzoek bekijken"))}</a>` : row.base_request_id ? `<a href="#intelligence/?request=${encodeURIComponent(row.base_request_id)}">${escape(text("Inspect frozen local base", "Bevroren lokale basis bekijken"))}</a>` : ""}<button id="home-operation-audit" class="quiet-button">${escape(text("Scope and public query plan", "Selectie en openbaar zoekplan"))}</button></div><div id="home-operation-audit-view"></div>${row.analysis_id ? `<div id="home-human-result"></div><p><a href="#intelligence/?analysis=${encodeURIComponent(row.analysis_id)}">${escape(text("Full retained analysis and original evidence", "Volledig bewaard onderzoek en oorspronkelijk bewijs"))}</a></p>` : ""}</div>`;
  }
  const startButton = () =>
    `<button id="home-investigate-start" class="primary">${escape(text("Investigate this problem", "Onderzoek dit probleem"))}</button>`;
  function manualLink(ctx) {
    const selection = ctx.selection,
      params = new URLSearchParams();
    params.set(
      "task",
      ["device", "device_group"].includes(selection.kind)
        ? "availability"
        : "incident",
    );
    if (selection.kind === "device") {
      params.set("target_type", "device");
      params.set("target", selection.device_id);
    }
    if (selection.kind === "device_group") {
      params.set("target_type", "group");
      params.set("target", ctx.problem_id);
    }
    if (selection.kind === "source_case")
      params.set("target", selection.case_key);
    if (selection.kind === "automation_run") {
      params.set("target", selection.entity_id);
      params.set("run_id", selection.run_id);
    }
    return "#intelligence/?" + params;
  }
  async function panel(id) {
    clearTimeout(timer);
    let current = null;
    const rememberedId = remembered(id),
      previousConfirmed = stored(id)?.operation_id || null,
      explicit = new URLSearchParams(location.hash.split("?")[1] || "").get(
        "operation",
      );
    try {
      const context = await api(
        "problems/" + encodeURIComponent(id) + "/investigation-context",
      );
      const operation =
        context.operation?.problem_id === id ? context.operation : null;
      if (operation)
        confirm(id, {
          operation_id: operation.operation_id,
          revision: operation.revision,
          language: operation.language,
          previous_confirmed_id: previousConfirmed,
        });
      const old = explicit || operation?.operation_id || rememberedId;
      let body = "";
      if (old) {
        try {
          current =
            operation?.operation_id === old
              ? operation
              : await api("home/investigations/" + encodeURIComponent(old));
          if (current.problem_id !== id) throw Error("Scope mismatch");
          const pending = stored(id, true);
          if (pending?.operation_id === old) confirm(id, pending);
          else if (!stored(id))
            // Another tab may have replaced/cleared pending before this lost-202
            // status read. Restore only a missing confirmation, never a newer one.
            confirm(id, {
              operation_id: old,
              revision: current.revision,
              language: current.language,
              previous_confirmed_id: null,
            });
          body = progress(current, context);
          if (
            !active.has(current.status) &&
            !current.in_flight &&
            context.consent.enabled &&
            context.outbound_enabled &&
            !context.busy
          )
            body += startButton();
        } catch {
          const pending = stored(id, true)?.operation_id === old;
          body = `<p class="coverage-note">${escape(
            pending
              ? text(
                  "Start is not confirmed. Only status was checked; nothing was restarted.",
                  "De start is niet bevestigd. Alleen de status is bekeken; niets is opnieuw gestart.",
                )
              : text(
                  "Saved operation is unavailable. No request was restarted. Inspect history or explicitly start a new investigation.",
                  "De bewaarde opdracht is niet beschikbaar. Er is niets opnieuw gestart. Bekijk de historie of start bewust een nieuw onderzoek.",
                ),
          )}</p>`;
          const confirmed = operation?.operation_id || stored(id)?.operation_id;
          if (confirmed && confirmed !== old) {
            try {
              const row =
                operation?.operation_id === confirmed
                  ? operation
                  : await api(
                      "home/investigations/" + encodeURIComponent(confirmed),
                    );
              if (row.problem_id === id) {
                current = row;
                body += progress(row, context);
              }
            } catch {
              /* Retain the unconfirmed intent; never dispatch a replacement. */
            }
          }
          if (
            !context.busy &&
            context.consent.enabled &&
            context.outbound_enabled &&
            context.selection_current !== false &&
            !current?.in_flight &&
            !active.has(current?.status)
          )
            body += startButton();
        }
      } else if (!context.consent.enabled) {
        body = `<p>${escape(text("One-click research needs its separate compact authorization.", "Eénklikonderzoek vereist afzonderlijke compacte toestemming."))} <a href="#settings">${escape(text("Review authorization", "Toestemming bekijken"))}</a></p>`;
      } else if (
        !context.outbound_enabled ||
        context.busy ||
        context.selection_current === false
      ) {
        body = `<p class="coverage-note">${escape(text("AI is disabled/local-only, this selection needs fresh coverage, or another investigation is running. Local checks remain available.", "AI staat uit/lokaal, deze selectie mist verse dekking of een ander onderzoek loopt. Lokale controles blijven beschikbaar."))}</p>`;
      } else body = startButton();
      if (
        explicit &&
        operation &&
        explicit !== operation.operation_id &&
        (active.has(operation.status) || operation.in_flight)
      )
        body += `<p role="status" class="coverage-note">${escape(text("Another investigation for this problem is active.", "Een ander onderzoek voor dit probleem loopt."))} <a class="current-investigation" href="#problems/${encodeURIComponent(id)}?operation=${encodeURIComponent(operation.operation_id)}">${escape(text("Open current investigation / withdraw further work", "Huidig onderzoek openen / vervolgwerk intrekken"))}</a></p>`;
      return `<section class="card home-investigation" data-problem="${escape(id)}" data-context="${escape(JSON.stringify(context))}" data-state="${escape(JSON.stringify(current))}"><h3>${escape(text("A concrete manual solution", "Een concrete handmatige oplossing"))}</h3><p>${escape(text("Local evidence → bounded public sources → one compact AI proposal. You perform every action yourself.", "Lokaal bewijs → begrensde openbare bronnen → één compact AI-voorstel. Je voert iedere handeling zelf uit."))}</p>${body}<p><a href="${escape(manualLink(context))}">${escape(text("Or inspect an exact manual preview", "Of bekijk vooraf een exact handmatig verzoek"))}</a></p></section>`;
    } catch {
      return `<p class="coverage-note">${escape(text("Research context unavailable; no work started. Local evidence and manual checks remain available.", "Onderzoekscontext niet beschikbaar; niets gestart. Lokaal bewijs en handmatige controles blijven beschikbaar."))}</p>`;
    }
  }
  async function settings() {
    try {
      const c = await api("home/investigation-consent");
      return `<section class="card"><h2>${escape(text("Compact one-click investigations", "Compact éénklikonderzoek"))}</h2><p>${escape(text("Each explicit click authorizes a frozen selected problem, at most six generic public GETs/30 seconds and one AI round. Providers, prices, budgets and technical retry/failover rules remain as configured below. Costs after transmission can remain uncertain. Friendly names, rooms and personal notes stay local. This is policy authorization; exact bodies can be inspected afterwards or via the separate manual preview route before sending. Diagnostic always needs fresh manual review.", "Iedere bewuste klik machtigt één vastgelegd probleem, maximaal zes generieke openbare GETs/30 seconden en één AI-ronde. Providers, prijzen, budgetten en technische uitwijkregels blijven zoals hieronder ingesteld. Kosten na verzending kunnen onzeker blijven. Namen, ruimtes en persoonlijke notities blijven lokaal. Dit is beleidstoestemming; exacte verzoeken zijn achteraf te bekijken of vooraf via de aparte handmatige previewroute. Diagnostische verzending vereist altijd een nieuwe handmatige controle."))}</p><form id="home-ai-consent"><label class="check-label"><input type="checkbox" name="enabled" ${c.enabled ? "checked" : ""}>${escape(text("Authorize compact one-click research (version 1)", "Compact éénklikonderzoek toestaan (versie 1)"))}</label><button type="submit">${escape(text("Save authorization in Vision", "Toestemming in Vision bewaren"))}</button></form></section>`;
    } catch {
      return `<p class="coverage-note">${escape(text("Investigation authorization is unavailable; nothing is enabled.", "Onderzoekstoestemming is niet beschikbaar; er wordt niets aangezet."))}</p>`;
    }
  }
  function results(analysis) {
    const result =
      (typeof analysis.result === "string"
        ? JSON.parse(analysis.result)
        : analysis.result) || {};
    const render = (item) =>
      `<article class="finding-card"><span class="overline">${escape(text("AI proposal · not proven cause", "AI-voorstel · geen bewezen oorzaak"))}</span><h3>${escape(item.title)}</h3><p>${escape(item.core_explanation)}</p><h4>${escape(text("Your next manual check", "Je eerstvolgende handmatige controle"))}</h4><p>${escape(item.next_check)}</p>${item.manual_plan ? `<details class="human-manual-plan"><summary>${escape(text("Full manual plan", "Volledig handmatig plan"))} (${item.manual_plan.steps.length})</summary>${item.manual_plan.prerequisites.length ? `<ul>${item.manual_plan.prerequisites.map((p) => `<li>${escape(p)}</li>`).join("")}</ul>` : ""}<ol>${item.manual_plan.steps.map((step) => `<li>${escape(step.instruction)} <small>${escape(step.source_refs.join(", "))}</small></li>`).join("")}</ol></details>` : ""}<details class="human-validation"><summary>${escape(text("How to validate", "Zo controleer je het resultaat"))}</summary><p>${escape(item.validation)}</p></details><details><summary>${escape(text("Evidence, uncertainty and full explanation", "Bewijs, onzekerheid en volledige uitleg"))}</summary><p>${escape(item.finding)}</p><p>${escape(item.uncertainty)}</p><p>${escape(item.evidence.join(", "))}</p><p>${escape(item.counter_evidence.join(", "))}</p><ul>${item.unknowns.map((v) => `<li>${escape(v)}</li>`).join("")}</ul></details></article>`;
    const entries = Array.isArray(result.diagnoses) ? result.diagnoses : [];
    return `<div class="human-findings"><small>${escape(text("Requested answer language", "Gevraagde antwoordtaal"))}: ${escape((typeof analysis.evidence === "string" ? JSON.parse(analysis.evidence) : analysis.evidence)?.language || analysis.language || "unknown")}</small><div class="finding-grid">${entries.slice(0, 3).map(render).join("")}</div>${entries.length > 3 ? `<details><summary>${escape(text("More retained proposals", "Meer bewaarde voorstellen"))} (${entries.length - 3})</summary>${entries.slice(3).map(render).join("")}</details>` : ""}${!entries.length ? `<p>${escape(text("No supported finding; inspect the unknowns.", "Geen ondersteunde bevinding; bekijk de onbekenden."))}</p>` : ""}<details><summary>${escape(text("Overall unknowns and original summary", "Overige onbekenden en oorspronkelijke samenvatting"))}</summary><p>${escape(result.summary)}</p><ul>${(result.unknowns || []).map((v) => `<li>${escape(v)}</li>`).join("")}</ul></details></div>`;
  }
  async function show(row, section) {
    if (!section.isConnected) return;
    const host = section.querySelector("#home-operation");
    if (
      host &&
      (host.dataset.status !== row.status ||
        (row.analysis_id && !host.querySelector("#home-human-result")))
    ) {
      const audit = host.querySelector("#home-operation-audit-view"),
        focused = document.activeElement;
      host.outerHTML = progress(row, JSON.parse(section.dataset.context));
      if (audit)
        section.querySelector("#home-operation-audit-view")?.replaceWith(audit);
      if (focused?.id)
        section.querySelector("#" + focused.id)?.focus({ preventScroll: true });
    }
    if (row.analysis_id) {
      const analysis = await api("intelligence/analyses/" + row.analysis_id);
      const output = section.querySelector("#home-human-result");
      if (output)
        output.innerHTML =
          results(analysis) +
          `<details><summary>${escape(text("Retained public passages", "Bewaarde openbare passages"))}</summary>${researchView(JSON.parse(analysis.evidence).research)}</details>`;
    }
    bindOperation(section, row);
    if (active.has(row.status) || row.in_flight)
      timer = setTimeout(async () => {
        if (!section.isConnected) return;
        try {
          const fresh = await api(
            "home/investigations/" + encodeURIComponent(row.operation_id),
          );
          await show(fresh, section);
        } catch {
          if (section.isConnected)
            notice.textContent = text(
              "Status unavailable; no new request started.",
              "Status niet beschikbaar; geen nieuw verzoek gestart.",
            );
        }
      }, 750);
  }
  function bindOperation(section, row) {
    const host = section.querySelector("#home-operation");
    if (!host || host.dataset.bound) return;
    host.dataset.bound = "true";
    section
      .querySelector("#home-operation-revoke")
      ?.addEventListener("click", async () => {
        try {
          await show(
            await api(
              "home/investigations/" +
                encodeURIComponent(row.operation_id) +
                "/revoke",
              { method: "POST" },
            ),
            section,
          );
        } catch {
          notice.textContent = text(
            "Withdrawal could not be confirmed; inspect status.",
            "Intrekking niet bevestigd; bekijk de status.",
          );
        }
      });
    section
      .querySelector("#home-operation-audit")
      ?.addEventListener("click", async () => {
        try {
          const value = await api(
            "home/investigations/" +
              encodeURIComponent(row.operation_id) +
              "/audit",
          );
          const target = section.querySelector("#home-operation-audit-view");
          if (target)
            target.innerHTML = `<details open><summary>${escape(value.authorization_mode)}</summary><pre>${escape(JSON.stringify({ scope: value.scope, plan: value.plan }, null, 2))}</pre></details>`;
        } catch {
          notice.textContent = text(
            "Audit unavailable.",
            "Bewijs niet beschikbaar.",
          );
        }
      });
  }
  function bind() {
    const form = document.querySelector("#home-ai-consent");
    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("home/investigation-consent", {
          method: "POST",
          body: JSON.stringify({
            version,
            enabled: form.elements.enabled.checked,
          }),
        });
        notice.textContent = text(
          "Authorization saved in Vision.",
          "Toestemming in Vision bewaard.",
        );
      } catch {
        notice.textContent = text(
          "Authorization was not saved.",
          "Toestemming is niet bewaard.",
        );
      }
    });
    const section = document.querySelector(".home-investigation");
    if (!section) return;
    const ctx = JSON.parse(section.dataset.context),
      current = JSON.parse(section.dataset.state);
    if (ctx.problem_id !== section.dataset.problem) return;
    if (current)
      show(current, section).catch(() => {
        notice.textContent = text(
          "Result unavailable; inspect history.",
          "Resultaat niet beschikbaar; bekijk de historie.",
        );
      });
    section
      .querySelector("#home-investigate-start")
      ?.addEventListener("click", async (e) => {
        const button = e.currentTarget;
        button.disabled = true;
        let dispatched = false,
          rejected = false;
        try {
          const nonce = [...crypto.getRandomValues(new Uint8Array(16))]
            .map((n) => n.toString(16).padStart(2, "0"))
            .join("");
          const value = {
            operation_id: `op1_${ctx.slot}_${nonce}`,
            revision: ctx.revision,
            language: ctx.language || (nl() ? "nl" : "en"),
          };
          const priorHash = location.hash,
            intent = {
              ...value,
              previous_confirmed_id:
                stored(ctx.problem_id)?.operation_id || null,
            };
          // Persist before HTTP. Storage failure must not dispatch an untrackable job.
          localStorage.setItem(
            key(ctx.problem_id, true),
            JSON.stringify(intent),
          );
          window.history.replaceState(
            null,
            "",
            `#problems/${encodeURIComponent(ctx.problem_id)}?operation=${encodeURIComponent(value.operation_id)}`,
          );
          let refreshRoute = false;
          try {
            dispatched = true;
            const accepted = await api(
              "problems/" + encodeURIComponent(ctx.problem_id) + "/investigate",
              { method: "POST", body: JSON.stringify(value) },
            );
            if (
              accepted.operation_id === value.operation_id &&
              accepted.problem_id === ctx.problem_id
            )
              confirm(ctx.problem_id, intent);
            refreshRoute = ownsRoute(ctx.problem_id, value.operation_id);
          } catch (error) {
            refreshRoute = ownsRoute(ctx.problem_id, value.operation_id);
            if (error.status >= 400 && error.status < 500) {
              rejected = true;
              if (
                stored(ctx.problem_id, true)?.operation_id ===
                value.operation_id
              )
                localStorage.removeItem(key(ctx.problem_id, true));
              if (refreshRoute) {
                const confirmed = stored(ctx.problem_id)?.operation_id;
                window.history.replaceState(
                  null,
                  "",
                  confirmed
                    ? `#problems/${encodeURIComponent(ctx.problem_id)}?operation=${encodeURIComponent(confirmed)}`
                    : priorHash,
                );
              }
            }
            if (refreshRoute)
              notice.textContent =
                error.message +
                " · " +
                text(
                  error.status >= 400 && error.status < 500
                    ? "Start rejected; no operation admitted. A new attempt needs an explicit click."
                    : "Status lookup only; no automatic restart.",
                  error.status >= 400 && error.status < 500
                    ? "Start afgewezen; geen opdracht aangenomen. Een nieuwe poging vereist een bewuste klik."
                    : "Alleen statuscontrole; geen automatische herstart.",
                );
          }
          if (refreshRoute) render();
        } catch {
          button.disabled = false;
          if (
            !section.isConnected ||
            location.hash.split("?")[0] !==
              "#problems/" + encodeURIComponent(ctx.problem_id)
          )
            return;
          notice.textContent = dispatched
            ? text(
                (rejected
                  ? "Start rejected; no new operation admitted. "
                  : "") + "Status lookup only; no automatic restart.",
                (rejected
                  ? "Start afgewezen; geen nieuwe opdracht aangenomen. "
                  : "") + "Alleen statuscontrole; geen automatische herstart.",
              )
            : text(
                "Could not save a secure operation identifier; no work started.",
                "Veilige opdracht-ID niet bewaard; niets gestart.",
              );
          if (dispatched) render();
        }
      });
  }
  return { panel, settings, results, bind };
})();
