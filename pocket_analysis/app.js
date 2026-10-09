"use strict";

const SVG_NS = "http://www.w3.org/2000/svg";
const THREAT_RADIUS = 2.5;

const state = {
  manifest: null,
  game: null,
  play: null,
  frameIndex: 0,
  timer: null,
  speed: 1,
  cache: new Map(),
  loadToken: 0,
};

const el = {};

function cacheElements() {
  const ids = [
    "loading", "error-banner", "game-select", "play-select", "speed-select",
    "play-button", "reset-button", "step-back", "step-forward", "frame-slider",
    "show-matchups", "field-svg", "timeline-svg", "current-time", "frame-count",
    "context-title", "result-badge", "context-situation", "context-matchup",
    "context-formation", "context-coverage", "context-dropback", "context-action",
    "play-description", "coaching-read", "metric-threat", "metric-threat-note",
    "metric-lane", "metric-rusher", "metric-rusher-note", "metric-pressure",
    "metric-duration", "matchup-body",
  ];
  ids.forEach((id) => { el[id] = document.getElementById(id); });
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Unable to load ${path} (${response.status})`);
  }
  return response.json();
}

function showError(message) {
  el["error-banner"].textContent = message;
  el["error-banner"].hidden = false;
}

function clearError() {
  el["error-banner"].hidden = true;
  el["error-banner"].textContent = "";
}

function setLoading(isLoading) {
  el.loading.classList.toggle("hidden", !isLoading);
}

function addOption(select, value, label, selected = false) {
  const option = document.createElement("option");
  option.value = String(value);
  option.textContent = label;
  option.selected = selected;
  select.appendChild(option);
}

function querySelection() {
  const params = new URLSearchParams(window.location.search);
  return {
    gameId: params.get("game"),
    playId: params.get("play"),
  };
}

function updateShareUrl() {
  if (!state.game || !state.play) return;
  const url = new URL(window.location.href);
  url.searchParams.set("game", state.game.game.id);
  url.searchParams.set("play", state.play.id);
  window.history.replaceState({}, "", url);
}

async function initialize() {
  cacheElements();
  bindControls();
  try {
    state.manifest = await fetchJson("./data/manifest.json");
    THREAT_RADIUS_VALUE = state.manifest.threatRadiusYards || THREAT_RADIUS;
    populateGames();
    const selected = querySelection();
    const initialGame = state.manifest.games.some((game) => String(game.id) === selected.gameId)
      ? selected.gameId
      : String(state.manifest.games[0].id);
    el["game-select"].value = initialGame;
    await loadGame(initialGame, selected.playId);
  } catch (error) {
    showError(`${error.message}. Build the dashboard data and serve the docs folder over HTTP.`);
  } finally {
    setLoading(false);
  }
}

let THREAT_RADIUS_VALUE = THREAT_RADIUS;

function populateGames() {
  el["game-select"].replaceChildren();
  state.manifest.games.forEach((game) => {
    addOption(el["game-select"], game.id, `${game.label} · ${game.plays} plays`);
  });
  el["game-select"].disabled = false;
}

async function loadGame(gameId, requestedPlayId = null) {
  const token = ++state.loadToken;
  stopPlayback();
  clearError();
  el["game-select"].disabled = true;
  el["play-select"].disabled = true;

  try {
    let payload = state.cache.get(String(gameId));
    if (!payload) {
      const manifestGame = state.manifest.games.find((game) => String(game.id) === String(gameId));
      if (!manifestGame) throw new Error("Selected game is not in the manifest");
      payload = await fetchJson(`./${manifestGame.file}`);
      state.cache.set(String(gameId), payload);
    }
    if (token !== state.loadToken) return;

    state.game = payload;
    populatePlays(requestedPlayId);
    const selectedPlayId = el["play-select"].value;
    selectPlay(selectedPlayId);
  } catch (error) {
    showError(error.message);
  } finally {
    if (token === state.loadToken) {
      el["game-select"].disabled = false;
      el["play-select"].disabled = false;
    }
  }
}

function populatePlays(requestedPlayId) {
  el["play-select"].replaceChildren();
  const requestedExists = state.game.plays.some((play) => String(play.id) === String(requestedPlayId));
  state.game.plays.forEach((play, index) => {
    const selected = requestedExists
      ? String(play.id) === String(requestedPlayId)
      : index === 0;
    addOption(el["play-select"], play.id, `#${play.id} · ${play.label}`, selected);
  });
}

