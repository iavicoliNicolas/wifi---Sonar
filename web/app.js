const stateNode = document.querySelector("#state");
const detailNode = document.querySelector("#detail");
const occupancyNode = document.querySelector("#occupancy");
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
  renderOccupancy(snapshot);
  renderSensing(snapshot);
  renderZones(snapshot);
  renderSpace(snapshot);
  renderMode(snapshot.mode);
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

function renderOccupancy(snapshot) {
  if (!snapshot.calibrated) {
    occupancyNode.textContent = "Personas en alcance: —";
    return;
  }
  const label = snapshot.occupancy_label || "0";
  const low = Boolean(snapshot.occupancy_low_confidence);
  occupancyNode.textContent = low
    ? `Personas en alcance: ${label} · confianza baja`
    : `Personas en alcance: ${label}`;
}

function displayRange(series) {
  const values = [];
  for (const column of series) {
    if (!column) {
      continue;
    }
    for (const raw of column) {
      const value = Number(raw);
      if (Number.isFinite(value) && Math.abs(value) > 1e-4) {
        values.push(value);
      }
    }
  }
  if (!values.length) {
    return { low: 0, high: 1 };
  }
  values.sort((left, right) => left - right);
  const low = values[Math.floor((values.length - 1) * 0.05)];
  const high = values[Math.ceil((values.length - 1) * 0.95)];
  if (high - low < 1e-4) {
    return { low: low - 0.05, high: high + 0.05 };
  }
  return { low, high };
}

function fitCanvas(node) {
  const width = Math.floor(node.clientWidth);
  if (width < 2) {
    return;
  }
  const height = Math.max(2, Math.round(width / 4));
  if (node.width !== width || node.height !== height) {
    node.width = width;
    node.height = height;
  }
}

function drawHeatmap() {
  fitCanvas(heatmap);
  const context = heatmap.getContext("2d");
  const width = heatmap.width;
  const height = heatmap.height;
  context.clearRect(0, 0, width, height);
  const series = recentColumns();
  if (!series.length || !series[0]) {
    return;
  }
  const range = displayRange(series);
  const span = range.high - range.low;
  const image = context.createImageData(width, height);
  const subcarriers = series[0].length;
  for (let x = 0; x < width; x += 1) {
    const column = series[Math.floor((x / width) * series.length)];
    for (let y = 0; y < height; y += 1) {
      const bin = Math.min(subcarriers - 1, Math.floor((y / height) * subcarriers));
      const raw = Number(column[bin]);
      const missing = !Number.isFinite(raw) || Math.abs(raw) <= 1e-4;
      const tone = missing ? 0 : Math.max(0, Math.min(1, (raw - range.low) / span));
      const offset = (y * width + x) * 4;
      image.data[offset] = missing ? 22 : Math.round(18 + tone * 214);
      image.data[offset + 1] = missing ? 28 : Math.round(48 + Math.sin(tone * Math.PI) * 120);
      image.data[offset + 2] = missing ? 32 : Math.round(78 * (1 - tone) + 24);
      image.data[offset + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
}

function drawScore() {
  fitCanvas(scoreCanvas);
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

function renderZones(snapshot) {
  const list = document.querySelector("#zones");
  const rows = Array.isArray(snapshot.nodes) ? snapshot.nodes : [];
  if (!rows.length) {
    list.replaceChildren();
    const item = document.createElement("li");
    item.textContent = "sin zonas";
    list.append(item);
    return;
  }
  const existing = new Map(
    [...list.querySelectorAll("li[data-node]")].map((item) => [item.dataset.node, item]),
  );
  const next = document.createDocumentFragment();
  for (const row of rows) {
    const nodeId = row.node_id || "";
    let item = existing.get(nodeId);
    if (!item) {
      item = document.createElement("li");
      item.dataset.node = nodeId;
      const field = document.createElement("label");
      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = 40;
      input.placeholder = nodeId || "zona";
      input.setAttribute("aria-label", `Nombre de la zona ${nodeId}`);
      input.addEventListener("change", saveZones);
      const device = document.createElement("small");
      device.textContent = nodeId;
      field.append(input, device);
      const state = document.createElement("span");
      state.className = "zone-state";
      item.append(field, state);
    }
    const input = item.querySelector("input");
    if (document.activeElement !== input) {
      input.value = row.zone || "";
    }
    item.querySelector(".zone-state").textContent = labels[row.state] || row.state || "—";
    next.append(item);
  }
  list.replaceChildren(next);
}

const floorNode = document.querySelector("#floor");
let spaceLayout = {};
let spaceDrag = null;
let lastRows = [];

function defaultPoint(index, total) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(total)));
  const rows = Math.max(1, Math.ceil(total / cols));
  return {
    x: (index % cols + 1) / (cols + 1),
    y: (Math.floor(index / cols) + 1) / (rows + 1),
  };
}

function clampUnit(value) {
  return Math.min(0.88, Math.max(0.12, value));
}

function pointsFor(rows) {
  const placed = {};
  rows.forEach((row, index) => {
    const nodeId = row.node_id || "";
    const saved = spaceLayout[nodeId];
    if (saved && Number.isFinite(Number(saved.x)) && Number.isFinite(Number(saved.y))) {
      placed[nodeId] = { x: Number(saved.x), y: Number(saved.y) };
      return;
    }
    placed[nodeId] = defaultPoint(index, rows.length);
  });
  return placed;
}

function renderSpace(snapshot) {
  const rows = Array.isArray(snapshot.nodes) ? snapshot.nodes : [];
  lastRows = rows;
  if (!rows.length) {
    floorNode.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "space-empty";
    empty.textContent = "Todavía no hay nodos.";
    floorNode.append(empty);
    return;
  }
  const placed = pointsFor(rows);
  const existing = new Map(
    [...floorNode.querySelectorAll(".space-marker")].map((marker) => [marker.dataset.node, marker]),
  );
  const next = document.createDocumentFragment();
  for (const row of rows) {
    const nodeId = row.node_id || "";
    let marker = existing.get(nodeId);
    if (!marker) {
      marker = document.createElement("button");
      marker.type = "button";
      marker.className = "space-marker";
      marker.dataset.node = nodeId;
    }
    const name = row.zone || nodeId || "zona";
    const state = labels[row.state] || row.state || "—";
    marker.dataset.state = state;
    marker.textContent = `${name} · ${state}`;
    marker.setAttribute("aria-label", `${name}, ${state}. Arrastrá para ubicar la zona.`);
    const point = placed[nodeId];
    marker.style.left = `${point.x * 100}%`;
    marker.style.top = `${point.y * 100}%`;
    next.append(marker);
  }
  floorNode.replaceChildren(next);
}

function saveLayout() {
  fetch("/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ layout: spaceLayout }),
  })
    .then((response) => (response.ok ? response.json() : null))
    .then((config) => {
      if (config && !spaceDrag) {
        spaceLayout = config.layout || {};
      }
    })
    .catch(() => {});
}

