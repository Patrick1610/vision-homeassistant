"use strict";
// Presentation-only locale and local drafts. Historical AI prose is never rewritten.
window.VisionHome = (() => {
  const strings = {
    en: {
      Today: "Today",
      Problems: "Problems",
      Devices: "Devices",
      History: "History",
      Settings: "Settings",
      Overview: "Technical overview",
      Automations: "Automations",
      Issues: "Source cases",
      Intelligence: "Expert research",
      Intake: "Your preferences",
      expert: "Expert views",
      tagline: "A reliable home, with less effort.",
      skip: "Skip to content",
      readonly: "Read only",
      language: "Language",
      auto: "Browser language",
      attention: "Something needs your attention",
      quiet: "No new attention needed",
      limited: "Not enough visibility yet",
      quietNote:
        "This means no demonstrated new priority, not that every device is healthy.",
      limitedNote:
        "Current coverage is incomplete. Inspect retained observations before drawing a conclusion.",
      coverageCheck:
        "Check whether Vision is connected and receiving recent observations.",
      coverageOpen: "Inspect monitoring coverage",
      intro:
        "Start with one check. Vision observes; you perform any action yourself.",
      personalize: "Make Vision yours",
      preferences: "Your preferences",
      later: "Later",
      open: "Understand this problem",
      view: "View problem",
      viewDevice: "View device evidence",
      unnamed: "Unnamed device",
      unknownRoom: "Room unknown",
      group: "devices changed",
      correlation:
        "Covered observations close together; shared cause is unproven.",
      offline: "Unavailable signals",
      partial: "Partly unavailable",
      unknown: "Unknown",
      online: "Available signals",
      step_errors: "Observed execution step errors",
      source_failure: "Source reports a failure",
      high: "Important to me",
      normal: "Normal importance",
      low: "Lower importance",
      new: "Observed change",
      persistent: "Persistent observation",
      proven: "What was observed",
      why: "Why it matters",
      plan: "Your first manual check",
      powerCheck:
        "Check whether this device should be active, then inspect its power and integration manually.",
      partialCheck:
        "Compare the unavailable function with a working function on this device before changing anything.",
      groupCheck:
        "Compare one affected device with a healthy counterpart; the cause is unknown.",
      sourceCheck:
        "Open the retained source and inspect the actual failure before choosing a change.",
      sourceOpen: "Open retained source evidence",
      relevance:
        "Relevance is based on your importance choice and declared links. Physical impact is not guaranteed.",
      validation: "How to check the result",
      validate:
        "Return to later covered observations of the same device and membership. Your report does not prove recovery or a cause.",
      feedback: "What happened when you checked?",
      observed_recovery: "Observed recovery",
      still_offline: "Still unavailable",
      still_partial: "Still partly unavailable",
      checked: "I performed a check",
      no_change: "No change",
      seems_recovered: "Seems recovered to me",
      note: "Optional note (local only)",
      saveFeedback: "Record my feedback",
      saved: "Saved in Vision. Home Assistant was not changed.",
      reported: "Your report",
      observed: "Later observations",
      noReport: "No local feedback yet.",
      earlierReports: "Reports from earlier episodes",
      check_capacity:
        "Report saved; check history is full, so no observation marker was created.",
      device_not_retained:
        "Report saved; this device is no longer in the retained cohort, so no observation marker was created.",
      memberUnknown:
        "Some earlier member details are no longer retained for this episode.",
      concentrations: "Integration observations",
      correlationShort: "Observed together; cause unknown.",
      snapshot: "Retained snapshot",
      snapshotDevices: "devices in this snapshot",
      unassessed: "unassessed",
      currentUnknown: "Current availability is unknown",
      snapshotPending: "Snapshot is updating",
      snapshotFailed: "Snapshot refresh failed",
      noObserved: "No covered later result yet.",
      factUnknown: "Cause remains unknown.",
      stale:
        "This retained problem is no longer in the current queue. Removal or missing observations do not prove recovery.",
      evidence: "Evidence and limitations",
      members: "Affected and contrary evidence",
      omitted: "Additional members omitted",
      gaps: "Coverage gaps",
      noGap:
        "No gap in the bounded retained selection; earlier coverage can still be unknown.",
      importance: "Importance to you",
      known: "I know about this issue",
      usual: "This behaviour is usual for me",
      independent:
        "These choices are independent. Saving them does not acknowledge worsening or change an existing policy baseline.",
      savePreference: "Save my choices",
      ack: "Explicitly acknowledge this worsening",
      ackNote:
        "This separate action updates only your local presentation baseline.",
      knownBacklog: "Known or usual backlog remains visible",
      backlog: "Known / usual observations",
      all: "All observations",
      attentionFilter: "Current attention",
      empty: "No demonstrated problem in this selection.",
      openHistory: "Inspect retained history",
      technical: "Technical details",
      impact: "Declared dependencies (possible impact)",
      noImpact:
        "No retained declared dependency is available; physical impact is unknown.",
      healthy: "Healthy counterevidence",
      time: "Observations as of",
      sourceFreshness:
        "Device detail recording is separate from monitoring freshness.",
      trace: "Observed timeline",
      burden: "Outage burden · first → second half",
      comparisonUnknown: "Comparable outage burden is unknown.",
      comparable: "comparable",
      excluded: "excluded",
      trend: "Device observations",
      method: "Coverage and calculation details",
      recent: "Current observed state",
      pending:
        "Local presentation is updating; the last coherent observation time remains visible.",
      capacity:
        "Local presentation capacity is limited; omitted cases are not a healthy result.",
      intake: "What matters in your home?",
      intakeIntro:
        "Optional: choose important devices and known or usual behaviour. Existing choices are prefilled. Nothing changes until you save.",
      intakeStep: "Choose devices · keep your history",
      complete: "Save and finish",
      draft: "Save for later",
      cancel: "Cancel without saving",
      skipIntake: "Skip for now",
      search: "Search friendly names or rooms",
      next: "Next page",
      previous: "Previous page",
      edit: "Adjust gradually in each problem",
      locale: "Interface language",
      noDevice:
        "No registered devices observed yet. Intake can be resumed later.",
      userOnly: "Subjective feedback · stored locally",
      unknownCount:
        "Unknown members remain unknown; diagnostic or disabled members do not establish device failure.",
      rooms: "Room display coverage",
      retained: "Retained expert evidence",
      changedCohort:
        "Gaps, changed membership and removal prevent a recovery conclusion.",
      ackConfirm:
        "Acknowledge the newly observed worsening? This is separate from importance and intake.",
      selectionCap: "Save at most 100 device edits at a time.",
      sourceState: "Retained source state",
      more: "More observations",
      noHealth: "No general home-health score is inferred.",
      intakeSaved:
        "Preferences saved. Existing history and policy baselines were preserved.",
    },
    nl: {
      Today: "Vandaag",
      Problems: "Problemen",
      Devices: "Apparaten",
      History: "Historie",
      Settings: "Instellingen",
      Overview: "Technisch overzicht",
      Automations: "Automatiseringen",
      Issues: "Bronmeldingen",
      Intelligence: "Verdiepend onderzoek",
      Intake: "Jouw voorkeuren",
      expert: "Expertweergaven",
      tagline: "Een betrouwbaar huis, met minder moeite.",
      skip: "Ga naar inhoud",
      readonly: "Alleen lezen",
      language: "Taal",
      auto: "Browsertaal",
      attention: "Dit vraagt je aandacht",
      quiet: "Geen nieuwe aandacht nodig",
      limited: "Nog onvoldoende zicht",
      quietNote:
        "Er is geen nieuwe onderbouwde prioriteit. Dat betekent niet dat elk apparaat gezond is.",
      limitedNote:
        "De actuele dekking is onvolledig. Bekijk bewaarde waarnemingen voordat je conclusies trekt.",
      coverageCheck:
        "Controleer of Vision verbonden is en recente waarnemingen ontvangt.",
      coverageOpen: "Bekijk de meetdekking",
      intro:
        "Begin met één controle. Vision kijkt mee; je voert handelingen zelf uit.",
      personalize: "Maak Vision persoonlijk",
      preferences: "Jouw voorkeuren",
      later: "Later",
      open: "Begrijp dit probleem",
      view: "Bekijk probleem",
      viewDevice: "Bekijk apparaatbewijs",
      unnamed: "Apparaat zonder naam",
      unknownRoom: "Ruimte onbekend",
      group: "apparaten veranderd",
      correlation:
        "Gedekte waarnemingen kort na elkaar; een gezamenlijke oorzaak is niet bewezen.",
      offline: "Signalen niet beschikbaar",
      partial: "Deels niet beschikbaar",
      unknown: "Onbekend",
      online: "Signalen beschikbaar",
      step_errors: "Fouten in een uitvoeringsstap waargenomen",
      source_failure: "De bron meldt een fout",
      high: "Belangrijk voor mij",
      normal: "Normaal belang",
      low: "Minder belangrijk",
      new: "Waargenomen verandering",
      persistent: "Aanhoudende waarneming",
      proven: "Wat is waargenomen",
      why: "Waarom dit relevant is",
      plan: "Je eerste handmatige controle",
      powerCheck:
        "Controleer of dit apparaat actief hoort te zijn. Bekijk daarna zelf de voeding en integratie.",
      partialCheck:
        "Vergelijk de niet-beschikbare functie met een werkende functie op dit apparaat voordat je iets wijzigt.",
      groupCheck:
        "Vergelijk één betrokken apparaat met een gezond voorbeeld; de oorzaak is onbekend.",
      sourceCheck:
        "Open het bewaarde bronbewijs en bekijk de werkelijke fout voordat je een wijziging kiest.",
      sourceOpen: "Open bewaard bronbewijs",
      relevance:
        "Relevantie volgt uit jouw belangkeuze en expliciete koppelingen. Fysieke gevolgen zijn niet gegarandeerd.",
      validation: "Hoe controleer je het resultaat",
      validate:
        "Bekijk latere gedekte waarnemingen van hetzelfde apparaat en dezelfde leden. Jouw melding bewijst geen herstel of oorzaak.",
      feedback: "Wat zag je na jouw controle?",
      observed_recovery: "Herstel waargenomen",
      still_offline: "Nog niet beschikbaar",
      still_partial: "Nog deels niet beschikbaar",
      checked: "Ik heb een controle uitgevoerd",
      no_change: "Geen verandering",
      seems_recovered: "Lijkt mij hersteld",
      note: "Optionele notitie (alleen lokaal)",
      saveFeedback: "Bewaar mijn terugkoppeling",
      saved: "Bewaard in Vision. Home Assistant is niet gewijzigd.",
      reported: "Jouw melding",
      observed: "Latere waarnemingen",
      noReport: "Nog geen lokale terugkoppeling.",
      earlierReports: "Meldingen bij eerdere periodes",
      check_capacity:
        "Melding bewaard; de controlehistorie is vol, dus er is geen waarnemingsmarker gemaakt.",
      device_not_retained:
        "Melding bewaard; dit apparaat zit niet meer in het bewaarde cohort, dus er is geen waarnemingsmarker gemaakt.",
      memberUnknown:
        "Sommige eerdere apparaatdetails zijn niet meer bewaard voor deze periode.",
      concentrations: "Integratiewaarnemingen",
      correlationShort: "Samen waargenomen; oorzaak onbekend.",
      snapshot: "Bewaarde momentopname",
      snapshotDevices: "apparaten in deze momentopname",
      unassessed: "niet beoordeeld",
      currentUnknown: "Actuele beschikbaarheid is onbekend",
      snapshotPending: "Momentopname wordt bijgewerkt",
      snapshotFailed: "Verversen van momentopname mislukt",
      noObserved: "Nog geen gedekt later resultaat.",
      factUnknown: "De oorzaak blijft onbekend.",
      stale:
        "Dit bewaarde probleem staat niet meer in de actuele werkvoorraad. Verwijdering of ontbrekende waarnemingen bewijzen geen herstel.",
      evidence: "Bewijs en beperkingen",
      members: "Getroffen leden en tegenbewijs",
      omitted: "Extra leden weggelaten",
      gaps: "Meetgaten",
      noGap:
        "Geen gat in de begrensde bewaarde selectie; eerdere dekking kan onbekend zijn.",
      importance: "Belang voor jou",
      known: "Dit probleem ken ik",
      usual: "Dit gedrag is voor mij gebruikelijk",
      independent:
        "Deze keuzes staan los van elkaar. Opslaan bevestigt geen verslechtering en wijzigt geen bestaande beleidsbasis.",
      savePreference: "Bewaar mijn keuzes",
      ack: "Bevestig deze verslechtering expliciet",
      ackNote:
        "Deze aparte handeling wijzigt alleen je lokale presentatiebasis.",
      knownBacklog: "Bekende of gebruikelijke achterstand blijft zichtbaar",
      backlog: "Bekende / gebruikelijke waarnemingen",
      all: "Alle waarnemingen",
      attentionFilter: "Actuele aandacht",
      empty: "Geen onderbouwd probleem in deze selectie.",
      openHistory: "Bekijk bewaarde historie",
      technical: "Technische details",
      impact: "Expliciete afhankelijkheden (mogelijk gevolg)",
      noImpact:
        "Geen bewaarde expliciete afhankelijkheid beschikbaar; fysieke gevolgen zijn onbekend.",
      healthy: "Gezond tegenbewijs",
      time: "Waarnemingen tot",
      sourceFreshness:
        "Het vastleggen van details is iets anders dan de actualiteit van de monitor.",
      trace: "Waargenomen tijdlijn",
      burden: "Uitvalbelasting · eerste → tweede helft",
      comparisonUnknown: "Vergelijkbare uitvalbelasting is onbekend.",
      comparable: "vergelijkbaar",
      excluded: "uitgesloten",
      trend: "Apparaatwaarnemingen",
      method: "Dekking en rekenmethode",
      recent: "Actueel waargenomen gedrag",
      pending:
        "De lokale presentatie wordt bijgewerkt; de tijd van de laatste samenhangende waarneming blijft zichtbaar.",
      capacity:
        "De lokale presentatie is begrensd; weggelaten gevallen betekenen geen gezonde toestand.",
      intake: "Wat is belangrijk in jouw huis?",
      intakeIntro:
        "Optioneel: kies belangrijke apparaten en bekend of gebruikelijk gedrag. Bestaande keuzes zijn ingevuld. Pas bij opslaan verandert er iets.",
      intakeStep: "Kies apparaten · behoud je historie",
      complete: "Opslaan en afronden",
      draft: "Bewaar voor later",
      cancel: "Annuleren zonder opslaan",
      skipIntake: "Nu overslaan",
      search: "Zoek op naam of ruimte",
      next: "Volgende pagina",
      previous: "Vorige pagina",
      edit: "Ook later per probleem aan te passen",
      locale: "Taal van de interface",
      noDevice:
        "Nog geen geregistreerde apparaten waargenomen. Je kunt later verdergaan.",
      userOnly: "Persoonlijke terugkoppeling · alleen lokaal",
      unknownCount:
        "Onbekende leden blijven onbekend; diagnostische of uitgeschakelde leden bewijzen geen apparaatuitval.",
      rooms: "Dekking van ruimtenamen",
      retained: "Bewaard expertbewijs",
      changedCohort:
        "Meetgaten, gewijzigde leden en verwijdering verhinderen een herstelconclusie.",
      ackConfirm:
        "De nieuw waargenomen verslechtering bevestigen? Dit staat los van belang en intake.",
      selectionCap: "Bewaar maximaal 100 apparaatwijzigingen tegelijk.",
      sourceState: "Bewaarde brontoestand",
      more: "Meer waarnemingen",
      noHealth: "Er wordt geen algemene gezondheidsscore afgeleid.",
      intakeSaved:
        "Voorkeuren bewaard. Bestaande historie en beleidsbasis zijn behouden.",
    },
  };
  let locale = navigator.language?.toLowerCase().startsWith("nl") ? "nl" : "en";
  try {
    const saved = localStorage.getItem("vision.locale");
    if (["nl", "en"].includes(saved)) locale = saved;
  } catch {}
  let intakeDraft = new Map(),
    intakeLocale = null;
  const t = (key) => strings[locale][key] || key;
  const x = (value) =>
    String(value ?? "").replace(
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
  const when = (value) =>
    typeof value === "number" && Number.isFinite(value)
      ? new Date(value * 1000).toLocaleString(
          locale === "nl" ? "nl-NL" : "en-GB",
        )
      : t("unknown");
  const link = (p) => "#problems/" + encodeURIComponent(p.problem_id);
  const title = (p) =>
    p.kind === "group"
      ? `${p.member_count} ${t("group")}`
      : p.name || t("unnamed");
  const manual = (p) =>
    t(
      p.kind === "group"
        ? "groupCheck"
        : p.kind === "source"
          ? "sourceCheck"
          : p.state === "partial"
            ? "partialCheck"
            : "powerCheck",
    );
  const room = (p) =>
    p.kind === "group"
      ? (p.member_labels || []).map((m) => m.name || t("unnamed")).join(" · ") +
        " · " +
        integrationLabel(p.target)
      : p.room || t("unknownRoom");
  const layout = (name, body) =>
    `<section class="home-section"><h2>${x(t(name))}</h2>${body}</section>`;
  const options = (values, selected) =>
    values
      .map(
        (v) =>
          `<option value="${x(v)}" ${v === selected ? "selected" : ""}>${x(t(v))}</option>`,
      )
      .join("");
  function applyLocale(value) {
    if (value === "auto") {
      locale = navigator.language?.toLowerCase().startsWith("nl") ? "nl" : "en";
      try {
        localStorage.removeItem("vision.locale");
      } catch {}
    } else if (["nl", "en"].includes(value)) {
      locale = value;
      try {
        localStorage.setItem("vision.locale", value);
      } catch {}
    }
    document.documentElement.lang = locale;
    const connection = document.querySelector("#connection");
    if (connection?.dataset.connected)
      connection.textContent =
        (connection.dataset.connected === "true"
          ? locale === "nl"
            ? "Verbonden"
            : "Connected"
          : locale === "nl"
            ? "Niet verbonden"
            : "Disconnected") +
        " · " +
        t("readonly");
    const current = location.hash.slice(1).split("/")[0] || "today",
      titleKey = Object.keys(strings.en).find(
        (k) => k.toLowerCase() === current,
      );
    if (titleKey && document.querySelector("#title"))
      document.querySelector("#title").textContent = t(titleKey);
    document.querySelectorAll("#nav a, #expert-nav a").forEach((a) => {
      const key = a.dataset.label;
      if (key) a.textContent = t(key);
    });
    const tagline = document.querySelector(".tagline");
    if (tagline) tagline.textContent = t("tagline");
    const skip = document.querySelector(".skip-link");
    if (skip) skip.textContent = t("skip");
    const safety = document.querySelector(".safety");
    if (safety)
      safety.innerHTML =
        locale === "nl"
          ? "◈ ALLEEN LEZEN<br><small>Geen bediening. Wel inzicht.</small>"
          : "◈ READ ONLY<br><small>No controls. Just clarity.</small>";
    const summary = document.querySelector("#expert-nav summary");
    if (summary) summary.textContent = t("expert");
  }
  let localeRead = null;
  async function resolveLocale() {
    if (!localeRead)
      localeRead = api("home/preferences")
        .then((p) => {
          applyLocale(p.locale);
          return p;
        })
        .catch(() => {
          localeRead = null;
          // Interface language is cosmetic: preserve browser/cached choice and retry.
          return null;
        });
    return localeRead;
  }
  async function savePreferences(value) {
    const p = await api("home/preferences", {
      method: "POST",
      body: JSON.stringify(value),
    });
    // Cache only a confirmed server choice; failed saves leave cache/drafts intact.
    localeRead = null;
    if (["auto", "nl", "en"].includes(p?.locale)) {
      localeRead = Promise.resolve(p);
      applyLocale(p.locale);
    }
    return p;
  }
  function localizeShell(page, root) {
    if (locale !== "nl" || !["settings", "history"].includes(page)) return;
    const labels = {
      "Configuration & privacy": "Configuratie en privacy",
      "Current configuration (secrets excluded)":
        "Actuele configuratie (zonder geheimen)",
      "Expected offline behavior": "Verwacht niet-beschikbaar gedrag",
      "Configure provider keys, model IDs, opt-in, prices, budgets and the daily schedule in":
        "Stel providersleutels, modellen, toestemming, prijzen, budgetten en het dagelijkse schema in via",
      "Settings → Apps → Vision → Configuration":
        "Instellingen → Apps → Vision → Configuratie",
      ", then restart Vision. Credentials are never returned here. Prices are user supplied in USD per million tokens; a zero rate blocks AI requests.":
        ", en herstart Vision. Sleutels worden hier nooit getoond. Prijzen geef je zelf op in USD per miljoen tokens; een nultarief blokkeert AI-verzoeken.",
      "Budget failover needs its own opt-in. Costs are estimates at configured rates; enforce provider-side spending limits too. Anthropic/OpenAI process only opt-in evidence requests.":
        "Budgetuitwijking vereist aparte toestemming. Kosten zijn schattingen op basis van ingestelde tarieven; stel ook bij de provider limieten in. Anthropic/OpenAI verwerken alleen bewijsverzoeken waarvoor toestemming is gegeven.",
      "Reduce attention for expected availability observations while preserving source facts. This changes only Vision's database. Reasons are redacted before storage.":
        "Verminder aandacht voor verwachte beschikbaarheidswaarnemingen en behoud de bronfeiten. Dit wijzigt alleen de Vision-database. Redenen worden vóór opslag opgeschoond.",
      Entity: "Entiteit",
      Reason: "Reden",
      "Expires after hours": "Verloopt na uren",
      Expires: "Verloopt",
      "Save exception": "Bewaar uitzondering",
      Remove: "Verwijderen",
      "Search retained history": "Zoek in bewaarde historie",
      Section: "Onderdeel",
      Search: "Zoeken",
      "Entity (runs / availability / changes)":
        "Entiteit (uitvoeringen / beschikbaarheid / wijzigingen)",
      "Outcome / state / source": "Uitkomst / toestand / bron",
      "Day (UTC)": "Dag (UTC)",
      "Search history": "Zoek historie",
      "Start of this section": "Begin van dit onderdeel",
      "Next observations →": "Volgende waarnemingen →",
      Started: "Gestart",
      Automation: "Automatisering",
      Outcome: "Uitkomst",
      "Time source": "Tijdbron",
      Evidence: "Bewijs",
      State: "Toestand",
      Ended: "Geëindigd",
      Coverage: "Dekking",
      Observed: "Waargenomen",
      Case: "Melding",
      Source: "Bron",
      Severity: "Ernst",
      "Reported count": "Gemeld aantal",
      Kind: "Soort",
      Time: "Tijd",
      Provider: "Provider",
      Model: "Model",
      Status: "Status",
      "Estimated USD": "Geschatte USD",
      Task: "Taak",
      "Retained findings": "Bewaarde bevindingen",
      "Inspect run": "Bekijk uitvoering",
      "Open findings and original evidence":
        "Open bevindingen en oorspronkelijk bewijs",
      runs: "uitvoeringen",
      availability: "beschikbaarheid",
      issues: "meldingen",
      changes: "wijzigingen",
      usage: "verbruik",
      analyses: "onderzoeken",
      "Structural baselines record observation time, not HA edit time. Costs include conservative uncertain reservations.":
        "Structurele nulmetingen tonen de waarnemingstijd, niet de HA-wijzigingstijd. Kosten omvatten conservatieve onzekere reserveringen.",
    };
    // Only application-owned shell text; never entity options, reasons, results or data cells.
    const owned = root.querySelectorAll(
      [
        ":scope > .card > h2",
        "#history-filter > label",
        "#history-filter > button",
        '#history-filter select[name="kind"] > option',
        "#exception-form > label",
        "#exception-form > button",
        "thead th",
        "[data-home-shell]",
        "button[data-remove]",
      ].join(","),
    );
    for (const parent of owned) {
      for (const node of parent.childNodes) {
        if (node.nodeType !== Node.TEXT_NODE) continue;
        const text = node.nodeValue.trim(),
          translated = labels[text];
        if (translated) {
          // A label-only translation must not change an implicit option submission value.
          if (parent.tagName === "OPTION") parent.value = parent.value;
          node.nodeValue = node.nodeValue.replace(text, translated);
        }
      }
    }
    const reason = root.querySelector('#exception-form input[name="reason"]');
    if (reason)
      reason.placeholder =
        "Bijvoorbeeld: een batterijapparaat slaapt 's nachts";
  }
  const reportEntry = (f) =>
    `<li>${x(t(f.kind))} · ${x(when(f.created))}${f.note ? `<p>${x(f.note)}</p>` : ""}${f.check_unavailable ? `<small>${x(t(f.check_unavailable))}</small>` : ""}</li>`;
  function integrationStrip(data) {
    const groups = data.integrations?.items || [];
    if (!groups.length) return "";
    const hasSnapshot = Number.isFinite(data.cache_as_of),
      current =
        hasSnapshot &&
        data.reliable_now === true &&
        data.cache_state === "ready" &&
        data.cache_pending === false,
      count = (value) =>
        Number.isInteger(value) && value >= 0 ? value : t("unknown");
    return `<section class="home-integrations" aria-label="${x(t("concentrations"))}"><h3>${x(t("concentrations"))}</h3><small>${x(t("correlationShort"))} · ${x(t("snapshot"))}: ${x(when(data.cache_as_of))}${!current ? ` · <strong>${x(t("currentUnknown"))}</strong>` : ""}${data.cache_pending ? ` · ${x(t("snapshotPending"))}` : ""}${data.cache_state === "failed" ? ` · ${x(t("snapshotFailed"))}` : ""}</small>${groups
      .slice(0, 3)
      .map(
        (item) =>
          `<div class="heatmap-row"><a href="#devices/reliability?platform=${encodeURIComponent(item.platform)}">${x(integrationLabel(item.platform))}</a><svg viewBox="0 0 360 22" role="img" aria-label="${x(integrationLabel(item.platform))}: ${x(t("trend"))}">${(item.points || []).map((point, i, points) => `<rect x="${(i * 360) / points.length}" y="1" width="${Math.max(1, 360 / points.length - 2)}" height="20" class="${heatmapUnknown(point) || (point.unknown > 0 && point.offline === 0) ? "chart-gap" : point.offline > 0 ? "heatmap-bad" : point.partial > 0 ? "series-new" : "heatmap-observed"}"><title>${x(when(point.end))}: ${x(heatmapUnknown(point) ? t("unknown") : point.offline + " " + t("offline"))}</title></rect>`).join("")}</svg><small>${hasSnapshot ? `${x(count(item.offline))} ${x(t("offline"))} · ${x(count(item.partial))} ${x(t("partial"))} · ${x(count(item.unknown))} ${x(t("unassessed"))} · ${x(count(item.devices))} ${x(t("snapshotDevices"))}` : x(t("currentUnknown"))}</small></div>`,
      )
      .join("")}</section>`;
  }
  function cards(items) {
    return items
      .map(
        (p, i) =>
          `<article class="today-priority"><div><span class="overline">${x(t(p.changed ? "new" : "persistent"))}</span><h2>${x(title(p))}</h2><p class="home-location">${x(room(p))} · ${x(t(p.state))}</p><p>${x(manual(p))}</p></div><a ${i === 0 ? 'class="button home-primary"' : 'class="quiet-link"'} href="${link(p)}">${x(t(i === 0 ? "open" : "view"))}<span class="sr-only"> · ${x(title(p))}</span></a></article>`,
      )
      .join("");
  }
  async function today() {
    const params = new URLSearchParams(location.hash.split("?")[1] || ""),
      windowName = params.get("window") || "24h";
    const data = await api("today?window=" + encodeURIComponent(windowName));
    applyLocale(data.preferences?.locale);
    const r = data.metrics,
      burden = r?.burden || {},
      hours = (v) =>
        !Number.isFinite(v)
          ? t("unknown")
          : v > 0 && v < 0.1
            ? locale === "nl"
              ? "<0,1 apparaat-uur"
              : "<0.1 device-hour"
            : new Intl.NumberFormat(locale, {
                maximumFractionDigits: 1,
              }).format(v) +
              (locale === "nl" ? " apparaat-uur" : " device-hours");
    const burdenText =
      burden.direction === "unknown" || !burden.direction
        ? t("comparisonUnknown")
        : `${{ increased: "↑", decreased: "↓", unchanged: "→" }[burden.direction] || "?"} ${hours(burden.before_device_hours)} → ${hours(burden.after_device_hours)} · ${burden.comparable_devices}/${burden.total_devices ?? burden.comparable_devices} ${t("comparable")}; ${burden.excluded_devices ?? 0} ${t("excluded")}`;
    return (
      `<section class="today-hero"><div><p class="overline">${x(t("readonly"))}</p><h2>${x(t(data.status))}</h2><p>${x(t(data.status === "quiet" ? "quietNote" : data.status === "limited" ? "limitedNote" : "intro"))}</p><small>${x(t("time"))}: ${x(when(data.as_of))}</small></div><a href="#intake">${x(t(data.preferences?.intake === "new" || data.preferences?.intake === "draft" ? "personalize" : "preferences"))}</a></section>` +
      (data.pending
        ? `<p role="status" class="coverage-note">${x(t("pending"))}</p>`
        : "") +
      (data.limited ? `<p class="coverage-note">${x(t("capacity"))}</p>` : "") +
      (data.status === "limited" &&
      !data.priorities?.length &&
      (!data.pending ||
        !Number.isFinite(data.as_of) ||
        !data.coverage?.reliable_now)
        ? `<section class="card home-coverage-check"><p>${x(t("coverageCheck"))}</p><a class="button home-primary" href="#overview">${x(t("coverageOpen"))}</a></section>`
        : "") +
      `<div class="home-priorities">${cards((data.priorities || []).slice(0, 3))}</div>` +
      `<section class="card home-chart"><div class="home-section-heading"><h2>${x(t("trend"))}</h2><nav aria-label="${x(t("trend"))}">${["24h", "7d", "30d"].map((w) => `<a ${w === windowName ? 'aria-current="page"' : ""} href="#today/?window=${w}">${w}</a>`).join("")}</nav></div>${r ? deviceChart(r, locale) + integrationStrip(r) : ""}<p class="home-burden"><strong>${x(t("burden"))}</strong><br>${x(burdenText)}</p><details><summary>${x(t("method"))}</summary><p>${x(t("changedCohort"))}</p><p>${x(r?.meaning || "")}</p>${r ? integrationMap(r) : ""}<p>${x(t("rooms"))}: ${data.rooms?.available ? x(when(data.rooms.observed_at)) : x(t("unknown"))}</p><a href="#overview">${x(t("Overview"))}</a></details></section>` +
      `<p><a href="#problems/?mode=backlog">${x(t("knownBacklog"))}</a> · <a href="#history">${x(t("openHistory"))}</a></p>`
    );
  }
  async function problems(route) {
    if (route && !route.startsWith("?"))
      return dossier(decodeURIComponent(route.split("?")[0]));
    const p = new URLSearchParams(route?.replace(/^\?/, "") || ""),
      mode = p.get("mode") || "attention",
      page = Number(p.get("page") || 1);
    const data = await api(
      `problems?mode=${encodeURIComponent(mode)}&page=${page}`,
    );
    return (
      `<div class="toolbar"><a href="#problems">${x(t("attentionFilter"))}</a><a href="#problems/?mode=backlog">${x(t("backlog"))}</a><a href="#problems/?mode=all">${x(t("all"))}</a></div>` +
      (data.pending ? `<p class="coverage-note">${x(t("pending"))}</p>` : "") +
      `<div class="home-problem-list">${data.items.length ? cards(data.items) : data.pending ? "" : `<p class="empty">${x(t("empty"))}</p>`}</div>` +
      (data.has_more
        ? `<a href="#problems/?mode=${x(mode)}&page=${page + 1}">${x(t("next"))}</a>`
        : "")
    );
  }
  function personalForm(deviceId, pref) {
    return `<form id="home-personal" data-device="${x(deviceId)}"><label>${x(t("importance"))}<select name="importance">${options(["high", "normal", "low"], pref.importance || "normal")}</select></label><label class="check-label"><input type="checkbox" name="known_issue" ${pref.known_issue ? "checked" : ""}>${x(t("known"))}</label><label class="check-label"><input type="checkbox" name="usual_behavior" ${pref.usual_behavior ? "checked" : ""}>${x(t("usual"))}</label><small>${x(t("independent"))}</small><button type="submit">${x(t("savePreference"))}</button>${pref.worsened ? `<button type="button" id="home-ack">${x(t("ack"))}</button><small>${x(t("ackNote"))}</small>` : ""}</form>`;
  }
  async function dossier(id) {
    const data = await api("problems/" + encodeURIComponent(id)),
      p = data.problem,
      device = data.device;
    const entries = data.members || [],
      primaryHealthy = device?.reliable_now
        ? entries.filter(
            (m) => m.role === "primary" && m.availability === "available",
          )
        : [];
    return (
      `<section class="today-hero"><div><p class="overline">${x(t("proven"))}</p><h2>${x(title(p))}</h2><p>${x(room(p))} · ${x(t(device?.state || p.state))}</p><small>${x(t("time"))}: ${x(when(device?._as_of || p.as_of))}</small></div><a href="#today">${x(t("Today"))}</a></section>` +
      (!data.current ? `<p class="coverage-note">${x(t("stale"))}</p>` : "") +
      (data.pending
        ? `<p role="status" class="coverage-note">${x(t("pending"))}</p>`
        : "") +
      (device && !device.reliable_now
        ? `<p class="coverage-note">${x(t("limitedNote"))}</p>`
        : "") +
      layout(
        "why",
        `<p>${x(t(p.preference?.importance || "normal"))}. ${x(t("relevance"))}</p>${
          data.dependencies?.affected_automations?.length
            ? `<ul>${data.dependencies.affected_automations
                .slice(0, 2)
                .map(
                  (e) =>
                    `<li><a href="${x(e.href)}">${x(e.display_name || t("retained"))}</a> · ${x(e.relation)}</li>`,
                )
                .join("")}</ul>`
            : ""
        }`,
      ) +
      layout(
        "plan",
        `<p class="home-next-check">${x(manual(p))}</p>${p.expert_href ? `<a href="${x(p.expert_href)}">${x(t("sourceOpen"))}</a>` : ""}<form id="home-feedback" data-problem="${x(p.problem_id)}" data-episode="${x(p.episode)}"><fieldset><legend>${x(t("feedback"))}</legend><select name="kind" aria-label="${x(t("feedback"))}">${options(["checked", "no_change", "seems_recovered", "later"], "checked")}</select><details><summary>${x(t("note"))}</summary><textarea name="note" maxlength="400"></textarea></details><button type="submit">${x(t("saveFeedback"))}</button></fieldset></form>`,
      ) +
      layout(
        "validation",
        `<p>${x(t("validate"))}</p><div class="followthrough-grid"><div><h3>${x(t("reported"))}</h3><small>${x(t("userOnly"))}</small>${data.feedback.length ? `<ol>${data.feedback.map(reportEntry).join("")}</ol>` : `<p>${x(t("noReport"))}</p>`}${data.earlier_feedback?.length ? `<details class="earlier-reports"><summary>${x(t("earlierReports"))} (${data.earlier_feedback.length})</summary><ol>${data.earlier_feedback.map(reportEntry).join("")}</ol></details>` : ""}</div><div><h3>${x(t("observed"))}</h3>${device?.checks?.length ? `<ul>${device.checks.map((c) => `<li>${x(t(c.validation))} · ${x(when(c.created))}</li>`).join("")}</ul>` : `<p>${x(t("noObserved"))}</p>`}<small>${x(t("changedCohort"))}</small></div></div>`,
      ) +
      `<details class="card"><summary>${x(t("evidence"))}</summary><p>${x(t("factUnknown"))}</p><p>${x(t("unknownCount"))}</p><h3>${x(t("members"))}</h3>${p.kind === "group" ? `<ul>${entries.map((m) => `<li><a href="${link(m)}">${x(title(m))}</a> · ${x(t(m.state))}</li>`).join("")}</ul>` : `<ul>${entries.map((m) => `<li>${x(m.name || t("unnamed"))} · ${x(m.availability)} · ${x(m.role)}</li>`).join("")}</ul>`}${data.members_omitted ? `<p>${data.members_omitted} ${x(t("omitted"))}</p>` : ""}${data.member_detail_unknown ? `<p class="coverage-note">${x(t("memberUnknown"))}</p>` : ""}<h3>${x(t("healthy"))}</h3><ul>${(
        data.healthy_counterevidence || primaryHealthy
      )
        .slice(0, 8)
        .map((m) => `<li>${x(m.name || t("unnamed"))}</li>`)
        .join(
          "",
        )}</ul>${device ? `<h3>${x(t("trace"))}</h3><ol>${device.history.map((h) => `<li>${x(when(h.started))} · ${x(t(h.state))}</li>`).join("")}</ol><h3>${x(t("gaps"))}</h3>${device.coverage_gaps.length ? `<ul>${device.coverage_gaps.map((g) => `<li>${x(when(g.started))} → ${x(when(g.ended))}</li>`).join("")}</ul>` : `<p>${x(t("noGap"))}</p>`}<small>${x(t("sourceFreshness"))} ${x(when(device.evidence_at))}</small>` : ""}<h3>${x(t("impact"))}</h3>${
        data.dependencies?.affected_automations?.length
          ? `<ul>${data.dependencies.affected_automations
              .slice(0, 10)
              .map(
                (e) =>
                  `<li>${x(e.display_name || t("retained"))} · ${x(e.relation)}</li>`,
              )
              .join("")}</ul>`
          : `<p>${x(t("noImpact"))}</p>`
      }<details><summary>${x(t("technical"))}</summary><pre>${x(JSON.stringify({ problem_id: p.problem_id, target: p.target, cohort: p.cohort, coverage: device?.evidence }, null, 2))}</pre>${device ? `<a href="#devices/reliability?device=${encodeURIComponent(p.target)}">${x(t("retained"))}</a>` : ""}</details></details>` +
      (device
        ? layout("preferences", personalForm(p.target, data.preference))
        : `<p>${x(t("correlation"))}</p>`)
    );
  }
  async function deviceList(route, intake = false) {
    const params = new URLSearchParams(route?.replace(/^\?/, "") || ""),
      page = Number(params.get("page") || 1),
      q = params.get("q") || "";
    const data = await api(
      `home/devices?page=${page}&q=${encodeURIComponent(q)}`,
    );
    let chosenLocale = "auto";
    if (intake) {
      const p = await resolveLocale();
      chosenLocale = intakeLocale || p?.locale || "auto";
    }
    const body =
      `<form id="home-search"><label>${x(t("search"))}<input name="q" type="search" maxlength="120" value="${x(q)}"></label><button type="submit">${x(t("search"))}</button></form>` +
      `<${intake ? 'form id="home-intake"' : "div"}>${intake ? `<label>${x(t("locale"))}<select name="locale"><option value="auto" ${chosenLocale === "auto" ? "selected" : ""}>${x(t("auto"))}</option>${options(["nl", "en"], chosenLocale)}</select></label>` : ""}<div class="home-device-list">${
        data.items
          .map((d) => {
            const v = {
              ...d.preference,
              ...(intakeDraft.get(d.device_id) || {}),
            };
            return `<article class="home-device" data-device="${x(d.device_id)}"><h3>${x(d.name || t("unnamed"))}</h3><small>${x(d.room || t("unknownRoom"))} · ${x(t(d.state))}</small>${intake ? `<label>${x(t("importance"))}<select data-field="importance">${options(["high", "normal", "low"], v.importance)}</select></label><label class="check-label"><input data-field="known_issue" type="checkbox" ${v.known_issue ? "checked" : ""}>${x(t("known"))}</label><label class="check-label"><input data-field="usual_behavior" type="checkbox" ${v.usual_behavior ? "checked" : ""}>${x(t("usual"))}</label>` : `<a href="${d.problem_available ? link(d) : "#devices/reliability?device=" + encodeURIComponent(d.device_id)}">${x(t(d.problem_available ? "view" : "viewDevice"))}</a>`}</article>`;
          })
          .join("") || `<p>${x(t("noDevice"))}</p>`
      }</div>${intake ? `<div class="home-actions"><button type="submit" value="complete">${x(t("complete"))}</button><button type="submit" value="draft">${x(t("draft"))}</button><button type="button" id="home-cancel">${x(t("cancel"))}</button></div>` : ""}</${intake ? "form" : "div"}>` +
      (data.has_more
        ? `<a href="#${intake ? "intake" : "devices"}/?page=${page + 1}&q=${encodeURIComponent(q)}">${x(t("next"))}</a>`
        : "");
    return intake
      ? `<section class="today-hero"><div><h2>${x(t("intake"))}</h2><p>${x(t("intakeIntro"))}</p><small>${x(t("independent"))}</small></div><button id="home-skip" class="quiet-button">${x(t("skipIntake"))}</button></section>` +
          body
      : body;
  }
  function bind() {
    applyLocale();
    const feedback = document.querySelector("#home-feedback");
    if (feedback)
      feedback.addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = new FormData(feedback),
          button = feedback.querySelector("button");
        button.disabled = true;
        try {
          const key =
            feedback.dataset.request ||
            (typeof crypto.randomUUID === "function"
              ? crypto.randomUUID().replaceAll("-", "")
              : [...crypto.getRandomValues(new Uint8Array(16))]
                  .map((n) => n.toString(16).padStart(2, "0"))
                  .join(""));
          feedback.dataset.request = key;
          await api(
            `problems/${encodeURIComponent(feedback.dataset.problem)}/feedback`,
            {
              method: "POST",
              body: JSON.stringify({
                request_id: key,
                episode: feedback.dataset.episode,
                kind: f.get("kind"),
                note: f.get("note") || "",
              }),
            },
          );
          notice.textContent = t("saved");
          render();
        } catch (error) {
          notice.textContent = error.message;
          button.disabled = false;
        }
      });
    const personal = document.querySelector("#home-personal");
    const personalEdits = new Set();
    personal
      ?.querySelectorAll("input,select")
      .forEach((control) =>
        control.addEventListener("change", () =>
          personalEdits.add(control.name),
        ),
      );
    const savePersonal = async (ack = false) => {
      const f = new FormData(personal);
      const value = { device_id: personal.dataset.device };
      for (const key of personalEdits)
        value[key] = key === "importance" ? f.get(key) : f.has(key);
      if (ack) value.acknowledge_worsening = true;
      try {
        await savePreferences({ devices: [value] });
        notice.textContent = t("saved");
        render();
      } catch (error) {
        notice.textContent = error.message;
      }
    };
    if (personal)
      personal.addEventListener("submit", (e) => {
        e.preventDefault();
        savePersonal();
      });
    document.querySelector("#home-ack")?.addEventListener("click", () => {
      if (window.confirm(t("ackConfirm"))) savePersonal(true);
    });
    const search = document.querySelector("#home-search");
    if (search)
      search.addEventListener("submit", (e) => {
        e.preventDefault();
        location.hash = `#${location.hash.startsWith("#intake") ? "intake" : "devices"}/?q=${encodeURIComponent(new FormData(search).get("q") || "")}`;
      });
    const intake = document.querySelector("#home-intake");
    if (intake && location.hash.startsWith("#intake")) {
      intake.querySelector("[name=locale]")?.addEventListener("change", (e) => {
        intakeLocale = e.target.value;
      });
      intake.querySelectorAll("[data-field]").forEach((control) =>
        control.addEventListener("change", () => {
          const row = control.closest("[data-device]"),
            value = intakeDraft.get(row.dataset.device) || {
              device_id: row.dataset.device,
            };
          value[control.dataset.field] =
            control.type === "checkbox" ? control.checked : control.value;
          intakeDraft.set(value.device_id, value);
        }),
      );
      intake.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (intakeDraft.size > 100) {
          notice.textContent = t("selectionCap");
          return;
        }
        try {
          await savePreferences({
            ...(intakeLocale !== null ? { locale: intakeLocale } : {}),
            intake: e.submitter?.value || "complete",
            devices: [...intakeDraft.values()],
          });
          intakeDraft.clear();
          intakeLocale = null;
          notice.textContent = t("intakeSaved");
          location.hash = "#today";
        } catch (error) {
          notice.textContent = error.message;
        }
      });
    }
    document.querySelector("#home-cancel")?.addEventListener("click", () => {
      intakeDraft.clear();
      intakeLocale = null;
      location.hash = "#today";
    });
    document
      .querySelector("#home-skip")
      ?.addEventListener("click", async () => {
        try {
          await savePreferences({ intake: "skipped" });
          intakeDraft.clear();
          intakeLocale = null;
          location.hash = "#today";
        } catch (error) {
          notice.textContent = error.message;
        }
      });
    document.querySelectorAll("[data-home-locale]").forEach((b) =>
      b.addEventListener("click", async () => {
        try {
          await savePreferences({ locale: b.dataset.homeLocale });
          render();
        } catch (error) {
          notice.textContent = error.message;
        }
      }),
    );
  }
  const settingsLinks = () =>
    `<section class="card"><h2>${x(t("preferences"))}</h2><p>${x(t("edit"))}</p><a class="button" href="#intake">${x(t("personalize"))}</a><div class="home-actions"><button data-home-locale="nl">Nederlands</button><button data-home-locale="en">English</button></div></section>`;
  return {
    label: t,
    applyLocale,
    resolveLocale,
    localizeShell,
    today,
    problems,
    devices: (route) => deviceList(route),
    intake: (route) => deviceList(route, true),
    bind,
    settingsLinks,
  };
})();