function selectPlay(playId) {
  stopPlayback();
  state.play = state.game.plays.find((play) => String(play.id) === String(playId));
  if (!state.play) return;

  renderPlaySummary();
  renderMatchups();
  el["frame-slider"].min = "0";
  el["frame-slider"].max = String(state.play.frames.length - 1);
  el["frame-slider"].value = "0";
  el["frame-slider"].disabled = false;
  setFrame(0);
  updateShareUrl();
}

function bindControls() {
  el["game-select"].addEventListener("change", (event) => loadGame(event.target.value));
  el["play-select"].addEventListener("change", (event) => selectPlay(event.target.value));
  el["play-button"].addEventListener("click", togglePlayback);
  el["reset-button"].addEventListener("click", () => { stopPlayback(); setFrame(0); });
  el["step-back"].addEventListener("click", () => { stopPlayback(); setFrame(state.frameIndex - 1); });
  el["step-forward"].addEventListener("click", () => { stopPlayback(); setFrame(state.frameIndex + 1); });
  el["frame-slider"].addEventListener("pointerdown", stopPlayback);
  el["frame-slider"].addEventListener("input", (event) => setFrame(Number(event.target.value), false));
  el["speed-select"].addEventListener("change", (event) => changeSpeed(Number(event.target.value)));
  el["show-matchups"].addEventListener("change", () => renderField(state.frameIndex));
  document.addEventListener("keydown", handleKeyboard);
}

function handleKeyboard(event) {
  if (!state.play || ["SELECT", "INPUT", "BUTTON"].includes(document.activeElement?.tagName)) return;
  if (event.code === "Space") {
    event.preventDefault();
    togglePlayback();
  } else if (event.code === "ArrowLeft") {
    event.preventDefault();
    stopPlayback();
    setFrame(state.frameIndex - 1);
  } else if (event.code === "ArrowRight") {
    event.preventDefault();
    stopPlayback();
    setFrame(state.frameIndex + 1);
  }
}

function togglePlayback() {
  if (!state.play) return;
  if (state.timer !== null) {
    stopPlayback();
    return;
  }
  if (state.frameIndex >= state.play.frames.length - 1) setFrame(0);
  startPlayback();
}

function startPlayback() {
  const interval = Math.max(45, 100 / state.speed);
  state.timer = window.setInterval(() => {
    if (state.frameIndex >= state.play.frames.length - 1) {
      stopPlayback();
      return;
    }
    setFrame(state.frameIndex + 1);
  }, interval);
  el["play-button"].textContent = "❚❚ PAUSE";
  el["play-button"].classList.add("playing");
  el["play-button"].setAttribute("aria-label", "Pause animation");
}

function stopPlayback() {
  if (state.timer !== null) {
    window.clearInterval(state.timer);
    state.timer = null;
  }
  if (el["play-button"]) {
    el["play-button"].textContent = "▶ PLAY";
    el["play-button"].classList.remove("playing");
    el["play-button"].setAttribute("aria-label", "Play animation");
  }
}

function changeSpeed(speed) {
  const wasPlaying = state.timer !== null;
  stopPlayback();
  state.speed = speed;
  if (wasPlaying) startPlayback();
}

function setFrame(index, syncSlider = true) {
  if (!state.play) return;
  const lastIndex = state.play.frames.length - 1;
  state.frameIndex = Math.max(0, Math.min(lastIndex, Math.round(index)));
  if (syncSlider) el["frame-slider"].value = String(state.frameIndex);
  const frame = state.play.frames[state.frameIndex];
  el["current-time"].textContent = `${frame.t.toFixed(1)}s`;
  el["frame-count"].textContent = `FRAME ${state.frameIndex + 1} / ${state.play.frames.length}`;
  renderField(state.frameIndex);
  renderTimeline(state.frameIndex);
}