floorNode.addEventListener("pointerdown", (event) => {
  const marker = event.target.closest(".space-marker");
  if (!marker) {
    return;
  }
  spaceDrag = { id: marker.dataset.node, pointer: event.pointerId };
  marker.setPointerCapture(event.pointerId);
});

floorNode.addEventListener("pointermove", (event) => {
  if (!spaceDrag || event.pointerId !== spaceDrag.pointer) {
    return;
  }
  const rect = floorNode.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) {
    return;
  }
  spaceLayout = {
    ...pointsFor(lastRows),
    [spaceDrag.id]: {
      x: clampUnit((event.clientX - rect.left) / rect.width),
      y: clampUnit((event.clientY - rect.top) / rect.height),
    },
  };
  const marker = floorNode.querySelector(`[data-node="${CSS.escape(spaceDrag.id)}"]`);
  if (!marker) {
    return;
  }
  marker.style.left = `${spaceLayout[spaceDrag.id].x * 100}%`;
  marker.style.top = `${spaceLayout[spaceDrag.id].y * 100}%`;
});

floorNode.addEventListener("pointerup", (event) => {
  if (!spaceDrag || event.pointerId !== spaceDrag.pointer) {
    return;
  }
  spaceDrag = null;
  saveLayout();
});

floorNode.addEventListener("pointercancel", () => {
  spaceDrag = null;
});

function saveZones() {
  const zones = {};
  for (const item of document.querySelectorAll("#zones li[data-node]")) {
    const name = item.querySelector("input").value.trim();
    if (name) {
      zones[item.dataset.node] = name;
    }
  }
  fetch("/config", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ zones }),
  }).catch(() => {});
}

function applyPaused(isPaused) {
  paused = Boolean(isPaused);
  sensingNode.textContent = paused ? "Sensado en pausa" : "Sensado activo";
  sensingNode.dataset.paused = paused ? "1" : "0";
  pauseButton.textContent = paused ? "Reanudar" : "Pausar";
}

function renderSensing(snapshot) {
  applyPaused(snapshot.paused);
}

function paintControlValues() {
  document.querySelector("#sensitivity-value").textContent = sensitivityInput.value;
  document.querySelector("#window-value").textContent = windowInput.value;
  document.querySelector("#hysteresis-value").textContent = hysteresisInput.value;
}

function fillSettings(config) {
  thresholds = config;
  sensitivityInput.value = String(config.sensitivity);
  windowInput.value = String(config.window_s);
  hysteresisInput.value = String(config.hysteresis);
  webhookInput.value = config.webhook_url || "";
  paintControlValues();
  settingsNote.textContent = `Sensibilidad ${config.sensitivity} · ventana ${config.window_s}s · histéresis ${config.hysteresis}`;
  retentionNode.textContent = `El historial se conserva ${config.retention_days} días en esta máquina.`;
  applyPaused(config.paused);
  renderMode(config.mode);
  if (!spaceDrag) {
    spaceLayout = config.layout || {};
    renderSpace(lastRows.length ? { nodes: lastRows } : { nodes: [] });
  }
}

function renderMode(mode) {
  document.querySelector("#mode-note").hidden = mode !== "rssi";
}

let editSeq = 0;

function scheduleSave() {
  paintControlValues();
  const seq = ++editSeq;
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
    if (!response.ok || seq !== editSeq) {
      return;
    }
    fillSettings(await response.json());
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

document.querySelector("#record").addEventListener("click", async () => {
  const response = await fetch("/recording", { method: "POST" });
  const body = await response.json().catch(() => ({}));
  settingsNote.textContent = response.ok
    ? `Traza guardada en esta máquina (${body.frames} frames).`
    : body.detail || "No hay traza para guardar.";
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
  displayRange,
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
