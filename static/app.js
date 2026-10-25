/* Case Sparring Partner: browser app. Plain JS, no build step. */
const App = (() => {
  const $ = (id) => document.getElementById(id);
  const TYPE_LABEL = {
    profitability: "Profitability", market_sizing: "Market sizing", market_entry: "Market entry",
    m_and_a: "M&A", pricing: "Pricing", operations: "Operations",
  };
  const DIM_LABEL = {
    structure: "Structure", clarifying: "Clarifying questions", quantitative: "Quantitative / math",
    judgment: "Business judgment", synthesis: "Synthesis / recommendation", communication: "Communication",
  };
  const STAGES = ["clarify", "structure", "analysis", "synthesis"];
  const YALE = "#00356b", YALE2 = "#286dc0", GRID = "#e3e9f1", MUTED = "#5f6f84";
  const SERIES_COLORS = [YALE, "#63aaff", "#bd5319", "#5f712d"];

  let cfg = null, cases = [], filter = "all";
  let session = null, timerId = null, busy = false, charts = [], lastSent = { text: "", t: 0 };

  // ------------------------------------------------------------------ helpers
  function el(tag, attrs = {}, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v;
      else if (k === "onclick") e.addEventListener("click", v);
      else e.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return e;
  }
  async function api(path, opts = {}) {
    const res = await fetch(path, {
      method: opts.method || (opts.body ? "POST" : "GET"),
      headers: { "Content-Type": "application/json" },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.detail?.[0]?.msg || `Request failed (${res.status})`);
    return data;
  }
  function toast(msg, ms = 4000) {
    const t = $("toast"); t.textContent = msg; t.classList.remove("hidden");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms);
  }
  function user() { return ($("username").value || "").trim(); }
  function needUser() {
    if (user()) return true;
    toast("Type your first name first, so your progress is saved.");
    $("username").focus();
    return false;
  }
  function show(view) {
    for (const v of ["start", "interview", "score", "progress", "review"]) $("view-" + v).classList.toggle("hidden", v !== view);
    window.scrollTo(0, 0);
  }
  const fmt = (n) => Number(n || 0).toLocaleString();
  const money = (n) => "$" + Number(n || 0).toFixed(4);

  // ------------------------------------------------------------------ start screen
  async function init() {
    $("username").value = localStorage.getItem("csp-user") || "";
    $("username").addEventListener("input", () => localStorage.setItem("csp-user", user()));
    $("coach-pick").onclick = () => startCase(null, true);
    $("gen-btn").onclick = generate;
    $("send").onclick = send;
    $("end-btn").onclick = endCase;
    $("delete-history").onclick = deleteHistory;
    $("input").addEventListener("input", updateCount);
    $("input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
    Voice.init();
    try { cfg = await api("/api/config"); } catch (e) { toast(e.message, 8000); }
    await loadCases();
    const m = location.hash.match(/^#review=([a-f0-9]+)/);
    const pg = location.hash.match(/^#progress=(.+)$/);
    const play = location.hash.match(/^#play=([a-z0-9_]+)/);  // direct link to a case, e.g. #play=pickleball
    if (m) showReview(m[1]).then(() => {
      if (location.search.includes("only=score")) $("view-review").querySelector(".interview").classList.add("hidden");  // for report screenshots
    });
    else if (play) { if (!user()) $("username").value = "Guest"; startCase(play[1]); }
    else if (pg) { $("username").value = decodeURIComponent(pg[1]); showProgress(); }
  }

  async function loadCases() {
    cases = await api("/api/cases");
    const f = $("filters"); f.innerHTML = "";
    for (const t of ["all", ...Object.keys(TYPE_LABEL)]) {
      f.append(el("button", { class: filter === t ? "on" : "", onclick: () => { filter = t; loadCases(); } }, t === "all" ? "All" : TYPE_LABEL[t]));
    }
    const g = $("case-grid"); g.innerHTML = "";
    for (const c of cases.filter((c) => filter === "all" || c.case_type === filter)) {
      g.append(el("div", { class: "case-card", onclick: () => startCase(c.id) },
        el("div", { class: "ctype" }, TYPE_LABEL[c.case_type] || c.case_type, " ", c.generated ? el("span", { class: "badge" }, "generated") : null),
        el("div", { class: "ctitle" }, c.title),
        el("div", { class: "cmeta" }, el("span", {}, c.industry), el("span", { class: "dots", title: "difficulty" }, "●".repeat(c.difficulty) + "○".repeat(3 - c.difficulty)))));
    }
  }

  async function generate() {
    const btn = $("gen-btn"), st = $("gen-status");
    btn.disabled = true;
    st.innerHTML = ""; st.append(el("span", { class: "muted" }, "Writing a case, then checking every number… (about 30–60 seconds)"));
    try {
      const r = await api("/api/generate", { body: { case_type: $("gen-type").value, industry: $("gen-industry").value || "any industry", difficulty: +$("gen-diff").value } });
      st.innerHTML = "";
      for (const a of r.attempts) {
        st.append(el("div", { class: "attempt" }, `Attempt ${a.attempt}: ${a.passed ? "✅ passed all math checks" : "❌ failed: " + a.problems.join("; ")}`));
      }
      st.append(el("div", { class: "muted" }, `Generator cost: ${money(r.usage.cost_usd)} (${fmt(r.usage.input_tokens)} in, ${fmt(r.usage.output_tokens)} out)`));
      if (r.ok) {
        st.append(el("div", {}, "New case ready: ", el("b", {}, r.case.title), " ", el("button", { class: "ghost", onclick: () => startCase(r.case.id) }, "Start it ▶")));
        await loadCases();
      } else {
        st.append(el("div", { class: "accent" }, "Couldn't build a case with clean math. Try again, or pick a library case."));
      }
    } catch (e) { st.textContent = e.message; }
    btn.disabled = false;
  }

  // ------------------------------------------------------------------ interview
  async function startCase(caseId, coachPick = false) {
    if (!needUser()) return;
    try {
      const r = await api("/api/start", { body: { user: user(), case_id: caseId, coach_pick: coachPick } });
      session = r.state;
      $("chat").innerHTML = ""; $("exhibits").innerHTML = ""; charts.forEach((c) => c.destroy()); charts = [];
      $("exhibits").append(el("div", { class: "empty" }, "Exhibits appear here when you ask for the right data."));
      $("case-type").textContent = `${TYPE_LABEL[session.case.case_type]} · ${session.case.industry}`;
      $("case-title").textContent = session.case.title;
      $("input").value = ""; updateCount();
      if (r.reason) addEvent("🎯 " + r.reason);
      addMsg("interviewer", r.opening);
      Voice.say(r.opening);
      render(session);
      const startedAt = Date.now();
      $("timer").textContent = "00:00";
      clearInterval(timerId);
      timerId = setInterval(() => {
        const s = Math.floor((Date.now() - startedAt) / 1000);
        $("timer").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
      }, 1000);
      show("interview");
      $("input").focus();
    } catch (e) { toast(e.message, 6000); }
  }

  function addMsg(role, text, flagged = false) {
    const m = el("div", { class: `msg ${role}${flagged ? " flagged" : ""}` }, el("span", { class: "who" }, role === "interviewer" ? "Interviewer" : "You"), text);
    $("chat").append(m); $("chat").scrollTop = $("chat").scrollHeight;
  }
  function addEvent(text, warn = false) {
    $("chat").append(el("div", { class: "event" + (warn ? " warn" : "") }, text));
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  function render(state) {
    const st = $("stages"); st.innerHTML = "";
    const idx = STAGES.indexOf(state.stage);
    STAGES.forEach((s, i) => st.append(el("span", { class: "stage " + (i < idx || state.stage === "done" ? "done" : i === idx ? "now" : "") }, s)));
    $("facts-count").textContent = `data unlocked ${state.revealed_count}/${state.fact_count}`;
    const u = state.usage;
    $("m-in").textContent = fmt(u.input_tokens); $("m-cached").textContent = fmt(u.cache_read_tokens);
    $("m-out").textContent = fmt(u.output_tokens); $("m-cost").textContent = money(u.cost_usd);
    const cap = cfg?.limits?.max_cost_per_case || 0.05;
    $("budget-bar").style.width = Math.min(100, (100 * u.cost_usd) / cap) + "%";
    $("budget-text").textContent = `${((100 * u.cost_usd) / cap).toFixed(1)}% of this case's $${cap.toFixed(2)} spending cap · ${state.turns} turns`;
    renderExhibits(state.exhibits);
  }

  function renderExhibits(list, box = $("exhibits")) {
    const have = new Set([...box.querySelectorAll(".exhibit")].map((e) => e.dataset.id));
    if (list.length && !have.size) box.innerHTML = "";
    for (const ex of list) {
      if (have.has(ex.id)) continue;
      const wrap = el("div", { class: "exhibit exhibit-new" }); wrap.dataset.id = ex.id;
      wrap.append(el("div", { class: "exhibit-title" }, ex.title));
      if (ex.kind === "table") {
        const t = el("table");
        t.append(el("tr", {}, el("th", {}, ""), ...ex.series.map((s) => el("th", {}, s.name))));
        ex.labels.forEach((lab, i) => t.append(el("tr", {}, el("td", {}, lab), ...ex.series.map((s) => el("td", {}, `${s.values[i]} ${ex.unit}`)))));
        wrap.append(t);
      } else {
        const canvas = el("canvas", { height: "200" }); wrap.append(canvas);
        box.prepend(wrap);
        charts.push(new Chart(canvas, {
          type: ex.kind,
          data: { labels: ex.labels, datasets: ex.series.map((s, i) => ({ label: s.name, data: s.values, backgroundColor: SERIES_COLORS[i % 4], borderColor: SERIES_COLORS[i % 4], tension: 0.25 })) },
          options: { plugins: { legend: { labels: { color: MUTED } } }, scales: { x: { ticks: { color: MUTED }, grid: { color: GRID } }, y: { ticks: { color: MUTED }, grid: { color: GRID }, title: { display: !!ex.unit, text: ex.unit, color: MUTED } } } },
        }));
        continue;
      }
      box.prepend(wrap);
    }
  }

  function updateCount() {
    const n = $("input").value.length, max = cfg?.limits?.max_input_chars || 1500;
    $("charcount").textContent = n > max * 0.7 ? `${n}/${max}` : "";
    $("charcount").style.color = n > max ? "#c62828" : "";
  }

  async function send() {
    const text = $("input").value.trim();
    if (!text || busy || !session) return;
    if (text === lastSent.text && Date.now() - lastSent.t < 15000) {  // found in user testing: the same answer got sent twice
      toast("You just sent that. Say or type something new.");
      $("input").value = ""; updateCount();
      return;
    }
    lastSent = { text, t: Date.now() };
    Voice.stopSpeaking();
    busy = true; $("send").disabled = true;
    addMsg("candidate", text);
    $("input").value = ""; updateCount();
    const thinking = el("div", { class: "thinking" }, "Interviewer is thinking"); $("chat").append(thinking);
    $("chat").scrollTop = $("chat").scrollHeight;
    try {
      const r = await api("/api/turn", { body: { session_id: session.session_id, text } });
      thinking.remove();
      for (const ev of r.events) {
        if (ev.type === "fact") addEvent(`🔓 Data unlocked: ${ev.topic.replace(/_/g, " ")}`);
        else if (ev.type === "exhibit") addEvent(`📊 Exhibit on screen: ${ev.title}`);
        else if (ev.type === "calc") addEvent(`🧮 Interviewer checked: ${ev.expression}`);
        else if (ev.type === "flagged") { addEvent("⚠️ " + ev.message, true); $("chat").querySelectorAll(".msg.candidate").forEach((m, i, all) => i === all.length - 1 && m.classList.add("flagged")); }
        else if (ev.type === "reveal_blocked") addEvent("🔒 Data request blocked on a flagged message", true);
        else if (ev.type === "off_topic") addEvent(`↩️ Off-topic warning ${ev.strikes}/3`, true);
        else if (ev.type === "limit") addEvent("⛔ " + ev.message, true);
      }
      if (r.warnings?.includes("leak_blocked")) addEvent("🛡️ The leak filter blocked a reply that contained hidden data", true);
      addMsg("interviewer", r.reply);
      Voice.say(r.reply);
      session = r.state; render(session);
      if (session.closed) { addEvent("⛔ " + session.close_reason, true); }
    } catch (e) {
      thinking.remove();
      addEvent("⛔ " + e.message, true);
      $("input").value = text; updateCount();
    }
    busy = false; $("send").disabled = false;
  }

  // ------------------------------------------------------------------ scorecard
  async function endCase() {
    if (!session || busy) return;
    Voice.stopSpeaking(); Voice.stopListening();
    busy = true;
    clearInterval(timerId);
    show("score");
    $("grading").classList.remove("hidden"); $("score-body").innerHTML = "";
    try {
      const r = await api("/api/end", { body: { session_id: session.session_id } });
      renderScore(r);
      session = null;
    } catch (e) {
      $("score-body").append(el("div", { class: "card" }, e.message, " ", el("button", { class: "ghost", onclick: () => show("interview") }, "Back to the case")));
    }
    $("grading").classList.add("hidden");
    busy = false;
  }

  function renderScore(r, body = $("score-body")) {
    const c = r.scorecard, p = r.coach;
    body.innerHTML = "";
    const mins = Math.round(r.duration_sec / 60);
    body.append(el("div", { class: "score-top" },
      el("div", { class: "card overall" }, el("div", { class: "muted" }, "Overall"), el("div", { class: "big" }, c.overall.toFixed(1)), el("div", { class: "muted" }, "out of 5"),
        el("div", { class: "muted", style: "margin-top:10px;font-size:12.5px" }, `${mins} min · cost ${money(r.usage.cost_usd)}`)),
      el("div", { class: "card" }, el("div", { class: "kicker" }, TYPE_LABEL[c.case_type]), el("h2", {}, c.case_title), el("p", {}, c.summary),
        el("div", { class: "two" }, el("div", {}, el("h3", {}, "💪 Top strength"), c.top_strength), el("div", {}, el("h3", {}, "🎯 Biggest gap"), c.biggest_gap)))));

    const dims = el("div", { class: "dims" });
    for (const s of c.scores) {
      const bar = el("div", { class: "bar5" }); for (let i = 1; i <= 5; i++) bar.append(el("span", { class: i <= s.score ? "on" : "" }));
      dims.append(el("div", { class: "card dim" }, el("div", { class: "dim-head" }, el("span", {}, DIM_LABEL[s.dimension]), el("span", { class: "accent" }, `${s.score}/5`)), bar,
        el("div", {}, s.reason), s.evidence_quote ? el("div", { class: "quote" }, `“${s.evidence_quote}”`) : null));
    }

    const mt = el("table", { class: "math" }, el("tr", {}, el("th", {}, "Calculation"), el("th", {}, "You said"), el("th", {}, "Answer key"), el("th", {}, "Result")));
    for (const m of c.math_results) {
      mt.append(el("tr", {}, el("td", {}, m.question), el("td", {}, m.candidate_number ?? "—"), el("td", {}, `${+m.correct_answer.toFixed(3)} ${m.unit}`),
        el("td", { class: "v-" + m.verdict }, m.verdict.replace("_", " "))));
    }

    const stack = el("div", { class: "stack" }, dims,
      el("div", { class: "card" }, el("h3", {}, "🧮 Math, checked by code (not by the AI)"), mt));
    if (c.adjustments?.length) {
      const ul = el("ul", { class: "adjust" }); c.adjustments.forEach((a) => ul.append(el("li", {}, a)));
      stack.append(el("div", { class: "card" }, el("h3", {}, "🛡️ What the Python checks changed"), ul));
    }
    stack.append(el("div", { class: "card coach" },
      el("h3", {}, "🧑‍🏫 Your coach"), el("p", {}, p.pattern),
      el("p", {}, el("b", {}, "Focus: "), DIM_LABEL[p.focus_dimension]),
      el("p", {}, el("b", {}, "10-minute drill: "), p.drill),
      el("p", {}, el("b", {}, "Next case: "), r.next_case ? r.next_case.title : p.next_case_id, el("span", { class: "muted" }, ` (${p.next_case_reason})`)),
      el("div", { style: "display:flex;gap:10px;flex-wrap:wrap" },
        el("button", { class: "primary", onclick: () => startCase(p.next_case_id) }, "Start recommended case ▶"),
        el("button", { class: "ghost", onclick: showProgress }, "See my progress"),
        el("button", { class: "ghost", onclick: showStart }, "Pick another case"))));
    body.append(stack);
  }

  // ------------------------------------------------------------------ progress
  async function showProgress() {
    if (!needUser()) return;
    show("progress");
    const body = $("progress-body"); body.innerHTML = "";
    const h = await api("/api/history?user=" + encodeURIComponent(user()));
    if (!h.length) { body.append(el("div", { class: "card empty" }, "No cases yet. Finish a case to see your scores here.")); return; }
    const canvas = el("canvas", { height: "110" });
    body.append(el("div", { class: "card" }, el("h3", {}, "Scores over time"), canvas));
    const dims = Object.keys(DIM_LABEL);
    new Chart(canvas, {
      type: "line",
      data: {
        labels: h.map((r, i) => `#${i + 1} ${r.case_id}`),
        datasets: [{ label: "Overall", data: h.map((r) => r.overall), borderColor: YALE, backgroundColor: YALE, borderWidth: 3, tension: .25 },
          ...dims.map((d, i) => ({ label: DIM_LABEL[d], data: h.map((r) => r.scores[d]), borderColor: ["#63aaff", "#5f712d", "#bd5319", "#978d85", "#286dc0", "#4a4a4a"][i], borderWidth: 1.2, pointRadius: 2, tension: .25, hidden: false }))],
      },
      options: { scales: { y: { min: 1, max: 5, ticks: { color: MUTED }, grid: { color: GRID } }, x: { ticks: { color: MUTED }, grid: { color: GRID } } }, plugins: { legend: { labels: { color: MUTED } } } },
    });
    const t = el("table", { class: "hist" }, el("tr", {}, ...["#", "Case", "Type", "Overall", "Math", "Time", "Turns", "Cost", ""].map((x) => el("th", {}, x))));
    h.forEach((r, i) => t.append(el("tr", {}, el("td", {}, i + 1), el("td", {}, r.case_title), el("td", {}, TYPE_LABEL[r.case_type]), el("td", { class: "accent" }, r.overall),
      el("td", {}, `${r.math_correct}/${r.math_total}`), el("td", {}, `${Math.round(r.duration_sec / 60)} min`), el("td", {}, r.turns), el("td", {}, money(r.cost_usd)),
      el("td", {}, r.session_id ? el("button", { class: "ghost", onclick: () => showReview(r.session_id) }, "Review") : ""))));
    body.append(el("div", { class: "card", style: "margin-top:14px" }, t));
  }

  async function deleteHistory() {
    if (!needUser() || !confirm(`Delete all saved practice history for "${user()}" on this computer?`)) return;
    const r = await api("/api/history?user=" + encodeURIComponent(user()), { method: "DELETE" });
    toast(`Deleted ${r.deleted} saved case(s).`);
    showProgress();
  }

  function showStart() { show("start"); loadCases(); }

  // ------------------------------------------------------------------ review a finished case
  async function showReview(sid) {
    let r;
    try { r = await api("/api/run/" + encodeURIComponent(sid)); } catch (e) { toast(e.message); return; }
    show("review");
    location.hash = "review=" + sid;
    $("rv-type").textContent = r.case ? `${TYPE_LABEL[r.case.case_type]} · ${r.case.industry} · review` : "review";
    $("rv-title").textContent = r.case ? r.case.title : r.case_id;
    const chat = $("rv-chat"); chat.innerHTML = "";
    for (const t of r.transcript) {
      for (const ev of t.events || []) {
        const label = ev.type === "fact" ? `🔓 reveal_fact("${ev.topic}")` : ev.type === "exhibit" ? `📊 exhibit shown: ${ev.title}`
          : ev.type === "calc" ? `🧮 calculator(${ev.expression})` : ev.type === "stage" ? `➡️ stage: ${ev.stage}` : ev.type === "off_topic" ? "↩️ flag_off_topic" : null;
        if (label) chat.append(el("div", { class: "event" }, label));
      }
      chat.append(el("div", { class: `msg ${t.role}${t.flagged ? " flagged" : ""}` }, el("span", { class: "who" }, t.role === "interviewer" ? "Interviewer" : "You"), t.text));
      if (t.flagged) chat.append(el("div", { class: "event warn" }, "⚠️ Flagged by the input guard: withheld from the AI"));
    }
    $("rv-facts").textContent = `${r.revealed.length} data topics unlocked`;
    const box = $("rv-exhibits"); box.innerHTML = "";
    if (!r.exhibits.length) box.append(el("div", { class: "empty" }, "No exhibits unlocked."));
    renderExhibits(r.exhibits, box);
    const u = r.usage;
    $("rv-in").textContent = fmt(u.input_tokens); $("rv-cached").textContent = fmt(u.cache_read_tokens);
    $("rv-out").textContent = fmt(u.output_tokens); $("rv-cost").textContent = money(u.cost_usd);
    renderScore(r, $("rv-score"));
  }

  // ------------------------------------------------------------------ voice (browser only, no tokens)
  const Voice = (() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    let rec = null, listening = false, finalText = "", spaceHeld = false;

    function init() {
      if (!SR) {
        $("mic").classList.add("hidden");
        $("voice-hint").classList.add("hidden");
        $("autosend").parentElement.classList.add("hidden");
        $("voice-note").classList.remove("hidden");
        $("voice-pill").textContent = "🎤 Voice input isn't supported in this browser. Use Chrome or Edge";
        $("voice-pill").classList.add("warn");
      } else {
        rec = new SR();
        rec.continuous = true; rec.interimResults = true; rec.lang = "en-US";
        rec.onresult = (e) => {
          let interim = "";
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            if (e.results[i].isFinal) finalText += t + " "; else interim += t;
          }
          $("input").value = finalText.trim(); updateCount();
          $("interim").textContent = interim;
        };
        rec.onerror = (e) => { if (e.error === "not-allowed") toast("Microphone permission was blocked. Allow it in Chrome's address bar, or type instead.", 7000); else if (e.error !== "no-speech" && e.error !== "aborted") toast("Voice error: " + e.error); };
        rec.onend = () => {
          const was = listening; listening = false; $("mic").classList.remove("live"); $("interim").textContent = "";
          if (was && $("autosend").checked && $("input").value.trim()) send();
        };
        $("mic").onclick = () => (listening ? stopListening() : startListening());
        document.addEventListener("keydown", (e) => {
          if (e.code === "Space" && !spaceHeld && document.activeElement !== $("input") && !$("view-interview").classList.contains("hidden") && !(e.target instanceof HTMLInputElement)) {
            e.preventDefault(); spaceHeld = true; startListening();
          }
        });
        document.addEventListener("keyup", (e) => { if (e.code === "Space" && spaceHeld) { spaceHeld = false; stopListening(); } });
      }
      if (!("speechSynthesis" in window)) { $("speak").parentElement.classList.add("hidden"); }
    }
    function startListening() {
      if (!rec || listening || busy) return;
      stopSpeaking();
      finalText = $("input").value ? $("input").value.trim() + " " : "";
      try { rec.start(); listening = true; $("mic").classList.add("live"); } catch (_) { /* already started */ }
    }
    function stopListening() { if (rec && listening) rec.stop(); }
    // Calm, natural-sounding female voices first. Premium/Enhanced Mac voices (free download in System Settings)
    // beat Chrome's Google voices, which beat the default Samantha.
    const VOICE_PREFS = [
      /^(Ava|Zoe|Allison|Susan|Samantha|Serena|Kate|Joelle|Noelle|Nicky).*\((Premium|Enhanced)\)/i,
      /^Google UK English Female$/i,
      /^Google US English$/i,
      /^Microsoft (Aria|Jenny|Ava|Emma|Sonia|Libby).*Natural/i,
      /^(Moira|Tessa|Karen|Samantha)\b/i,
    ];
    const NOVELTY = /^(Albert|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Wobble|Good News|Jester|Organ|Superstar|Trinoids|Whisper|Zarvox|Grandpa|Grandma|Junior|Ralph|Fred|Rocko|Eddy|Reed|Sandy|Shelley|Flo)\b/i;
    const englishVoices = () => speechSynthesis.getVoices().filter((v) => v.lang.startsWith("en") && !NOVELTY.test(v.name));
    function pickVoice() {
      const vs = englishVoices();
      const saved = localStorage.getItem("csp-voice");
      const chosen = saved && vs.find((v) => v.name === saved);
      if (chosen) return chosen;
      for (const re of VOICE_PREFS) { const v = vs.find((x) => re.test(x.name)); if (v) return v; }
      return vs[0];
    }
    function fillVoicePicker() {
      const sel = $("voice-select"); if (!sel) return;
      const vs = englishVoices(); if (!vs.length) return;
      const current = pickVoice();
      sel.innerHTML = "";
      for (const v of vs) {
        const o = el("option", { value: v.name }, v.name.replace(/^Google /, "").replace(/^Microsoft /, "") + (v.localService ? "" : " (online)"));
        if (current && v.name === current.name) o.selected = true;
        sel.append(o);
      }
    }
    if ("speechSynthesis" in window) {
      speechSynthesis.onvoiceschanged = fillVoicePicker;
      document.addEventListener("DOMContentLoaded", () => {
        fillVoicePicker();
        $("voice-select")?.addEventListener("change", (e) => { localStorage.setItem("csp-voice", e.target.value); say("Hi, I'll be your interviewer today. Take your time, and walk me through your thinking.", true); });
        $("voice-test")?.addEventListener("click", () => say("Hi, I'll be your interviewer today. Take your time, and walk me through your thinking.", true));
      });
    }
    function say(text, force = false) {
      if (!("speechSynthesis" in window) || (!force && !$("speak").checked)) return;
      speechSynthesis.cancel();
      const v = pickVoice();
      // One sentence per utterance: Chrome's online voices cut off long utterances, and short pauses sound calmer.
      const parts = text.replace(/\s+/g, " ").match(/[^.!?]+[.!?]*/g) || [text];
      for (const part of parts) {
        if (!part.trim()) continue;
        const u = new SpeechSynthesisUtterance(part.trim());
        if (v) u.voice = v;
        u.rate = 0.92;   // a little slower than default: calmer
        u.pitch = 1.0;
        speechSynthesis.speak(u);
      }
    }
    function stopSpeaking() { if ("speechSynthesis" in window) speechSynthesis.cancel(); }
    return { init, say, stopSpeaking, stopListening };
  })();

  document.addEventListener("DOMContentLoaded", init);
  return { showStart, showProgress, showReview };
})();
