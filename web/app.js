"use strict";

const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const formEl = document.getElementById("composer");
const memoryEl = document.getElementById("use-memory");
const settingsEl = document.getElementById("settings");
const settingsBtn = document.getElementById("settings-btn");
const apiKeyEl = document.getElementById("api-key");
const statusDot = document.getElementById("status-dot");
const memoryInfo = document.getElementById("memory-info");
const agentSelect = document.getElementById("agent-select");

// Verlauf bleibt im Browser (Zero-Cloud: Server ist zustandslos) — pro Agent getrennt.
const histories = {};
const displayNames = {};
let currentAgent = "shaka";
let busy = false;

function history() {
  return (histories[currentAgent] ||= []);
}

function greeting() {
  const name = displayNames[currentAgent] || "Agent";
  if (currentAgent === "shaka") {
    return (
      "Shaka online. Lokaler Wissensspeicher aktiv — leg deine Claude-Exporte in data/ und " +
      "ingestiere sie mit `python scripts/ingest.py <pfad>`. Womit starten wir?"
    );
  }
  return name + " hier — eigenes Gedächtnis, eigene Seele. Womit kann ich helfen?";
}

apiKeyEl.value = sessionStorage.getItem("shaka_api_key") || "";
apiKeyEl.addEventListener("change", () => {
  sessionStorage.setItem("shaka_api_key", apiKeyEl.value);
});

settingsBtn.addEventListener("click", () => settingsEl.classList.toggle("hidden"));

function headers() {
  const h = { "Content-Type": "application/json" };
  if (apiKeyEl.value) h["X-API-Key"] = apiKeyEl.value;
  return h;
}

function addMessage(role, text, extraClass) {
  const div = document.createElement("div");
  div.className = "msg " + role + (extraClass ? " " + extraClass : "");
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function renderHistory() {
  chatEl.innerHTML = "";
  const hist = history();
  if (hist.length === 0) {
    addMessage("assistant", greeting());
    return;
  }
  for (const msg of hist) {
    addMessage(msg.role === "user" ? "user" : "assistant", msg.content);
  }
}

async function loadAgents() {
  try {
    const res = await fetch("/api/agents");
    if (!res.ok) return;
    const data = await res.json();
    agentSelect.innerHTML = "";
    for (const a of data.agents) {
      displayNames[a.name] = a.display;
      const opt = document.createElement("option");
      opt.value = a.name;
      opt.textContent = a.display.toUpperCase();
      agentSelect.appendChild(opt);
    }
    agentSelect.value = currentAgent;
    renderHistory();
  } catch {
    /* Server offline — checkHealth zeigt es an */
  }
}

agentSelect.addEventListener("change", () => {
  if (busy) {
    agentSelect.value = currentAgent; // Wechsel während des Streamens verhindern
    return;
  }
  currentAgent = agentSelect.value;
  renderHistory();
  inputEl.focus();
});

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    statusDot.classList.add("ok");
    statusDot.classList.remove("err");
    memoryInfo.textContent =
      "Modell: " + data.model +
      " · Agenten: " + (data.agents ? data.agents.length : 1) +
      " · Wissensspeicher (Shaka): " + data.memory_chunks + " Chunks" +
      (data.auth_required ? " · API-Key erforderlich" : "");
  } catch {
    statusDot.classList.add("err");
    statusDot.classList.remove("ok");
    memoryInfo.textContent = "Server nicht erreichbar.";
  }
}

// Server-Fehler kommen im Stream hinter diesem Marker: anzeigen, aber nie als
// Assistent-Antwort in den Verlauf übernehmen (sonst "vergiftet" der Fehler die Historie).
const ERROR_MARKER = "\u001e"; // ASCII Record Separator, vom Server gesetzt

function splitAnswer(raw) {
  const idx = raw.indexOf(ERROR_MARKER);
  if (idx === -1) return { clean: raw, error: "" };
  return {
    clean: raw.slice(0, idx),
    error: raw.slice(idx).split(ERROR_MARKER).join("").trim(),
  };
}

async function send(text) {
  busy = true;
  sendBtn.disabled = true;
  const hist = history(); // Agent zum Sendezeitpunkt festhalten
  const agent = currentAgent;
  addMessage("user", text);
  hist.push({ role: "user", content: text });

  const bubble = addMessage("assistant", "", "thinking");
  let raw = "";
  let clean = "";

  function render() {
    const parts = splitAnswer(raw);
    clean = parts.clean;
    bubble.textContent = clean + (parts.error ? "\n⚠ " + parts.error : "");
    if (parts.error) bubble.classList.add("error");
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ messages: hist, use_memory: memoryEl.checked, agent: agent }),
    });

    if (!res.ok) {
      let detail = "HTTP " + res.status;
      try {
        const err = await res.json();
        if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      } catch { /* Body war kein JSON */ }
      // Request kam nie bei Claude an — Nutzer-Turn zurücknehmen, damit ein
      // erneutes Senden keinen doppelten Turn erzeugt.
      hist.pop();
      bubble.classList.remove("thinking");
      bubble.classList.add("error");
      bubble.textContent = "⚠ " + detail;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      raw += decoder.decode(value, { stream: true });
      render();
    }
    raw += decoder.decode();
    render();
  } catch (err) {
    // Mitten im Stream abgerissen: Nutzer-Turn bleibt im Verlauf (die Frage wurde
    // gestellt), Teilantwort bleibt sichtbar, Fehler wird markiert.
    bubble.classList.add("error");
    bubble.textContent = (clean ? clean + "\n" : "") + "⚠ Verbindungsfehler: " + err.message;
  } finally {
    // Nur echte, nicht-leere Antworten werden Teil der Historie.
    if (clean.trim()) {
      hist.push({ role: "assistant", content: clean });
    }
    bubble.classList.remove("thinking");
    busy = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text || busy) return;
  inputEl.value = "";
  send(text);
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});

checkHealth();
renderHistory();
loadAgents();
