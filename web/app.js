const stateNode = document.querySelector("#state");
const detailNode = document.querySelector("#detail");
const connectionNode = document.querySelector("#connection");

const labels = {
  vacío: "vacío",
  presencia: "presencia",
  movimiento: "movimiento",
};

function render(snapshot) {
  const state = labels[snapshot.state] || snapshot.state || "—";
  stateNode.textContent = state;
  stateNode.dataset.state = state;
  const score = Number(snapshot.score || 0);
  const calibrated = snapshot.calibrated ? "calibrado" : "sin calibrar";
  detailNode.textContent = `${calibrated} · score ${score.toFixed(2)}`;
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
    render(JSON.parse(event.data));
  };
}

connect();
