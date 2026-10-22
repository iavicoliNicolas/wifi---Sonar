const stateNode = document.querySelector("#state");
const detailNode = document.querySelector("#detail");
const connectionNode = document.querySelector("#connection");
const heatmap = document.querySelector("#heatmap");
const scoreCanvas = document.querySelector("#score");
const timeline = document.querySelector("#timeline");

const MAX_COLUMNS = 240;
const MAX_EVENTS = 40;
const columns = new Array(MAX_COLUMNS);
const scores = new Array(MAX_COLUMNS);
let columnCount = 0;
let columnHead = 0;
let thresholds = { on_threshold: 0.75, hysteresis: 0.35 };
let lastState = null;

const labels = {
  vacío: "vacío",
  presencia: "presencia",
  movimiento: "movimiento",
};

function pushColumn(values) {
  columns[columnHead] = values;
  columnHead = (columnHead + 1) % MAX_COLUMNS;
  if (columnCount < MAX_COLUMNS) {
    columnCount += 1;
  }
}

function pushScore(value) {
  scores[columnHead === 0 ? MAX_COLUMNS - 1 : columnHead - 1] = value;
}

function recentColumns() {
  const ordered = [];
  const start = (columnHead - columnCount + MAX_COLUMNS) % MAX_COLUMNS;
  for (let index = 0; index < columnCount; index += 1) {
    ordered.push(columns[(start + index) % MAX_COLUMNS]);
  }
  return ordered;
}

function renderState(snapshot) {
  const state = labels[snapshot.state] || snapshot.state || "—";
  stateNode.textContent = state;
  stateNode.dataset.state = state;
  const score = Number(snapshot.score || 0);
  const calibrated = snapshot.calibrated ? "calibrado" : "sin calibrar";
  detailNode.textContent = `${calibrated} · score ${score.toFixed(2)}`;
  renderSensing(snapshot);
  if (state !== lastState) {
    lastState = state;
    const item = document.createElement("li");
    const label = document.createElement("span");
    const when = document.createElement("time");
    label.textContent = state;
    when.textContent = snapshot.ts == null ? "" : `${Number(snapshot.ts).toFixed(1)} s`;
    item.append(label, when);
    timeline.prepend(item);
    while (timeline.children.length > MAX_EVENTS) {
      timeline.removeChild(timeline.lastElementChild);
    }
  }
}

