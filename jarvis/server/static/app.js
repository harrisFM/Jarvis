/* Jarvis dashboard: WebSocket client, browser speech in/out, approvals, memory, metrics. No build step. */
(() => {
  const $ = (s) => document.querySelector(s);
  const token = new URLSearchParams(location.search).get("token") || "";
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  const api = (path, opts = {}) => fetch(path + (path.includes("?") ? "&" : "?") + (token ? `token=${encodeURIComponent(token)}` : ""), {
    headers: { "Content-Type": "application/json", ...(token ? { "X-Jarvis-Token": token } : {}) }, ...opts,
  }).then((r) => (r.ok ? r.json() : r.json().then((e) => Promise.reject(e))));

  let ws, state = {}, currentAssistant = null, speaking = false;
  const speechQueue = [];
  const orb = $("#orb"), transcript = $("#transcript"), activity = $("#activity");

  // ---------------------------------------------------------------- websocket
  function connect() {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws${qs}`);
    ws.onopen = () => setConn("online", true);
    ws.onclose = () => { setConn("offline", false); setTimeout(connect, 2000); };
    ws.onmessage = (m) => handle(JSON.parse(m.data));
  }
  function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }
  function setConn(text, ok) { const b = $("#conn"); b.textContent = text; b.className = "badge " + (ok ? "ok" : "bad"); orb.classList.toggle("off", !ok); }

  function handle(ev) {
    switch (ev.type) {
      case "hello": case "state": applyState(ev.state); break;
      case "transcript":
        if (ev.role === "user") addMsg("user", ev.text, `${ev.user || ""} · ${ev.room || ""}`);
        else if (currentAssistant) { currentAssistant.firstChild.textContent = ev.text; currentAssistant = null; }
        else addMsg("assistant", ev.text);
        break;
      case "turn_started": orb.classList.add("thinking"); currentAssistant = addMsg("assistant", ""); break;
      case "assistant_delta": if (currentAssistant) currentAssistant.firstChild.textContent += ev.text; scrollBottom(); break;
      case "speak": enqueueSpeech(ev.text); break;
      case "turn_finished": orb.classList.remove("thinking"); if (currentAssistant) { const m = currentAssistant.querySelector(".meta"); if (m) m.textContent = fmtMetric(ev); } refreshState(); break;
      case "first_token": break;
      case "tool_call": logActivity(`${ev.name} <span class="${ev.status}">${ev.status}</span>${ev.input ? " " + esc(JSON.stringify(ev.input)).slice(0, 160) : ""}${ev.reason ? " — " + esc(ev.reason) : ""}`); break;
      case "tool_result": logActivity(`↳ <span class="${ev.is_error ? "err" : "allow"}">${esc(ev.result).slice(0, 200)}</span> <span class="t">${ev.duration_ms}ms</span>`); break;
      case "approval_requested": addApproval(ev); break;
      case "approval_resolved": removeApproval(ev.id); logActivity(`approval ${ev.id} → ${ev.approved ? '<span class="allow">approved</span>' : '<span class="deny">denied</span>'} by ${esc(ev.by || "")}`); break;
      case "timer_fired": addMsg("system", `⏰ ${ev.speak}`); enqueueSpeech(ev.speak); refreshState(); break;
      case "timers_changed": renderTimers(ev.timers); break;
      case "todos_changed": renderTodos(ev.todos); break;
      case "memory_changed": loadMemory(); break;
      case "notification": addMsg("system", `📨 ${ev.title}: ${ev.text}`); break;
      case "error": addMsg("system", `⚠ ${ev.text}`); orb.classList.remove("thinking"); currentAssistant = null; break;
      case "interrupted": addMsg("system", "interrupted"); orb.classList.remove("thinking"); currentAssistant = null; stopSpeaking(); break;
      case "conversation_reset": transcript.innerHTML = ""; addMsg("system", "context cleared"); break;
      case "ha_state": logActivity(`HA ${esc(ev.entity_id)} → ${esc(ev.state)}`); break;
    }
  }

  // ---------------------------------------------------------------- rendering
  function addMsg(role, text, meta) {
    const d = document.createElement("div"); d.className = "msg " + role;
    const span = document.createElement("span"); span.textContent = text; d.appendChild(span);
    if (role !== "system") { const m = document.createElement("span"); m.className = "meta"; m.textContent = meta || ""; d.appendChild(m); }
    transcript.appendChild(d); scrollBottom(); return d;
  }
  function scrollBottom() { transcript.scrollTop = transcript.scrollHeight; }
  function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function fmtMetric(ev) { return `${ev.model || ""} · ${ev.tier || ""} · first token ${ev.ttft_ms ?? "–"} ms · total ${ev.total_ms} ms · ${ev.input_tokens} in / ${ev.output_tokens} out${ev.cache_read_tokens ? ` · ${ev.cache_read_tokens} cached` : ""}`; }
  function logActivity(html) { const li = document.createElement("li"); li.innerHTML = `<span class="t">${new Date().toLocaleTimeString()}</span>${html}`; activity.prepend(li); while (activity.children.length > 200) activity.lastChild.remove(); }

  function applyState(s) {
    state = s; $("#title").textContent = s.assistant_name;
    const userSel = $("#user"); const prev = userSel.value;
    userSel.innerHTML = s.users.map((u) => `<option value="${esc(u.id)}">${esc(u.name)} (${esc(u.role)})</option>`).join("");
    if (prev) userSel.value = prev;
    const rows = [
      ["credentials", s.credentials ? "✓ configured" : "✗ ANTHROPIC_API_KEY missing"],
      ["default model", s.models.default + (s.models.fallbacks ? " · fallbacks on" : "")],
      ["fast tier", s.models.router_enabled ? s.models.fast + " (router on)" : "router off"],
      ["effort", `${s.models.effort_chat} chat / ${s.models.effort_complex} complex`],
      ["web search", s.models.web_search ? "on" : "off"],
      ["home assistant", s.home_assistant.configured ? (s.home_assistant.online ? "✓ online" : "configured, unreachable") : "not configured"],
      ["voice", `STT ${s.voice.stt} · TTS ${s.voice.tts} · wake "${s.voice.wake_word}"`],
      ["tools", s.tools.join(", ")],
    ];
    $("#status-table").innerHTML = rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("");
    $("#approvals").innerHTML = ""; (s.pending_approvals || []).forEach(addApproval); updateApprovalCount();
    renderTimers(s.timers); renderTodos(s.todos); renderMetrics(s.metrics);
  }
  function refreshState() { send({ type: "state" }); }
  function renderTimers(ts) { $("#timers").innerHTML = (ts || []).map((t) => `<li><span>⏱ ${esc(t.label || "timer")} — ${t.remaining_s}s</span><span class="cat">${esc(t.room)}</span></li>`).join(""); }
  function renderTodos(items) { $("#todos").innerHTML = (items || []).map((t) => `<li><span>☐ ${esc(t.text)}</span><span class="cat">#${t.id}</span></li>`).join("") || '<li class="empty">list is empty</li>'; }
  function renderMetrics(ms) { $("#metrics tbody").innerHTML = (ms || []).slice(-12).reverse().map((m) => `<tr><td>${esc(m.model)}</td><td>${esc(m.tier)}</td><td>${m.ttft_ms ?? "–"} ms</td><td>${m.total_ms} ms</td><td>${m.input_tokens}</td><td>${m.output_tokens}</td><td>${m.cache_read_tokens}</td><td>${m.tool_calls}</td></tr>`).join(""); }

  function addApproval(ev) {
    if ($(`#appr-${ev.id}`)) return;
    const c = document.createElement("div"); c.className = "card"; c.id = `appr-${ev.id}`;
    c.innerHTML = `<div class="title">${esc(ev.tool)}</div><div class="why">${esc(ev.reason || "")} · asked by ${esc(ev.user || "")}</div>
      <pre class="why">${esc(JSON.stringify(ev.input, null, 1))}</pre>
      <div class="actions"><button class="ok">Approve</button><button class="bad">Deny</button></div>`;
    c.querySelector(".ok").onclick = () => send({ type: "approve", id: ev.id, approved: true, by: "dashboard:" + $("#user").value });
    c.querySelector(".bad").onclick = () => send({ type: "approve", id: ev.id, approved: false, by: "dashboard:" + $("#user").value });
    const box = $("#approvals"); const empty = box.querySelector(".empty"); if (empty) empty.remove(); box.appendChild(c); updateApprovalCount();
  }
  function removeApproval(id) { const c = $(`#appr-${id}`); if (c) c.remove(); updateApprovalCount(); if (!$("#approvals").children.length) $("#approvals").innerHTML = '<p class="empty">Nothing waiting.</p>'; }
  function updateApprovalCount() { const n = document.querySelectorAll("#approvals .card").length; const el = $("#approval-count"); el.textContent = n; el.className = "count" + (n ? "" : " zero"); }

  // ---------------------------------------------------------------- memory
  async function loadMemory(q = "") {
    const { facts } = await api(`/api/memory?q=${encodeURIComponent(q)}`);
    $("#facts").innerHTML = facts.map((f) => `<li><span>${esc(f.text)} <span class="cat">${esc(f.category)}${f.confirmed ? "" : " · pending"}</span></span><button data-id="${f.id}" class="ghost">forget</button></li>`).join("") || '<li class="empty">no memories yet</li>';
    $("#facts").querySelectorAll("button").forEach((b) => (b.onclick = () => api(`/api/memory/${b.dataset.id}`, { method: "DELETE" }).then(() => loadMemory($("#mem-q").value))));
  }
  $("#mem-search").onsubmit = (e) => { e.preventDefault(); loadMemory($("#mem-q").value); };
  $("#mem-add").onsubmit = (e) => { e.preventDefault(); const t = $("#mem-text").value.trim(); if (!t) return; api("/api/memory", { method: "POST", body: JSON.stringify({ text: t, category: $("#mem-cat").value, user_id: $("#user").value }) }).then(() => { $("#mem-text").value = ""; loadMemory(); }); };

  // ---------------------------------------------------------------- composer
  function sendText(text) { if (!text.trim()) return; stopSpeaking(); send({ type: "user_message", text, user_id: $("#user").value, room: $("#room").value }); }
  $("#composer").onsubmit = (e) => { e.preventDefault(); sendText($("#text").value); $("#text").value = ""; };
  $("#stop").onclick = () => { send({ type: "interrupt" }); stopSpeaking(); };
  $("#reset").onclick = () => api("/api/reset", { method: "POST" });
  $("#clear-activity").onclick = () => (activity.innerHTML = "");

  // ---------------------------------------------------------------- speech out (browser TTS)
  function enqueueSpeech(text) { if (!$("#tts").checked || !("speechSynthesis" in window)) return; speechQueue.push(text); pumpSpeech(); }
  function pumpSpeech() {
    if (speaking || !speechQueue.length) return;
    const u = new SpeechSynthesisUtterance(speechQueue.shift());
    const voice = speechSynthesis.getVoices().find((v) => /en-GB/i.test(v.lang) && /male|Daniel|Arthur|George/i.test(v.name)) || speechSynthesis.getVoices().find((v) => /en-GB/i.test(v.lang));
    if (voice) u.voice = voice; u.rate = 1.02;
    speaking = true; orb.classList.add("speaking");
    u.onend = u.onerror = () => { speaking = false; orb.classList.remove("speaking"); pumpSpeech(); };
    speechSynthesis.speak(u);
  }
  function stopSpeaking() { speechQueue.length = 0; if ("speechSynthesis" in window) speechSynthesis.cancel(); speaking = false; orb.classList.remove("speaking"); }

  // ---------------------------------------------------------------- speech in (browser STT + wake word)
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, micOn = false, wakeMode = false;
  function startRec(continuous) {
    if (!SR) { addMsg("system", "This browser has no speech recognition. Use Chrome, or set JARVIS_STT=faster_whisper and post audio to /api/stt."); return; }
    if (rec) rec.stop();
    rec = new SR(); rec.lang = "en-GB"; rec.interimResults = true; rec.continuous = continuous;
    rec.onstart = () => { micOn = true; $("#mic").classList.add("on"); $("#listening").hidden = false; orb.classList.add("listening"); };
    rec.onend = () => { micOn = false; $("#mic").classList.remove("on"); $("#listening").hidden = true; orb.classList.remove("listening"); if (wakeMode) setTimeout(() => startRec(true), 300); };
    rec.onerror = (e) => { if (e.error !== "no-speech" && e.error !== "aborted") addMsg("system", "mic error: " + e.error); };
    rec.onresult = (e) => {
      let interim = "", final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) { const t = e.results[i][0].transcript; if (e.results[i].isFinal) final += t; else interim += t; }
      $("#interim").textContent = interim;
      if (interim && speaking) { stopSpeaking(); send({ type: "interrupt" }); } // barge-in
      if (final) {
        const wake = (state.voice && state.voice.wake_word) || "jarvis";
        let text = final.trim();
        if (wakeMode) { const idx = text.toLowerCase().indexOf(wake.toLowerCase()); if (idx < 0) return; text = text.slice(idx + wake.length).replace(/^[,.!?\s]+/, ""); if (!text) return; }
        sendText(text);
        if (!wakeMode) rec.stop();
      }
    };
    rec.start();
  }
  $("#mic").onclick = () => { if (micOn && !wakeMode) { rec.stop(); } else { wakeMode = false; $("#wake").checked = false; startRec(false); } };
  $("#wake").onchange = (e) => { wakeMode = e.target.checked; if (wakeMode) startRec(true); else if (rec) rec.stop(); };
  if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => {};

  connect(); loadMemory();
})();
