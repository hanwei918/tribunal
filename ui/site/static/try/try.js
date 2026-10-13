/* Try it: change a recorded case, run the real code checks in the browser,
   and, when the live service is on, run the AI panel on it.
   Strings come from window.TRY_I18N (written per language by the site build);
   the live service address comes from try-config.js (window.TRIBUNAL_TRY_API). */
(function(){
  "use strict";
  var T = window.TRY_I18N || {};
  var API = (window.TRIBUNAL_TRY_API || "").replace(/\/+$/, "");
  // Pyodide 0.27.7 is served from this site (try/pyodide/) so the page has no third-party dependency.
  var PYODIDE = window.TRIBUNAL_PYODIDE || new URL("try/pyodide/", location.href).href;
  var $ = function(id){ return document.getElementById(id); };
  var TEMPLATES = null, RECORDED = null, state = null, original = null, py = null, pyLoading = null, lastView = null, health = null;

  function el(tag, attrs, kids){
    var n = document.createElement(tag);
    if (attrs){ for (var k in attrs){ if (k === "text"){ n.textContent = attrs[k]; } else if (k === "html"){ n.innerHTML = attrs[k]; } else { n.setAttribute(k, attrs[k]); } } }
    (kids || []).forEach(function(c){ if (c != null){ n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); } });
    return n;
  }
  function clear(n){ while (n.firstChild){ n.removeChild(n.firstChild); } return n; }
  function fmt(s, o){ return String(s).replace(/\{(\w+)\}/g, function(_, k){ return o[k] == null ? "" : o[k]; }); }
  function money(v){ return v == null ? "" : "SGD " + Number(v).toFixed(2); }
  function say(id, text){ var n = $(id); if (n){ n.textContent = text; } }

  // -------------------------------------------------------------------------
  // Loading the starting cases
  // -------------------------------------------------------------------------
  Promise.all([fetch("try/templates.json").then(function(r){ return r.json(); }), fetch("try/recorded.json").then(function(r){ return r.json(); })])
    .then(function(res){
      TEMPLATES = {}; res[0].forEach(function(t){ TEMPLATES[t.case_no] = t; });
      RECORDED = res[1];
      var first = Number((location.hash.match(/case=(\d+)/) || [])[1]) || 208;
      choose(TEMPLATES[first] ? first : 208);
      checkLive();
    })
    .catch(function(){ say("try-status", T.loadFail); });

  document.querySelectorAll("[data-template]").forEach(function(b){
    b.addEventListener("click", function(){ choose(Number(b.getAttribute("data-template"))); });
  });

  function choose(n){
    var t = TEMPLATES[n];
    document.querySelectorAll("[data-template]").forEach(function(b){ b.setAttribute("aria-pressed", String(Number(b.getAttribute("data-template")) === n)); });
    state = {
      template: n,
      claim_text: t.claim_text,
      counterparty_text: t.counterparty_text || "",
      safety_flag: !!t.safety_flag,
      missing: [],
      messages: t.messages.map(function(m){ return {msg_id: m.msg_id, sender: m.sender, text: m.text, sent_at: m.sent_at, deleted: false}; })
    };
    original = JSON.stringify(edits());
    $("f-claim").value = state.claim_text;
    $("f-other").value = state.counterparty_text;
    $("f-safety").checked = state.safety_flag;
    $("f-gps").checked = false; $("f-chat").checked = false;
    say("f-claim-who", t.filed_by === "DRIVER" ? T.driverSays : T.riderSays);
    say("f-other-who", t.filed_by === "DRIVER" ? T.riderSays : T.driverSays);
    renderChat();
    showRecorded();
    clear($("code-out")); clear($("ai-out"));
    say("code-status", ""); say("ai-status", "");
    changed();
  }

  // -------------------------------------------------------------------------
  // The form
  // -------------------------------------------------------------------------
  function renderChat(){
    var box = clear($("chat"));
    state.messages.forEach(function(m, i){
      if (m.deleted){ return; }
      var who = m.sender === "SYSTEM" ? T.app : m.sender === "RIDER" ? T.rider : T.driver;
      var row = el("li", {"class": "msg " + m.sender.toLowerCase()});
      row.appendChild(el("span", {"class": "who", text: who}));
      if (m.sender === "SYSTEM"){
        row.appendChild(el("span", {"class": "txt sys", text: m.text}));
      } else {
        var input = el("input", {type: "text", value: m.text, maxlength: "400", "aria-label": fmt(T.msgLabel, {who: who, n: i + 1})});
        input.addEventListener("input", function(){ m.text = input.value; changed(); });
        row.appendChild(input);
        var del = el("button", {type: "button", "class": "x", "aria-label": T.remove, text: "×"});
        del.addEventListener("click", function(){ if (m.msg_id){ m.deleted = true; } else { state.messages.splice(i, 1); } renderChat(); changed(); });
        row.appendChild(del);
      }
      box.appendChild(row);
    });
    var live = state.messages.filter(function(m){ return !m.deleted; }).length;
    $("add-msg").disabled = live >= 14;
  }

  $("f-claim").addEventListener("input", function(){ state.claim_text = this.value; changed(); });
  $("f-other").addEventListener("input", function(){ state.counterparty_text = this.value; changed(); });
  $("f-safety").addEventListener("change", function(){ state.safety_flag = this.checked; changed(); });
  ["gps", "chat"].forEach(function(k){
    $("f-" + k).addEventListener("change", function(){
      var type = k === "gps" ? "GPS_TRACE" : "CHAT_LOG";
      state.missing = state.missing.filter(function(x){ return x !== type; });
      if (this.checked){ state.missing.push(type); }
      changed();
    });
  });
  $("add-msg").addEventListener("click", function(){
    var text = $("new-text").value.trim();
    if (!text){ $("new-text").focus(); return; }
    state.messages.push({msg_id: null, sender: $("new-sender").value, text: text, deleted: false});
    $("new-text").value = "";
    renderChat(); changed();
  });
  $("new-text").addEventListener("keydown", function(e){ if (e.key === "Enter"){ e.preventDefault(); $("add-msg").click(); } });
  $("reset").addEventListener("click", function(){ choose(state.template); });

  // One-click ideas.
  document.querySelectorAll("[data-idea]").forEach(function(b){
    b.addEventListener("click", function(){
      var idea = b.getAttribute("data-idea");
      if (idea === "threat"){ state.messages.push({msg_id: null, sender: "DRIVER", text: T.ideaThreat, deleted: false}); renderChat(); }
      if (idea === "pii"){ state.claim_text = state.claim_text + " " + T.ideaPii; $("f-claim").value = state.claim_text; }
      if (idea === "inject"){ state.messages.push({msg_id: null, sender: "RIDER", text: T.ideaInject, deleted: false}); renderChat(); }
      if (idea === "nogps"){ $("f-gps").checked = true; $("f-gps").dispatchEvent(new Event("change")); }
      if (idea === "safety"){ $("f-safety").checked = true; $("f-safety").dispatchEvent(new Event("change")); }
      changed();
    });
  });

  function edits(){
    var out = {template: state.template, claim_text: state.claim_text, counterparty_text: state.counterparty_text,
               safety_flag: state.safety_flag, missing: state.missing.slice().sort(), messages: []};
    state.messages.forEach(function(m){
      if (m.sender === "SYSTEM"){ return; }
      if (m.msg_id){ out.messages.push({msg_id: m.msg_id, text: m.deleted ? "" : m.text}); }
      else if (!m.deleted){ out.messages.push({msg_id: null, sender: m.sender, text: m.text}); }
    });
    return out;
  }
  function isEdited(){ return JSON.stringify(edits()) !== original; }

  var pending = null;
  function changed(){
    say("edited", isEdited() ? T.edited : T.unedited);
    $("download").href = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify({scenario: edits()}, null, 1));
    if (lastView){ clearTimeout(pending); pending = setTimeout(runCode, 500); }
    updateAiButton();
  }

  // -------------------------------------------------------------------------
  // Step 3: the code checks, in Python, in this browser
  // -------------------------------------------------------------------------
  function loadPython(){
    if (py){ return Promise.resolve(py); }
    if (pyLoading){ return pyLoading; }
    say("code-status", T.loadingPy);
    pyLoading = new Promise(function(resolve, reject){
      var s = document.createElement("script");
      s.src = PYODIDE + "pyodide.js"; s.onload = resolve; s.onerror = function(){ reject(new Error("pyodide")); };
      document.head.appendChild(s);
    }).then(function(){ return window.loadPyodide({indexURL: PYODIDE}); })
      .then(function(p){ py = p; return fetch("try/tribunal-core.zip"); })
      .then(function(r){ return r.arrayBuffer(); })
      .then(function(buf){
        py.FS.mkdir("/app"); py.FS.writeFile("/app/core.zip", new Uint8Array(buf));
        py.runPython("import zipfile, sys\nzipfile.ZipFile('/app/core.zip').extractall('/app')\nsys.path.insert(0, '/app')\nfrom tryit import case as C\nimport json");
        return py;
      });
    pyLoading.catch(function(){ pyLoading = null; say("code-status", T.pyFail); });
    return pyLoading;
  }

  $("run-code").addEventListener("click", runCode);
  function runCode(){
    var started = Date.now();
    $("run-code").disabled = true;
    loadPython().then(function(p){
      p.globals.set("EDITS", JSON.stringify(edits()));
      var out;
      try {
        out = JSON.parse(p.runPython("json.dumps(C.view_for(EDITS))"));
      } catch (err){
        var msg = String(err.message || err).split("\n").filter(Boolean);
        say("code-status", T.codeRefused + " " + msg[msg.length - 1].replace(/^\w+Error: /, ""));
        $("run-code").disabled = false; return;
      }
      lastView = out;
      renderCode(out);
      say("code-status", fmt(T.codeDone, {ms: Date.now() - started}));
      $("run-code").disabled = false;
      $("run-code").textContent = T.rerunCode;
    }).catch(function(){ $("run-code").disabled = false; });
  }

  var FACTS = {
    NO_SHOW_CHARGE: [
      ["GPS_TRACE.arrival.arrived_at", "fArrived", "time"],
      ["GPS_TRACE.arrival.longest_qualifying_run.duration_sec", "fWaited", "sec"],
      ["GPS_TRACE.arrival.pickup_zone_class", "fZone", "text"],
      ["GPS_TRACE.rider_presence.min_distance_m", "fRiderNear", "m"],
      ["GPS_TRACE.rider_presence.max_distance_m", "fRiderFar", "m"],
      ["FARE_BREAKDOWN.money.fee_charged", "fFee", "sgd"],
      ["FARE_BREAKDOWN.money.schedule_fee", "fSchedule", "sgd"],
      ["FARE_BREAKDOWN.money.driver_compensation", "fComp", "sgd"],
      ["FARE_BREAKDOWN.money.goodwill", "fGoodwill", "sgd"]
    ],
    ROUTE_DEVIATION: [
      ["GPS_TRACE.deviation.trace_distance_km", "fDriven", "km"],
      ["GPS_TRACE.deviation.optimal_distance_km", "fOptimal", "km"],
      ["GPS_TRACE.deviation.excess_pct", "fExcess", "pct"],
      ["GPS_TRACE.deviation.status", "fStatus", "text"],
      ["FARE_BREAKDOWN.money.charged_total", "fCharged", "sgd"],
      ["FARE_BREAKDOWN.money.recomputed_fare", "fRecomputed", "sgd"],
      ["FARE_BREAKDOWN.money.erp_lines.off_optimal_route_total", "fErpOff", "sgd"],
      ["FARE_BREAKDOWN.money.refund.refund_before_rounding", "fRefund", "sgd"],
      ["FARE_BREAKDOWN.money.surge_multiplier", "fSurge", "x"]
    ]
  };
  function factValue(v, kind){
    if (v == null){ return T.none; }
    if (kind === "sec"){ return Math.round(v) + " s (" + (v / 60).toFixed(1) + " min)"; }
    if (kind === "m"){ return Math.round(v) + " m"; }
    if (kind === "km"){ return Number(v).toFixed(2) + " km"; }
    if (kind === "pct"){ return Number(v).toFixed(1) + "%"; }
    if (kind === "sgd"){ return money(v); }
    if (kind === "x"){ return "×" + v; }
    if (kind === "time"){ return String(v).slice(11, 19); }
    return (T.values || {})[v] || String(v);
  }
  function highlightMasks(text){
    var frag = document.createDocumentFragment();
    String(text || "").split(/(\[[^\]]*masked\])/).forEach(function(part){
      frag.appendChild(/masked\]$/.test(part) ? el("mark", {text: part}) : document.createTextNode(part));
    });
    return frag;
  }

  function renderCode(v){
    var out = clear($("code-out"));
    var threat = v.threat_in_chat, gate = v.scope_gate.to_person;
    var route = gate ? T.routeGate : threat ? T.routeThreat : T.routeAi;
    out.appendChild(el("div", {"class": "verdict-line " + (gate || threat ? "warn" : "go")}, [el("span", {"class": "kicker", text: T.route}), el("p", {text: route})]));

    var grid = el("div", {"class": "cgrid"});
    // What the AI is shown: the masked statements.
    var masked = el("div", {"class": "cbox"}, [el("h3", {text: T.maskedTitle})]);
    masked.appendChild(el("p", {"class": "small", text: T.maskedNote}));
    var q1 = el("blockquote"); q1.appendChild(highlightMasks(v.claim_masked)); masked.appendChild(q1);
    if (v.counterparty_masked){ var q2 = el("blockquote"); q2.appendChild(highlightMasks(v.counterparty_masked)); masked.appendChild(q2); }
    grid.appendChild(masked);

    // The chat, as the queue reads it.
    var chat = el("div", {"class": "cbox"}, [el("h3", {text: T.chatTitle})]);
    if (!v.messages.length){ chat.appendChild(el("p", {"class": "small", text: T.noChat})); }
    var ul = el("ul", {"class": "clist"});
    v.messages.forEach(function(m){
      var li = el("li", {"class": m.threat ? "threat" : ""});
      li.appendChild(el("span", {"class": "who", text: m.sender === "SYSTEM" ? T.app : m.sender === "RIDER" ? T.rider : T.driver}));
      var span = el("span"); span.appendChild(highlightMasks(m.masked)); li.appendChild(span);
      if (m.threat){ li.appendChild(el("span", {"class": "tag", text: T.threat + " " + m.matched.join(", ")})); }
      ul.appendChild(li);
    });
    chat.appendChild(ul);
    grid.appendChild(chat);

    // Evidence and weights.
    var ev = el("div", {"class": "cbox"}, [el("h3", {text: T.evTitle}), el("p", {"class": "small", text: T.evNote})]);
    var table = el("table", {"class": "etable"});
    table.appendChild(el("thead", null, [el("tr", null, [el("th", {text: T.evType}), el("th", {text: T.evStatus}), el("th", {text: T.evWeight})])]));
    var tb = el("tbody");
    v.evidence.forEach(function(e){
      tb.appendChild(el("tr", {"class": e.weight === 0 ? "dim" : ""}, [el("td", {text: (T.types || {})[e.type] || e.type}), el("td", {text: (T.status || {})[e.status] || e.status}), el("td", {text: "×" + e.weight})]));
    });
    table.appendChild(tb); ev.appendChild(table); grid.appendChild(ev);

    // Facts code worked out.
    var fx = el("div", {"class": "cbox"}, [el("h3", {text: T.factsTitle}), el("p", {"class": "small", text: T.factsNote})]);
    var dl = el("dl", {"class": "facts"});
    (FACTS[v.category] || []).forEach(function(f){
      var item = v.facts[f[0]];
      dl.appendChild(el("dt", {text: T[f[1]] || f[1]}));
      dl.appendChild(el("dd", {text: item ? factValue(item.value, f[2]) : T.none}));
    });
    fx.appendChild(dl); grid.appendChild(fx);
    out.appendChild(grid);

    out.appendChild(el("p", {"class": "fp"}, [el("span", {"class": "kicker", text: T.fingerprint}), " ", el("code", {text: v.brief_sha256.slice(0, 24) + "…"}), " ", T.fpNote]));
    out.querySelectorAll("table").forEach(function(tbl){ tbl.setAttribute("tabindex", "0"); });
  }

  // -------------------------------------------------------------------------
  // Step 4: the AI panel
  // -------------------------------------------------------------------------
  var LABELS = T.rulings || {};
  function rulingLine(r){
    if (!r || !r.ruling){ return T.noRuling; }
    var label = LABELS[r.ruling] || r.ruling;
    if (r.ruling === "DRIVER_COMPENSATION"){ return label + " — " + fmt(T.driverPaid, {sgd: money(r.driver_compensation_sgd)}); }
    if (r.ruling === "FULL_REFUND" || r.ruling === "PARTIAL_REFUND"){ return label + " — " + money(r.amount_sgd); }
    return label;
  }
  function showRecorded(){
    var r = RECORDED[String(state.template)];
    var box = clear($("recorded"));
    if (!r){ return; }
    box.appendChild(el("span", {"class": "kicker", text: fmt(T.recordedKicker, {n: state.template})}));
    box.appendChild(el("p", {"class": "rline", text: rulingLine(r)}));
    var bits = [];
    if (r.confidence != null){ bits.push(fmt(T.confidence, {c: r.confidence})); }
    bits.push(fmt(T.keptDropped, {rk: r.kept.RIDER, dk: r.kept.DRIVER, rd: r.dropped.RIDER, dd: r.dropped.DRIVER}));
    if (r.vote_agreement != null){ bits.push(fmt(T.agreement, {a: Math.round(r.vote_agreement * 100)})); }
    bits.push(fmt(T.took, {s: Math.round(r.seconds)}));
    box.appendChild(el("p", {"class": "small", text: bits.join(" · ")}));
    box.appendChild(el("p", {"class": "small"}, [T.recordedNote + " ", el("a", {"class": "ul", href: "case-" + String(state.template).padStart(5, "0") + ".html", text: T.openCase})]));
  }

  function checkLive(){
    if (!API){ return setLive(null); }
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function(){ if (ctl){ ctl.abort(); } }, 5000);
    fetch(API + "/api/health", ctl ? {signal: ctl.signal} : {}).then(function(r){ return r.json(); })
      .then(function(h){ clearTimeout(timer); setLive(h); }).catch(function(){ setLive(null); });
  }
  function setLive(h){
    health = h && h.live ? h : null;
    $("ai-live").hidden = !health;
    $("ai-off").hidden = !!health;
    if (health){
      say("ai-left", fmt(T.left, {today: health.left_today, you: health.left_for_you}) + (health.mode === "recorded-test" ? " " + T.testMode : ""));
    }
    updateAiButton();
  }
  function updateAiButton(){
    var b = $("run-ai");
    if (!b){ return; }
    b.disabled = !health || health.left_today < 1 || health.left_for_you < 1;
  }

  $("run-ai").addEventListener("click", function(){
    var b = this; b.disabled = true;
    clear($("ai-out")); say("ai-status", T.sending);
    fetch(API + "/api/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({scenario: edits()})})
      .then(function(r){ return r.json().then(function(j){ return {ok: r.ok, j: j}; }); })
      .then(function(res){
        if (!res.ok){ say("ai-status", res.j.error || T.aiFail); b.disabled = false; return; }
        if (health){ health.left_today -= 1; health.left_for_you -= 1; setLive(health); }
        poll(res.j.id);
      })
      .catch(function(){ say("ai-status", T.aiFail); b.disabled = false; });
  });

  var STEPS = [["rider", "stRider"], ["driver", "stDriver"], ["referee", "stReferee"], ["drafts", "stDrafts"], ["vote", "stVote"]];
  function poll(id){
    fetch(API + "/api/run/" + id).then(function(r){ return r.json(); }).then(function(s){
      if (s.status === "queued"){ say("ai-status", fmt(T.queued, {n: s.position + 1})); return setTimeout(function(){ poll(id); }, 3000); }
      if (s.status === "running"){
        say("ai-status", fmt(T.running, {s: Math.round(s.elapsed_seconds || 0)}));
        renderSteps(s.progress || {});
        return setTimeout(function(){ poll(id); }, 3000);
      }
      if (s.status === "failed"){ say("ai-status", T.aiFail + " " + (s.error || "")); updateAiButton(); return; }
      renderSteps({rider: true, driver: true, referee: true, drafts: 4, vote: true}, s.result);
      renderResult(s.result);
      say("ai-status", fmt(T.done, {s: Math.round(s.result.seconds)}));
      updateAiButton();
    }).catch(function(){ setTimeout(function(){ poll(id); }, 5000); });
  }
  function renderSteps(p, result){
    var box = $("ai-steps") || $("ai-out").appendChild(el("ol", {id: "ai-steps", "class": "steps-live"}));
    clear(box);
    var gated = result && result.scope_gate;
    STEPS.forEach(function(st){
      var done = st[0] === "drafts" ? p.drafts >= 4 : !!p[st[0]];
      var label = T[st[1]] + (st[0] === "drafts" ? " (" + Math.min(p.drafts || 0, 4) + "/4)" : "");
      box.appendChild(el("li", {"class": gated ? "skip" : done ? "done" : "wait", text: label}));
    });
  }
  function renderResult(r){
    var out = $("ai-out");
    var card = el("div", {"class": "rcard"});
    card.appendChild(el("span", {"class": "kicker", text: T.yourResult}));
    card.appendChild(el("p", {"class": "rline", text: r.ruling ? rulingLine(r.ruling) : (r.failed_agent ? T.agentFailed : T.noRuling)}));
    var lane = (T.lanes || {})[r.lane + ":" + (r.lane_reasons || [])[0]] || (T.lanes || {})[r.lane] || r.lane;
    card.appendChild(el("p", {"class": "lane", text: lane}));
    var bits = [];
    if (r.ruling && r.ruling.confidence != null && r.ruling.ruling !== "ESCALATE"){ bits.push(fmt(T.confidence, {c: r.ruling.confidence})); }
    bits.push(fmt(T.keptDropped, {rk: r.referee.kept.RIDER || 0, dk: r.referee.kept.DRIVER || 0, rd: r.referee.dropped.RIDER || 0, dd: r.referee.dropped.DRIVER || 0}));
    if (r.vote_agreement != null){ bits.push(fmt(T.agreement, {a: Math.round(r.vote_agreement * 100)})); }
    bits.push(fmt(T.tokens, {n: (r.tokens.prompt + r.tokens.completion).toLocaleString()}));
    card.appendChild(el("p", {"class": "small", text: bits.join(" · ")}));
    if (r.drafts && r.drafts.length){
      var dl = el("ul", {"class": "drafts"});
      r.drafts.forEach(function(d){
        var what = d.valid && d.proposal ? rulingLine(d.proposal) : T.draftRefused;
        dl.appendChild(el("li", {"class": d.valid ? "ok" : "no"}, [el("span", {"class": "kicker", text: fmt(d.kind === "position_swapped" ? T.draftSwapped : T.draftN, {n: d.draft})}), " " + what]));
      });
      card.appendChild(dl);
    }
    if (r.referee.discards && r.referee.discards.length){
      var dd = el("details", {"class": "more"}, [el("summary", {text: fmt(T.dropped, {n: r.referee.discards.length})})]);
      var dul = el("ul");
      r.referee.discards.forEach(function(x){ dul.appendChild(el("li", {text: (x.side === "RIDER" ? T.rider : T.driver) + " · " + x.reason_code + ": " + x.claim})); });
      dd.appendChild(dul); card.appendChild(dd);
    }
    if (r.ruling && r.ruling.explanation){
      var ex = el("details", {"class": "more"}, [el("summary", {text: T.reasons}), el("pre", {"class": "expl", tabindex: "0", text: r.ruling.explanation})]);
      card.appendChild(ex);
    }
    card.appendChild(el("p", {"class": "fp"}, [el("span", {"class": "kicker", text: T.fingerprint}), " ", el("code", {text: r.brief_sha256.slice(0, 24) + "…"}),
      " ", lastView && lastView.brief_sha256 === r.brief_sha256 ? T.fpSame : ""]));
    out.appendChild(card);
  }
})();
