let configData = null;
let logsCleared = false;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

function setStatus(running, pid) {
  const pill = document.getElementById("status-pill");
  pill.textContent = running ? "Running" : "Stopped";
  pill.className = "pill " + (running ? "run" : "idle");
  document.getElementById("status-pid").textContent =
    running && pid ? `PID ${pid}` : "";
}

function showPanel(id) {
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav").forEach((n) => n.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  document.querySelector(`.nav[data-panel="${id}"]`).classList.add("active");
}

document.querySelectorAll(".nav").forEach((btn) => {
  btn.onclick = () => showPanel(btn.dataset.panel);
});

function renderField(container, field, agent, options) {
  const label = document.createElement("label");
  label.textContent = field.label;
  let input;
  if (field.type === "select") {
    input = document.createElement("select");
    input.id = field.key;
    (options[field.optionKey] || []).forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = v;
      if (v === agent[field.key]) o.selected = true;
      input.appendChild(o);
    });
  } else {
    input = document.createElement("input");
    input.type = "number";
    input.id = field.key;
    input.step = field.step || "any";
    if (field.min != null) input.min = field.min;
    if (field.max != null) input.max = field.max;
    input.value = agent[field.key] ?? "";
  }
  label.appendChild(input);
  container.appendChild(label);
}

function renderSettingsForm() {
  if (!configData) return;
  const { agent, field_groups: groups, options } = configData;
  const titles = {
    "fields-identity": "Agent identity",
    "fields-models": "Models & voice",
    "fields-vad": "VAD (when you are speaking)",
    "fields-turn": "Turn-taking & speakerphone",
  };
  const map = {
    "fields-identity": groups.identity,
    "fields-models": groups.models,
    "fields-vad": groups.vad,
    "fields-turn": groups.turn_taking,
  };
  Object.entries(map).forEach(([id, fields]) => {
    const el = document.getElementById(id);
    el.innerHTML = `<h2>${titles[id]}</h2>`;
    fields.forEach((f) => renderField(el, f, agent, options));
  });
}

async function loadConfig() {
  configData = await api("/api/config");
  renderSettingsForm();
  document.getElementById("system_prompt").value =
    configData.prompt.system_prompt || "";
}

function collectAgent() {
  const agent = { ...configData.agent };
  document.querySelectorAll("#panel-settings input, #panel-settings select").forEach((el) => {
    if (!el.id) return;
    const raw = el.value;
    if (el.type === "number") {
      agent[el.id] = raw.includes(".") ? parseFloat(raw) : parseInt(raw, 10);
    } else {
      agent[el.id] = raw;
    }
  });
  return agent;
}

async function saveConfig(message) {
  const msg = document.getElementById("status-msg");
  try {
    const res = await api("/api/config", {
      method: "PUT",
      body: JSON.stringify({
        agent: collectAgent(),
        prompt: { system_prompt: document.getElementById("system_prompt").value },
      }),
    });
    msg.textContent = message || res.message;
    await loadConfig();
  } catch (e) {
    msg.textContent = e.message;
  }
}

async function refreshPreflight() {
  const data = await api("/api/preflight");
  const ul = document.getElementById("preflight-list");
  ul.innerHTML = "";
  data.checks.forEach((c) => {
    const li = document.createElement("li");
    const icon = c.ok ? "✓" : "✗";
    const cls = c.ok ? "check-ok" : "check-fail";
    li.innerHTML = `<span class="${cls}">${icon}</span> <strong>${c.name}</strong> — ${c.detail}${
      c.fix && !c.ok ? `<br><span class="hint">Fix: ${c.fix}</span>` : ""
    }`;
    ul.appendChild(li);
  });
  return data.ready;
}

async function refreshStatus() {
  const st = await api("/api/agent/status");
  setStatus(st.running, st.pid);
  return st.running;
}

function renderTranscript(items) {
  const box = document.getElementById("transcript");
  if (!items.length) {
    box.innerHTML = '<p class="hint">Start a call — conversation lines appear here.</p>';
    return;
  }
  box.innerHTML = "";
  items.forEach((item) => {
    const div = document.createElement("div");
    div.className = `bubble ${item.role}`;
    div.innerHTML = `<div class="who">${item.role === "user" ? "You" : "Priya"}</div>${escapeHtml(item.text)}`;
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function refreshLogs() {
  if (logsCleared) return;
  const data = await api("/api/agent/logs?tail=300");
  const pre = document.getElementById("logs");
  pre.textContent = data.lines.join("\n");
  pre.scrollTop = pre.scrollHeight;
  renderTranscript(data.transcript || []);
}

document.getElementById("btn-save").onclick = () =>
  saveConfig("Settings saved. Restart the agent to apply while a call is running.");

document.getElementById("btn-start").onclick = async () => {
  const msg = document.getElementById("status-msg");
  try {
    const ready = await refreshPreflight();
    if (!ready) {
      msg.textContent = "Fix Setup checklist items first.";
      showPanel("panel-setup");
      return;
    }
    await api("/api/agent/start", { method: "POST" });
    msg.textContent = "Agent running — speak when Priya finishes. Allow microphone if macOS asks.";
    logsCleared = false;
    await refreshStatus();
    showPanel("panel-session");
  } catch (e) {
    msg.textContent = e.message;
  }
};

document.getElementById("btn-stop").onclick = async () => {
  await api("/api/agent/stop", { method: "POST" });
  document.getElementById("status-msg").textContent = "Agent stopped.";
  await refreshStatus();
};

document.getElementById("btn-restart").onclick = async () => {
  const msg = document.getElementById("status-msg");
  try {
    await saveConfig();
    const res = await api("/api/agent/restart", { method: "POST" });
    msg.textContent = res.message || "Restarted.";
    logsCleared = false;
    await refreshStatus();
  } catch (e) {
    msg.textContent = e.message;
  }
};

document.getElementById("btn-refresh-preflight").onclick = refreshPreflight;
document.getElementById("btn-clear-logs").onclick = () => {
  logsCleared = true;
  document.getElementById("logs").textContent = "";
};

(async () => {
  await loadConfig();
  await refreshPreflight();
  await refreshStatus();
  setInterval(refreshStatus, 4000);
  setInterval(refreshLogs, 2000);
})();