function person(play, id) {
  return play.people[String(id)] || { n: `Player ${id}`, j: null, p: "—", r: "—" };
}

function lastName(name) {
  const parts = String(name).trim().split(/\s+/);
  return parts[parts.length - 1];
}

function seconds(value, missing = "NO ENTRY") {
  return value === null || value === undefined ? missing : `${Number(value).toFixed(1)}s`;
}

function shortLane(lane) {
  if (lane.startsWith("Offense left")) return "OFF. LEFT";
  if (lane.startsWith("Offense right")) return "OFF. RIGHT";
  if (lane === "Interior") return "INTERIOR";
  return "NO ENTRY";
}

function timingLabel(threatTime) {
  if (threatTime === null || threatTime === undefined) return "No nearby threat";
  if (threatTime <= 2.0) return "Quick threat";
  if (threatTime <= 2.5) return "On-time threat";
  return "Late threat";
}

function renderPlaySummary() {
  const play = state.play;
  const meta = play.meta;
  const summary = play.summary;
  const game = state.game.game;
  const threatPerson = summary.threatRusher ? person(play, summary.threatRusher) : null;

  el["context-title"].textContent = `Q${meta.q} · ${meta.clock}`;
  el["result-badge"].textContent = meta.result;
  el["result-badge"].className = `result-badge ${String(meta.result).toLowerCase()}`;
  el["context-situation"].textContent = `${meta.down} & ${meta.toGo}`;
  el["context-matchup"].textContent = `${meta.off} offense · ${meta.def} defense`;
  el["context-formation"].textContent = meta.formation;
  el["context-coverage"].textContent = meta.coverage;
  el["context-dropback"].textContent = meta.dropback.replaceAll("_", " ");
  el["context-action"].textContent = meta.playAction ? "Yes" : "No";
  el["play-description"].textContent = meta.description;

  el["metric-threat"].textContent = seconds(summary.threatTime);
  el["metric-threat-note"].textContent = timingLabel(summary.threatTime);
  el["metric-lane"].textContent = shortLane(summary.threatLane);
  el["metric-rusher"].textContent = threatPerson ? lastName(threatPerson.n).toUpperCase() : "—";
  el["metric-rusher-note"].textContent = threatPerson
    ? `#${threatPerson.j ?? "—"} · ${threatPerson.p}`
    : "No rusher crossed the reference";
  el["metric-pressure"].textContent = summary.pressureOutcome.toUpperCase();
  el["metric-duration"].textContent = seconds(summary.duration, "—");
  el["coaching-read"].textContent = buildCoachingRead(game, play);
}

function buildCoachingRead(game, play) {
  const summary = play.summary;
  const meta = play.meta;
  const movementNote = summary.maxLateral >= 3
    ? ` The quarterback moved ${summary.maxLateral.toFixed(1)} lateral yards during the pocket phase, so review whether movement contributed to the pressure picture.`
    : "";
  const rolloutNote = meta.dropback.includes("ROLLOUT") || meta.dropback.includes("SCRAMBLE")
    ? " This is not a conventional stationary pocket; interpret the triangle and lane with extra caution."
    : "";

  if (summary.threatTime === null) {
    return `No pass rusher entered the ${THREAT_RADIUS_VALUE.toFixed(1)}-yard reference area before the ${summary.duration.toFixed(1)}-second pocket phase ended. The play finished as ${meta.result.toLowerCase()} for ${meta.yards} yards.${movementNote}${rolloutNote}`;
  }

  const rusher = person(play, summary.threatRusher);
  const matchup = play.matchups.find((item) => item.r === summary.threatRusher);
  const blockers = matchup?.b?.length
    ? matchup.b.map((id) => `${person(play, id).n} (${person(play, id).p})`).join(" and ")
    : "no initial blocker recorded in the PFF pairing";
  const creditNote = summary.threatOutcome === "No pressure credit"
    ? " The proximity event did not receive a PFF pressure credit, making it a useful film-review disagreement."
    : ` PFF credited the primary threat with a ${summary.threatOutcome.toLowerCase()}.`;

  return `${timingLabel(summary.threatTime)}: ${rusher.n} entered from ${summary.threatLane.toLowerCase()} at ${summary.threatTime.toFixed(1)} seconds. Initial assignment: ${blockers}.${creditNote}${movementNote}${rolloutNote}`;
}

