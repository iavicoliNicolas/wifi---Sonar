const stateEl = document.querySelector("#state");
const scoreEl = document.querySelector("#score");
const linkEl = document.querySelector("#link");

const NAMES = { empty: "vacío", presence: "presencia", motion: "movimiento" };

function apply(payload) {
  const name = NAMES[payload.state] || payload.state;
  stateEl.textContent = name;
  stateEl.dataset.state = payload.state;
  const score = Number(payload.score || 0);
  scoreEl.textContent = "score " + score.toFixed(2);
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

connect();
