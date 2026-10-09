"use strict";

const gameSelect = document.querySelector("#game-select");
const playSelect = document.querySelector("#play-select");
const generateButton = document.querySelector("#generate-button");
const replayButton = document.querySelector("#replay-button");
const results = document.querySelector("#results");
const status = document.querySelector("#status");
let catalog = null;

const currentGame = () => catalog.games.find(game => String(game.gameId) === gameSelect.value);
const currentPlay = () => currentGame()?.plays.find(play => String(play.playId) === playSelect.value);

function fillPlaySelector() {
  const game = currentGame();
  playSelect.innerHTML = "";
  for (const play of game?.plays || []) {
    const option = document.createElement("option");
    option.value = play.playId;
    option.textContent = `Play ${play.playId} · ${play.label}`;
    playSelect.append(option);
  }
  playSelect.disabled = !game?.plays.length;
  generateButton.disabled = !game?.plays.length;
}

function addSituation(label, value) {
  const item = document.createElement("div");
  item.className = "situation-item";
  const key = document.createElement("span");
  key.textContent = label;
  const val = document.createElement("strong");
  val.textContent = value || "—";
  item.append(key, val);
  document.querySelector("#situation-grid").append(item);
}

function showBreakdown() {
  const game = currentGame();
  const play = currentPlay();
  if (!game || !play) return;

  status.textContent = "Loading animation…";
  const animation = document.querySelector("#coverage-animation");
  animation.onload = () => { status.textContent = "Breakdown ready."; };
  animation.src = `${play.gif}?replay=${Date.now()}`;

  document.querySelector("#game-label").textContent = game.label;
  document.querySelector("#play-title").textContent = `Game ${game.gameId} · Play ${play.playId}`;
  document.querySelector("#play-description").textContent = play.description;

  const badge = document.querySelector("#result-badge");
  badge.textContent = play.result.headline;
  badge.className = `result-badge ${play.result.tier}`;

  const analysis = play.analysis;
  document.querySelector("#coverage-name").textContent = `${analysis.coverage} · ${analysis.coverage_type}`;
  document.querySelector("#scheme-note").textContent = analysis.scheme_note;
  document.querySelector("#void-distance").textContent = `${analysis.largest_void.dist_to_nearest_yds} yd separation`;
  document.querySelector("#void-phrase").textContent = analysis.largest_void.phrase;

  const grid = document.querySelector("#situation-grid");
  grid.innerHTML = "";
  const situation = play.situation;
  addSituation("Situation", play.result.down_distance);
  addSituation("Quarter / Clock", `Q${situation.quarter} · ${situation.gameClock}`);
  addSituation("Teams", `${situation.possessionTeam} offense vs ${situation.defensiveTeam} defense`);
  addSituation("Line to Gain", play.result.first_down_conceded ? "First down conceded" : "Stopped short");
  addSituation("Defensive Personnel", analysis.personnel_d);
  addSituation("Defenders in Box", String(analysis.defenders_in_box ?? "—"));
  addSituation("Offensive Personnel", analysis.personnel_o);
  addSituation("Formation", analysis.offense_formation);
  addSituation("Dropback", analysis.drop_back_type);
  addSituation("Play Action", analysis.play_action ? "Yes" : "No");

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

replayButton.addEventListener("click", () => {
  const animation = document.querySelector("#coverage-animation");
  const src = animation.src.split("?")[0];
  animation.src = `${src}?replay=${Date.now()}`;
});
gameSelect.addEventListener("change", fillPlaySelector);
generateButton.addEventListener("click", showBreakdown);

fetch("demo-data.json")
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    catalog = data;
    document.querySelector("#demo-notice").textContent = data.demoNotice;
    gameSelect.innerHTML = "";
    for (const game of data.games) {
      const option = document.createElement("option");
      option.value = game.gameId;
      option.textContent = `Game ${game.gameId} · ${game.label}`;
      gameSelect.append(option);
    }
    gameSelect.disabled = false;
    fillPlaySelector();
    status.textContent = "Choose a game and play, then generate the breakdown.";
  })
  .catch(error => {
    status.textContent = `Unable to load demo data: ${error.message}`;
    document.querySelector("#demo-notice").textContent = "Demo data could not be loaded.";
  });