function renderMatchups() {
  el["matchup-body"].replaceChildren();
  if (!state.play.matchups.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "empty-cell";
    cell.textContent = "No pass-rush matchups were recorded for this play.";
    row.appendChild(cell);
    el["matchup-body"].appendChild(row);
    return;
  }

  state.play.matchups.forEach((matchup) => {
    const row = document.createElement("tr");
    const rusher = person(state.play, matchup.r);
    appendPlayerCell(row, rusher);

    const blockerCell = document.createElement("td");
    if (matchup.b.length) {
      matchup.b.forEach((id, index) => {
        const blocker = person(state.play, id);
        const line = document.createElement("span");
        line.className = index === 0 ? "player-name" : "subtext";
        line.textContent = `${blocker.n} (${blocker.p})`;
        blockerCell.appendChild(line);
      });
    } else {
      blockerCell.textContent = "No initial blocker recorded";
    }
    row.appendChild(blockerCell);

    appendTextCell(row, matchup.bt.length ? matchup.bt.join(" + ") : "—");
    appendTextCell(row, seconds(matchup.tt, "No entry"));
    appendTextCell(row, matchup.min === null ? "—" : `${matchup.min.toFixed(2)} yd`);

    const outcomeCell = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = `outcome-pill ${matchup.out.toLowerCase().replaceAll(" ", "-")}`;
    pill.textContent = matchup.out;
    outcomeCell.appendChild(pill);
    row.appendChild(outcomeCell);
    el["matchup-body"].appendChild(row);
  });
}

function appendPlayerCell(row, player) {
  const cell = document.createElement("td");
  const name = document.createElement("span");
  name.className = "player-name";
  name.textContent = player.n;
  const detail = document.createElement("span");
  detail.className = "subtext";
  detail.textContent = `#${player.j ?? "—"} · ${player.p}`;
  cell.append(name, detail);
  row.appendChild(cell);
}

function appendTextCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
}

function svgNode(tag, attributes = {}, text = null) {
  const node = document.createElementNS(SVG_NS, tag);
  Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
  if (text !== null) node.textContent = text;
  return node;
}

function addSvg(parent, tag, attributes = {}, text = null) {
  const node = svgNode(tag, attributes, text);
  parent.appendChild(node);
  return node;
}

function addSvgTitle(parent, text) {
  parent.appendChild(svgNode("title", {}, text));
}

function fieldBounds(play) {
  if (play._bounds) return play._bounds;
  const yValues = [];
  play.frames.forEach((frame) => {
    yValues.push(frame.q[2]);
    [...frame.o, ...frame.h, ...frame.r].forEach((item) => yValues.push(item[2]));
  });
  const rawMin = Math.min(...yValues);
  const rawMax = Math.max(...yValues);
  const span = Math.max(24, rawMax - rawMin + 7);
  let yMin = Math.max(0, (rawMin + rawMax - span) / 2);
  let yMax = Math.min(53.3, yMin + span);
  yMin = Math.max(0, yMax - span);

  let xMin = Math.max(0, play.los - 13);
  let xMax = Math.min(120, play.los + 9);
  if (xMax - xMin < 22) {
    xMin = Math.max(0, xMax - 22);
    xMax = Math.min(120, xMin + 22);
  }
  play._bounds = { xMin, xMax, yMin, yMax };
  return play._bounds;
}

