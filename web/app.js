const stateEl = document.querySelector("#state");
const scoreEl = document.querySelector("#score");
const linkEl = document.querySelector("#link");
const heatCanvas = document.querySelector("#heatmap");
const scoreCanvas = document.querySelector("#scoreboard");
const timeline = document.querySelector("#timeline");

const NAMES = { empty: "vacío", presence: "presencia", motion: "movimiento" };
const HEAT_COLS = 180;
const SCORE_CAP = 180;
const heat = [];
const scores = [];
let lastState = "";
let drawQueued = false;

function apply(payload) {
  const name = NAMES[payload.state] || payload.state;
  stateEl.textContent = name;
  stateEl.dataset.state = payload.state;
  const score = Number(payload.score || 0);
  scoreEl.textContent = "score " + score.toFixed(2);
  if (Array.isArray(payload.amplitudes)) {
    heat.push(payload.amplitudes.slice());
    if (heat.length > HEAT_COLS) heat.shift();
  }
  scores.push(score);
  if (scores.length > SCORE_CAP) scores.shift();
  if (payload.state !== lastState) {
    lastState = payload.state;
    const item = document.createElement("li");
    item.textContent = name;
    const stamp = document.createElement("span");
    stamp.textContent = Number(payload.ts || 0).toFixed(1) + " s";
    item.append(stamp);
    timeline.prepend(item);
    while (timeline.children.length > 12) timeline.lastChild.remove();
  }
  scheduleDraw();
}

function scheduleDraw() {
  if (drawQueued) return;
  drawQueued = true;
  requestAnimationFrame(() => {
    drawQueued = false;
    drawHeat();
    drawScore();
  });
}

function drawHeat() {
  const ctx = heatCanvas.getContext("2d");
  const width = heatCanvas.width;
  const height = heatCanvas.height;
  ctx.clearRect(0, 0, width, height);
  if (!heat.length) return;
  const rows = heat[0].length || 1;
  const colWidth = width / HEAT_COLS;
  const rowHeight = height / rows;
  heat.forEach((column, index) => {
    column.forEach((value, row) => {
      const tone = Math.max(0, Math.min(1, (value - 0.6) / 1.2));
      ctx.fillStyle = "rgb(" + Math.round(40 + tone * 200) + "," + Math.round(50 + tone * 80) + ",40)";
      const x = width - (heat.length - index) * colWidth;
      ctx.fillRect(x, row * rowHeight, colWidth + 0.5, rowHeight + 0.5);
    });
  });
}

function drawScore() {
  const ctx = scoreCanvas.getContext("2d");
  const width = scoreCanvas.width;
  const height = scoreCanvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#5c5848";
  ctx.beginPath();
  ctx.moveTo(0, height * 0.5);
  ctx.lineTo(width, height * 0.5);
  ctx.stroke();
  ctx.strokeStyle = "#d6f25c";
  ctx.beginPath();
  scores.forEach((score, index) => {
    const x = width - (scores.length - index) * (width / SCORE_CAP);
    const y = height - score * (height - 8) - 4;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(protocol + "://" + location.host + "/ws");
  socket.onopen = () => {
    linkEl.textContent = "conectado";
    linkEl.dataset.state = "on";
  };
  socket.onclose = () => {
    linkEl.textContent = "reconectando";
    linkEl.dataset.state = "off";
    setTimeout(connect, 1000);
  };
  socket.onmessage = (event) => {
    apply(JSON.parse(event.data));
  };
}

const calButton = document.querySelector("#cal-start");
const calPrompt = document.querySelector("#cal-prompt");
const calCount = document.querySelector("#cal-count");
const calResult = document.querySelector("#cal-result");
let calibrating = false;

async function calibrateRoom() {
  if (calibrating) return;
  calibrating = true;
  calButton.disabled = true;
  calResult.textContent = "";
  calPrompt.textContent = "salí de la habitación";
  calCount.hidden = false;
  for (let left = 5; left >= 1; left -= 1) {
    calCount.textContent = String(left);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  calCount.textContent = "capturando";
  const response = await fetch("/calibrate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ seconds: 12 }),
  });
  const body = await response.json();
  const quality = body.quality || {};
  calPrompt.textContent = "listo";
  calCount.hidden = true;
  calResult.textContent = (quality.label || "error") + " — " + (quality.detail || "");
  calButton.disabled = false;
  calibrating = false;
}

calButton.addEventListener("click", () => {
  calibrateRoom();
});

connect();