function drawHeatmap() {
  const context = heatmap.getContext("2d");
  const width = heatmap.width;
  const height = heatmap.height;
  context.clearRect(0, 0, width, height);
  const series = recentColumns();
  if (!series.length || !series[0]) {
    return;
  }
  const image = context.createImageData(width, height);
  const subcarriers = series[0].length;
  for (let x = 0; x < width; x += 1) {
    const column = series[Math.floor((x / width) * series.length)];
    for (let y = 0; y < height; y += 1) {
      const bin = Math.min(subcarriers - 1, Math.floor((y / height) * subcarriers));
      const value = Math.max(-1, Math.min(1, Number(column[bin]) || 0));
      const offset = (y * width + x) * 4;
      image.data[offset] = value > 0 ? 40 + value * 180 : 20;
      image.data[offset + 1] = 70 + Math.abs(value) * 80;
      image.data[offset + 2] = value < 0 ? 40 + -value * 140 : 60;
      image.data[offset + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
}

function drawScore() {
  const context = scoreCanvas.getContext("2d");
  const width = scoreCanvas.width;
  const height = scoreCanvas.height;
  context.clearRect(0, 0, width, height);
  const on = thresholds.on_threshold;
  const off = Math.max(0, on - thresholds.hysteresis);
  context.strokeStyle = "#5c6b64";
  context.setLineDash([4, 4]);
  for (const level of [on, off]) {
    const y = height - level * (height - 16) - 8;
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }
  context.setLineDash([]);
  context.strokeStyle = "#e2b15a";
  context.lineWidth = 2;
  context.beginPath();
  for (let index = 0; index < columnCount; index += 1) {
    const slot = (columnHead - columnCount + index + MAX_COLUMNS) % MAX_COLUMNS;
    const value = Number(scores[slot] || 0);
    const x = (index / Math.max(1, columnCount - 1)) * (width - 8) + 4;
    const y = height - value * (height - 16) - 8;
    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  }
  context.stroke();
}

function pushSnapshot(snapshot) {
  if (Array.isArray(snapshot.amplitudes) && snapshot.amplitudes.length) {
    pushColumn(snapshot.amplitudes.slice(0, 64));
    pushScore(Number(snapshot.score) || 0);
  }
  renderStateWithAlert(snapshot);
}

function frame() {
  drawHeatmap();
  drawScore();
  window.requestAnimationFrame(frame);
}

function setLive(live) {
  connectionNode.textContent = live ? "en vivo" : "desconectado";
  connectionNode.classList.toggle("live", live);
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  socket.onopen = () => setLive(true);
  socket.onclose = () => {
    setLive(false);
    window.setTimeout(connect, 1000);
  };
  socket.onerror = () => socket.close();
  socket.onmessage = (event) => {
    pushSnapshot(JSON.parse(event.data));
  };
}

const sensitivityInput = document.querySelector("#sensitivity");
const windowInput = document.querySelector("#window");
const hysteresisInput = document.querySelector("#hysteresis");
const webhookInput = document.querySelector("#webhook");
const alertsInput = document.querySelector("#alerts");
const settingsNote = document.querySelector("#settings-note");
let saveTimer = 0;

const sensingNode = document.querySelector("#sensing");
const pauseButton = document.querySelector("#pause");
const retentionNode = document.querySelector("#retention");
let paused = false;

function applyPaused(isPaused) {
  paused = Boolean(isPaused);
  sensingNode.textContent = paused ? "Sensado en pausa" : "Sensado activo";
  sensingNode.dataset.paused = paused ? "1" : "0";
  pauseButton.textContent = paused ? "Reanudar" : "Pausar";
}

function renderSensing(snapshot) {
  applyPaused(snapshot.paused);
}

function fillSettings(config) {
  thresholds = config;
  sensitivityInput.value = String(config.sensitivity);
  windowInput.value = String(config.window_s);
  hysteresisInput.value = String(config.hysteresis);
  webhookInput.value = config.webhook_url || "";
  settingsNote.textContent = `Sensibilidad ${config.sensitivity} · ventana ${config.window_s}s · histéresis ${config.hysteresis}`;
  retentionNode.textContent = `El historial se conserva ${config.retention_days} días en esta máquina.`;
  applyPaused(config.paused);
}

function scheduleSave() {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(async () => {
    const payload = {
      sensitivity: Number(sensitivityInput.value),
      window_s: Number(windowInput.value),
      hysteresis: Number(hysteresisInput.value),
      webhook_url: webhookInput.value.trim(),
    };
    const response = await fetch("/config", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      fillSettings(await response.json());
    }
  }, 200);
}

for (const input of [sensitivityInput, windowInput, hysteresisInput, webhookInput]) {
  input.addEventListener("change", scheduleSave);
  input.addEventListener("input", scheduleSave);
}

pauseButton.addEventListener("click", async () => {
  const response = await fetch("/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ paused: !paused }),
  });
  if (response.ok) {
    fillSettings(await response.json());
  }
});

document.querySelector("#erase").addEventListener("click", async () => {
  if (!window.confirm("¿Borrar el historial guardado en esta máquina?")) {
    return;
  }
  const response = await fetch("/history", { method: "DELETE" });
  if (response.ok) {
    timeline.replaceChildren();
  }
});

alertsInput.addEventListener("change", () => {
  if (alertsInput.checked && "Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
});

const originalRender = renderState;
function renderStateWithAlert(snapshot) {
  const previous = lastState;
  originalRender(snapshot);
  if (
    alertsInput.checked &&
    previous &&
    snapshot.state !== previous &&
    "Notification" in window &&
    Notification.permission === "granted"
  ) {
    new Notification("WiFi Sonar", { body: snapshot.state });
  }
}

fetch("/config")
  .then((response) => response.json())
  .then(fillSettings)
  .catch(() => {});

window.__sonar = {
  pushSnapshot,
  columnCount: () => columnCount,
  maxColumns: MAX_COLUMNS,
  eventCount: () => timeline.children.length,
};

const wizard = document.querySelector("#wizard");
const countdownNode = document.querySelector("#countdown");
const wizardResult = document.querySelector("#wizard-result");
const wizardStart = document.querySelector("#wizard-start");

document.querySelector("#calibrate").addEventListener("click", () => {
  countdownNode.textContent = "";
  wizardResult.textContent = "";
  wizard.showModal();
});

document.querySelector("#wizard-close").addEventListener("click", () => wizard.close());

wizardStart.addEventListener("click", async () => {
  wizardStart.disabled = true;
  try {
    for (let left = 3; left >= 1; left -= 1) {
      countdownNode.textContent = String(left);
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    countdownNode.textContent = "capturando…";
    const response = await fetch("/calibrate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ seconds: 12 }),
    });
    const body = await response.json();
    if (!response.ok) {
      wizardResult.textContent = body.detail || "No se pudo calibrar.";
      return;
    }
    const threshold = Number(body.thresholds.motion_energy).toFixed(4);
    wizardResult.textContent = `Calidad: ${body.quality}. Umbral de movimiento ${threshold}.`;
  } finally {
    wizardStart.disabled = false;
  }
});

window.requestAnimationFrame(frame);
connect();