function scales(bounds, width, height, margin) {
  return {
    x: (value) => margin.left + ((value - bounds.xMin) / (bounds.xMax - bounds.xMin)) * (width - margin.left - margin.right),
    y: (value) => height - margin.bottom - ((value - bounds.yMin) / (bounds.yMax - bounds.yMin)) * (height - margin.top - margin.bottom),
    xRate: (width - margin.left - margin.right) / (bounds.xMax - bounds.xMin),
    yRate: (height - margin.top - margin.bottom) / (bounds.yMax - bounds.yMin),
  };
}

function renderField(index) {
  if (!state.play) return;
  const svg = el["field-svg"];
  svg.replaceChildren();
  const play = state.play;
  const frame = play.frames[index];
  const width = 820;
  const height = 500;
  const margin = { top: 23, right: 20, bottom: 32, left: 36 };
  const bounds = fieldBounds(play);
  const scale = scales(bounds, width, height, margin);

  addSvg(svg, "rect", {
    x: margin.left,
    y: margin.top,
    width: width - margin.left - margin.right,
    height: height - margin.top - margin.bottom,
    class: "field-surface",
    rx: 4,
  });
  drawYardLines(svg, bounds, scale, height, margin);
  drawLineOfScrimmage(svg, play.los, scale, height, margin);
  drawRusherTrails(svg, play, index, scale);
  drawPocketShape(svg, frame, scale);
  drawThreatRadius(svg, frame, scale);
  if (el["show-matchups"].checked) drawAssignments(svg, play, frame, scale);
  drawFootball(svg, frame, scale);
  drawParticipants(svg, play, frame, scale);
  drawBreachMarker(svg, play, index, scale);

  addSvg(svg, "text", { x: width - 24, y: 17, "text-anchor": "end", class: "chart-title-text" },
    `${frame.t.toFixed(1)} SEC · ${frame.d.toFixed(2)} YD TO NEAREST RUSHER`);
}

function drawYardLines(svg, bounds, scale, height, margin) {
  const firstYard = Math.ceil(bounds.xMin / 5) * 5;
  for (let yard = firstYard; yard <= bounds.xMax; yard += 5) {
    const x = scale.x(yard);
    addSvg(svg, "line", { x1: x, y1: margin.top, x2: x, y2: height - margin.bottom, class: "field-yard-line" });
    addSvg(svg, "text", { x, y: height - 15, "text-anchor": "middle", class: "field-yard-label" }, String(yard));
  }
}

function drawLineOfScrimmage(svg, los, scale, height, margin) {
  const x = scale.x(los);
  addSvg(svg, "line", { x1: x, y1: margin.top, x2: x, y2: height - margin.bottom, class: "line-of-scrimmage" });
  addSvg(svg, "text", { x: x + 5, y: margin.top + 13, class: "los-label" }, "LINE OF SCRIMMAGE");
}

function drawPocketShape(svg, frame, scale) {
  if (frame.o.length < 2) return;
  const outside = [...frame.o].sort((a, b) => a[2] - b[2]);
  const points = [frame.q, outside[0], outside[outside.length - 1]]
    .map((item) => `${scale.x(item[1])},${scale.y(item[2])}`)
    .join(" ");
  addSvg(svg, "polygon", { points, class: "pocket-shape" });
}

function drawThreatRadius(svg, frame, scale) {
  addSvg(svg, "ellipse", {
    cx: scale.x(frame.q[1]),
    cy: scale.y(frame.q[2]),
    rx: THREAT_RADIUS_VALUE * scale.xRate,
    ry: THREAT_RADIUS_VALUE * scale.yRate,
    class: "threat-radius",
  });
}

function drawRusherTrails(svg, play, index, scale) {
  const rusherIds = play.matchups.map((matchup) => matchup.r);
  rusherIds.forEach((rusherId) => {
    const points = play.frames.slice(0, index + 1)
      .map((frame) => frame.r.find((item) => item[0] === rusherId))
      .filter(Boolean)
      .map((item) => `${scale.x(item[1])},${scale.y(item[2])}`)
      .join(" ");
    if (points) addSvg(svg, "polyline", { points, class: "rusher-trail" });
  });
}

function currentPositions(frame) {
  const positions = new Map();
  [frame.q, ...frame.o, ...frame.h, ...frame.r].forEach((item) => positions.set(item[0], item));
  return positions;
}

function drawAssignments(svg, play, frame, scale) {
  const positions = currentPositions(frame);
  play.matchups.forEach((matchup) => {
    const rusher = positions.get(matchup.r);
    if (!rusher) return;
    matchup.b.forEach((blockerId) => {
      const blocker = positions.get(blockerId);
      if (!blocker) return;
      addSvg(svg, "line", {
        x1: scale.x(blocker[1]), y1: scale.y(blocker[2]),
        x2: scale.x(rusher[1]), y2: scale.y(rusher[2]),
        class: "assignment-line",
      });
    });
  });
}

function drawFootball(svg, frame, scale) {
  if (!frame.b) return;
  addSvg(svg, "ellipse", {
    cx: scale.x(frame.b[0]), cy: scale.y(frame.b[1]), rx: 7, ry: 4,
    fill: "#9a6238", stroke: "#f1d0aa", "stroke-width": 1.2,
  });
}

function starPoints(cx, cy, outer = 14, inner = 6.5) {
  const points = [];
  for (let index = 0; index < 10; index += 1) {
    const radius = index % 2 === 0 ? outer : inner;
    const angle = -Math.PI / 2 + index * Math.PI / 5;
    points.push(`${cx + Math.cos(angle) * radius},${cy + Math.sin(angle) * radius}`);
  }
  return points.join(" ");
}

function drawParticipants(svg, play, frame, scale) {
  frame.o.forEach((item) => drawPlayer(svg, play, item, "core", scale, frame.n));
  frame.h.forEach((item) => drawPlayer(svg, play, item, "helper", scale, frame.n));
  frame.r.forEach((item) => drawPlayer(svg, play, item, "rusher", scale, frame.n));
  drawPlayer(svg, play, frame.q, "qb", scale, frame.n);
}

function drawPlayer(svg, play, item, type, scale, nearestId) {
  const [id, fieldX, fieldY] = item;
  const x = scale.x(fieldX);
  const y = scale.y(fieldY);
  const info = person(play, id);
  const group = addSvg(svg, "g", { tabindex: 0, role: "img" });
  addSvgTitle(group, `${info.n} · #${info.j ?? "—"} · ${info.p}`);

  if (id === nearestId && type === "rusher") {
    addSvg(group, "circle", { cx: x, cy: y, r: 18, class: "nearest-ring" });
  }
  if (type === "qb") {
    addSvg(group, "polygon", { points: starPoints(x, y), class: "player-qb" });
  } else if (type === "helper") {
    addSvg(group, "rect", { x: x - 10, y: y - 10, width: 20, height: 20, rx: 2,
      transform: `rotate(45 ${x} ${y})`, class: "player-marker player-helper" });
  } else {
    addSvg(group, "circle", { cx: x, cy: y, r: 13,
      class: `player-marker player-${type}` });
  }

  const label = type === "qb" ? "QB" : type === "core" ? info.p : String(info.j ?? info.p);
  addSvg(group, "text", { x, y: y + 0.5, class: `player-label ${type === "qb" ? "qb-label" : ""}` }, label);
}

function drawBreachMarker(svg, play, currentIndex, scale) {
  const threatIndex = play.summary.threatIndex;
  if (threatIndex === null || currentIndex < threatIndex) return;
  const threatFrame = play.frames[threatIndex];
  const rusher = threatFrame.r.find((item) => item[0] === play.summary.threatRusher);
  if (!rusher) return;
  const x = scale.x(rusher[1]);
  const y = scale.y(rusher[2]);
  addSvg(svg, "circle", { cx: x, cy: y, r: 22, class: "breach-marker" });
  addSvg(svg, "text", { x: x + 27, y: y - 16, class: "breach-label" },
    `FIRST THREAT · ${threatFrame.t.toFixed(1)}s`);
}

function renderTimeline(index) {
  if (!state.play) return;
  const svg = el["timeline-svg"];
  svg.replaceChildren();
  const width = 520;
  const height = 500;
  const margin = { top: 38, right: 24, bottom: 52, left: 58 };
  const play = state.play;
  const current = play.frames[index];
  const duration = Math.max(play.summary.duration, 0.1);
  const maxDistance = Math.max(...play.frames.map((frame) => frame.d));
  const yMax = Math.max(8, Math.ceil((maxDistance + 0.5) / 2) * 2);
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const x = (time) => margin.left + (time / duration) * plotWidth;
  const y = (distance) => height - margin.bottom - (distance / yMax) * plotHeight;

  addSvg(svg, "rect", { x: margin.left, y: y(THREAT_RADIUS_VALUE), width: plotWidth,
    height: y(0) - y(THREAT_RADIUS_VALUE), class: "danger-zone" });
  drawTimelineGrid(svg, duration, yMax, x, y, width, height, margin);

  addSvg(svg, "line", { x1: margin.left, y1: y(THREAT_RADIUS_VALUE), x2: width - margin.right,
    y2: y(THREAT_RADIUS_VALUE), class: "threshold-line" });
  addSvg(svg, "text", { x: width - margin.right, y: y(THREAT_RADIUS_VALUE) - 7,
    "text-anchor": "end", class: "chart-text" }, `${THREAT_RADIUS_VALUE.toFixed(1)} YD THREAT REFERENCE`);

  const curve = play.frames.map((frame) => `${x(frame.t)},${y(frame.d)}`).join(" ");
  addSvg(svg, "polyline", { points: curve, class: "distance-line" });

  if (play.summary.threatIndex !== null) {
    const threat = play.frames[play.summary.threatIndex];
    addSvg(svg, "circle", { cx: x(threat.t), cy: y(threat.d), r: 6, class: "threat-dot" });
    addSvg(svg, "text", { x: x(threat.t) + 9, y: y(threat.d) - 10, class: "breach-label" }, "FIRST THREAT");
  }

  addSvg(svg, "line", { x1: x(current.t), y1: margin.top, x2: x(current.t),
    y2: height - margin.bottom, class: "cursor-line" });
  addSvg(svg, "circle", { cx: x(current.t), cy: y(current.d), r: 7, class: "cursor-dot" });
  const nearest = person(play, current.n);
  addSvg(svg, "text", { x: margin.left, y: 19, class: "chart-title-text" },
    `${nearest.n.toUpperCase()} · ${current.d.toFixed(2)} YARDS`);
}

function drawTimelineGrid(svg, duration, yMax, x, y, width, height, margin) {
  for (let distance = 0; distance <= yMax; distance += 2) {
    const py = y(distance);
    addSvg(svg, "line", { x1: margin.left, y1: py, x2: width - margin.right, y2: py, class: "chart-grid" });
    addSvg(svg, "text", { x: margin.left - 10, y: py + 3, "text-anchor": "end", class: "chart-text" }, String(distance));
  }
  const secondStep = duration <= 3 ? 0.5 : 1;
  for (let second = 0; second <= duration + 0.001; second += secondStep) {
    const px = x(second);
    addSvg(svg, "line", { x1: px, y1: margin.top, x2: px, y2: height - margin.bottom, class: "chart-grid" });
    addSvg(svg, "text", { x: px, y: height - margin.bottom + 19, "text-anchor": "middle", class: "chart-text" }, `${second.toFixed(1)}s`);
  }
  addSvg(svg, "line", { x1: margin.left, y1: height - margin.bottom, x2: width - margin.right,
    y2: height - margin.bottom, class: "chart-axis" });
  addSvg(svg, "line", { x1: margin.left, y1: margin.top, x2: margin.left,
    y2: height - margin.bottom, class: "chart-axis" });
  addSvg(svg, "text", { x: 14, y: height / 2, transform: `rotate(-90 14 ${height / 2})`,
    "text-anchor": "middle", class: "chart-text" }, "DISTANCE TO QUARTERBACK (YARDS)");
}

window.addEventListener("DOMContentLoaded", initialize);
