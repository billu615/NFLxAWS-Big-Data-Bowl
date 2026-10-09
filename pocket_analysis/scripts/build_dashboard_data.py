"""Build compact, static dashboard data from NFL tracking CSV files.

The generated JSON is split by game so the GitHub Pages site only downloads
one game at a time. Raw tracking files remain outside the published site.

Run from the project root:
    uv run python pocket_analysis/scripts/build_dashboard_data.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "nfl-big-data-bowl-regional-event-data" / "data"
OUTPUT_DIR = SITE_DIR / "data"
GAME_OUTPUT_DIR = OUTPUT_DIR / "games"

CORE_LINE_POSITIONS = {"LT", "LG", "C", "RG", "RT"}
THREAT_RADIUS_YARDS = 2.5
MAX_POCKET_SECONDS = 5.0
END_EVENTS = {"pass_forward", "autoevent_passforward", "qb_sack", "run"}
TRACKING_COLUMNS = [
    "gameId",
    "playId",
    "nflId",
    "frameId",
    "jerseyNumber",
    "team",
    "playDirection",
    "x",
    "y",
    "s",
    "event",
]
RESULT_NAMES = {
    "C": "Complete",
    "I": "Incomplete",
    "S": "Sack",
    "R": "Scramble",
    "IN": "Interception",
}


def clean(value: Any, default: Any = None) -> Any:
    """Convert pandas/numpy values to JSON-safe Python values."""
    if pd.isna(value):
        return default
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def rounded(value: float | None, digits: int = 2) -> float | None:
    """Round a numeric value while preserving missing values."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def first_frame(play_tracking: pd.DataFrame, events: set[str]) -> int | None:
    """Return the first frame carrying one of the requested event labels."""
    values = play_tracking.loc[play_tracking["event"].isin(events), "frameId"]
    return None if values.empty else int(values.min())


def pff_outcome(row: pd.Series) -> str:
    """Return the most severe PFF pressure credit on a rusher's play."""
    if clean(row.get("pff_sack"), 0) == 1:
        return "Sack"
    if clean(row.get("pff_hit"), 0) == 1:
        return "Hit"
    if clean(row.get("pff_hurry"), 0) == 1:
        return "Hurry"
    return "No pressure credit"


def overall_pressure_outcome(rushers: pd.DataFrame) -> str:
    """Return the most severe pressure result credited on the play."""
    outcomes = {pff_outcome(row) for _, row in rushers.iterrows()}
    for outcome in ("Sack", "Hit", "Hurry"):
        if outcome in outcomes:
            return outcome
    return "No pressure credit"


def play_label(play: pd.Series) -> str:
    """Create a concise selector label in familiar football language."""
    down = clean(play.get("down"), "–")
    distance = clean(play.get("yardsToGo"), "–")
    quarter = clean(play.get("quarter"), "–")
    clock = clean(play.get("gameClock"), "--:--")
    result = RESULT_NAMES.get(clean(play.get("passResult")), "Unknown")
    return f"Q{quarter} {clock} · {down} & {distance} · {result}"


def participant_catalog(
    window: pd.DataFrame,
    roles: pd.DataFrame,
    player_names: dict[int, str],
    relevant_ids: set[int],
) -> dict[str, dict[str, Any]]:
    """Build one compact identity record per displayed participant."""
    role_lookup = roles.drop_duplicates("nflId").set_index("nflId")
    first_tracking = window.dropna(subset=["nflId"]).drop_duplicates("nflId").set_index("nflId")
    people: dict[str, dict[str, Any]] = {}

    for nfl_id in sorted(relevant_ids):
        role = role_lookup.loc[nfl_id]
        tracked = first_tracking.loc[nfl_id] if nfl_id in first_tracking.index else None
        jersey = clean(tracked.get("jerseyNumber")) if tracked is not None else None
        people[str(nfl_id)] = {
            "n": player_names.get(nfl_id, f"Player {nfl_id}"),
            "j": int(jersey) if jersey is not None else None,
            "p": clean(role.get("pff_positionLinedUp"), "—"),
            "r": clean(role.get("pff_role"), "—"),
        }
    return people


def build_matchups(
    roles: pd.DataFrame,
    frames: list[dict[str, Any]],
    rusher_ids: set[int],
) -> list[dict[str, Any]]:
    """Combine PFF initial assignments with tracking proximity by rusher."""
    blockers = roles.loc[
        roles["pff_role"].eq("Pass Block")
        & roles["pff_nflIdBlockedPlayer"].notna()
    ]
    rusher_rows = roles.loc[roles["pff_role"].eq("Pass Rush")].set_index("nflId")
    matchups: list[dict[str, Any]] = []

    for rusher_id in sorted(rusher_ids):
        assigned = blockers.loc[blockers["pff_nflIdBlockedPlayer"].eq(rusher_id)]
        distances = [
            (frame["t"], rusher[3])
            for frame in frames
            for rusher in frame["r"]
            if rusher[0] == rusher_id
        ]
        threat_times = [time for time, distance in distances if distance <= THREAT_RADIUS_YARDS]
        outcome = pff_outcome(rusher_rows.loc[rusher_id])
        matchups.append(
            {
                "r": rusher_id,
                "b": [int(value) for value in assigned["nflId"].tolist()],
                "bt": [clean(value, "—") for value in assigned["pff_blockType"].tolist()],
                "out": outcome,
                "min": rounded(min((distance for _, distance in distances), default=None)),
                "tt": rounded(min(threat_times), 1) if threat_times else None,
            }
        )
    return matchups


def extract_frame(
    frame: pd.DataFrame,
    qb_id: int,
    core_ids: set[int],
    helper_ids: set[int],
    rusher_ids: set[int],
    snap_frame: int,
) -> dict[str, Any] | None:
    """Extract compact participant positions and pocket measurements."""
    player_rows = {
        int(row.nflId): row
        for row in frame.itertuples()
        if not pd.isna(row.nflId)
    }
    if qb_id not in player_rows:
        return None

    qb_row = player_rows[qb_id]
    qb_x, qb_y = float(qb_row.xStandard), float(qb_row.y)
    core = [player_rows[nfl_id] for nfl_id in core_ids if nfl_id in player_rows]
    rushers = [player_rows[nfl_id] for nfl_id in rusher_ids if nfl_id in player_rows]
    if len(core) < 2 or not rushers:
        return None

    offensive_line = [
        [int(row.nflId), rounded(row.xStandard), rounded(row.y)] for row in core
    ]
    helpers = [
        [int(player_rows[nfl_id].nflId), rounded(player_rows[nfl_id].xStandard), rounded(player_rows[nfl_id].y)]
        for nfl_id in helper_ids
        if nfl_id in player_rows
    ]
    rush = [
        [
            int(row.nflId),
            rounded(row.xStandard),
            rounded(row.y),
            rounded(np.hypot(row.xStandard - qb_x, row.y - qb_y)),
        ]
        for row in rushers
    ]
    nearest = min(rush, key=lambda item: item[3])

    blocker_y = [float(row.y) for row in core]
    wall_x = float(np.mean([row.xStandard for row in core]))
    width = max(blocker_y) - min(blocker_y)
    cushion = max(wall_x - qb_x, 0.0)
    ball_rows = frame.loc[frame["team"].eq("football")]
    ball = None
    if not ball_rows.empty:
        ball = [rounded(ball_rows.iloc[0]["xStandard"]), rounded(ball_rows.iloc[0]["y"])]

    return {
        "t": rounded((int(frame["frameId"].iloc[0]) - snap_frame) / 10, 1),
        "q": [qb_id, rounded(qb_x), rounded(qb_y)],
        "o": offensive_line,
        "h": helpers,
        "r": rush,
        "b": ball,
        "w": rounded(width),
        "c": rounded(cushion),
        "a": rounded(width * cushion / 2),
        "n": int(nearest[0]),
        "d": rounded(nearest[3]),
    }


def summarize_play(
    frames: list[dict[str, Any]],
    roles: pd.DataFrame,
    rusher_ids: set[int],
) -> dict[str, Any]:
    """Build defensive-coordinator summary fields for one play."""
    threat_index = next(
        (index for index, frame in enumerate(frames) if frame["d"] <= THREAT_RADIUS_YARDS),
        None,
    )
    threat_frame = frames[threat_index] if threat_index is not None else None
    threat_rusher = threat_frame["n"] if threat_frame else None
    lane = "No nearby threat"

    if threat_frame is not None:
        threat_position = next(item for item in threat_frame["r"] if item[0] == threat_rusher)
        lateral_difference = threat_position[2] - threat_frame["q"][2]
        if lateral_difference > 1.25:
            lane = "Offense left / defense right"
        elif lateral_difference < -1.25:
            lane = "Offense right / defense left"
        else:
            lane = "Interior"

    rusher_rows = roles.loc[roles["pff_role"].eq("Pass Rush")]
    threat_outcome = "No pressure credit"
    if threat_rusher is not None:
        threat_row = rusher_rows.loc[rusher_rows["nflId"].eq(threat_rusher)]
        if not threat_row.empty:
            threat_outcome = pff_outcome(threat_row.iloc[0])

    initial_qb_y = frames[0]["q"][2]
    max_lateral_move = max(abs(frame["q"][2] - initial_qb_y) for frame in frames)
    return {
        "duration": frames[-1]["t"],
        "threatTime": threat_frame["t"] if threat_frame else None,
        "threatIndex": threat_index,
        "threatRusher": threat_rusher,
        "threatLane": lane,
        "threatOutcome": threat_outcome,
        "pressureOutcome": overall_pressure_outcome(rusher_rows),
        "pffPressure": overall_pressure_outcome(rusher_rows) != "No pressure credit",
        "minDistance": min(frame["d"] for frame in frames),
        "maxLateral": rounded(max_lateral_move),
    }


def build_play(
    play_tracking: pd.DataFrame,
    play: pd.Series,
    roles: pd.DataFrame,
    player_names: dict[int, str],
) -> dict[str, Any] | None:
    """Create one static-site play record from tracking and PFF data."""
    snap_frame = first_frame(play_tracking, {"ball_snap"})
    if snap_frame is None:
        snap_frame = first_frame(play_tracking, {"autoevent_ballsnap"})
    if snap_frame is None:
        return None

    end_candidates = play_tracking.loc[
        play_tracking["event"].isin(END_EVENTS)
        & play_tracking["frameId"].ge(snap_frame),
        "frameId",
    ]
    end_frame = int(end_candidates.min()) if not end_candidates.empty else int(play_tracking["frameId"].max())
    end_frame = min(end_frame, snap_frame + int(MAX_POCKET_SECONDS * 10))

    window = play_tracking.loc[play_tracking["frameId"].between(snap_frame, end_frame)].copy()
    direction = clean(window["playDirection"].mode().iloc[0], "right")
    window["xStandard"] = np.where(direction == "right", window["x"], 120 - window["x"])

    passer_rows = roles.loc[roles["pff_role"].eq("Pass")]
    rusher_rows = roles.loc[roles["pff_role"].eq("Pass Rush")]
    blocker_rows = roles.loc[roles["pff_role"].eq("Pass Block")]
    if passer_rows.empty or rusher_rows.empty:
        return None

    qb_id = int(passer_rows.iloc[0]["nflId"])
    rusher_ids = set(rusher_rows["nflId"].astype(int))
    core_ids = set(
        blocker_rows.loc[
            blocker_rows["pff_positionLinedUp"].isin(CORE_LINE_POSITIONS), "nflId"
        ].astype(int)
    )
    helper_ids = set(blocker_rows["nflId"].astype(int)) - core_ids
    relevant_ids = {qb_id} | rusher_ids | core_ids | helper_ids

    frames = [
        extracted
        for _, frame in window.groupby("frameId", sort=True)
        if (extracted := extract_frame(frame, qb_id, core_ids, helper_ids, rusher_ids, snap_frame))
    ]
    if not frames:
        return None

    summary = summarize_play(frames, roles, rusher_ids)
    matchups = build_matchups(roles, frames, rusher_ids)
    people = participant_catalog(window, roles, player_names, relevant_ids)
    raw_los = float(play["absoluteYardlineNumber"])
    standard_los = raw_los if direction == "right" else 120 - raw_los

    return {
        "id": int(play["playId"]),
        "label": play_label(play),
        "meta": {
            "q": clean(play.get("quarter")),
            "clock": clean(play.get("gameClock"), "--:--"),
            "down": clean(play.get("down")),
            "toGo": clean(play.get("yardsToGo")),
            "off": clean(play.get("possessionTeam"), "—"),
            "def": clean(play.get("defensiveTeam"), "—"),
            "formation": clean(play.get("offenseFormation"), "Unknown"),
            "coverage": clean(play.get("pff_passCoverage"), "Unknown"),
            "coverageType": clean(play.get("pff_passCoverageType"), "Unknown"),
            "dropback": clean(play.get("dropBackType"), "Unknown"),
            "playAction": bool(clean(play.get("pff_playAction"), 0)),
            "result": RESULT_NAMES.get(clean(play.get("passResult")), "Unknown"),
            "yards": clean(play.get("playResult"), 0),
            "description": clean(play.get("playDescription"), "Description unavailable"),
        },
        "los": rounded(standard_los),
        "people": people,
        "frames": frames,
        "summary": summary,
        "matchups": matchups,
    }


def build_game(
    game: pd.Series,
    plays: pd.DataFrame,
    pff: pd.DataFrame,
    player_names: dict[int, str],
) -> dict[str, Any]:
    """Build all dashboard-ready plays for one game."""
    game_id = int(game["gameId"])
    tracking_path = DATA_DIR / "tracking" / f"tracking_{game_id}.csv"
    tracking = pd.read_csv(tracking_path, usecols=TRACKING_COLUMNS)
    game_plays = plays.loc[plays["gameId"].eq(game_id)].set_index("playId", drop=False)
    game_roles = pff.loc[pff["gameId"].eq(game_id)]
    roles_by_play = {int(play_id): group for play_id, group in game_roles.groupby("playId")}

    output_plays: list[dict[str, Any]] = []
    for play_id, play_tracking in tracking.groupby("playId", sort=True):
        play_id = int(play_id)
        if play_id not in game_plays.index or play_id not in roles_by_play:
            continue
        record = build_play(
            play_tracking,
            game_plays.loc[play_id],
            roles_by_play[play_id],
            player_names,
        )
        if record is not None:
            output_plays.append(record)

    game_meta = {
        "id": game_id,
        "season": int(game["season"]),
        "week": int(game["week"]),
        "date": clean(game["gameDate"]),
        "home": clean(game["homeTeamAbbr"]),
        "away": clean(game["visitorTeamAbbr"]),
        "label": f"Week {int(game['week'])} · {game['visitorTeamAbbr']} @ {game['homeTeamAbbr']} · {game['gameDate']}",
    }
    return {"game": game_meta, "plays": output_plays}


def write_json(path: Path, payload: Any) -> None:
    """Write compact UTF-8 JSON suitable for static hosting."""
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def main() -> None:
    """Generate the game files and top-level manifest."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Data directory not found: {DATA_DIR}")

    games = pd.read_csv(DATA_DIR / "games.csv").sort_values(["week", "gameId"])
    plays = pd.read_csv(DATA_DIR / "plays.csv")
    players = pd.read_csv(DATA_DIR / "players.csv")
    pff = pd.read_csv(DATA_DIR / "pffScoutingData.csv")
    player_names = players.set_index("nflId")["displayName"].to_dict()

    GAME_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_games: list[dict[str, Any]] = []
    total_plays = 0

    for number, (_, game) in enumerate(games.iterrows(), start=1):
        payload = build_game(game, plays, pff, player_names)
        game_id = payload["game"]["id"]
        write_json(GAME_OUTPUT_DIR / f"{game_id}.json", payload)
        total_plays += len(payload["plays"])
        manifest_games.append(
            {
                **payload["game"],
                "plays": len(payload["plays"]),
                "file": f"data/games/{game_id}.json",
            }
        )
        if number % 20 == 0 or number == len(games):
            print(f"Processed {number:>3}/{len(games)} games")

    manifest = {
        "schemaVersion": 1,
        "threatRadiusYards": THREAT_RADIUS_YARDS,
        "trackingHz": 10,
        "games": manifest_games,
        "totalPlays": total_plays,
    }
    write_json(OUTPUT_DIR / "manifest.json", manifest)

    size_mb = sum(path.stat().st_size for path in OUTPUT_DIR.rglob("*.json")) / 1024**2
    print(f"Wrote {len(manifest_games)} games and {total_plays:,} plays ({size_mb:.1f} MB).")


if __name__ == "__main__":
    main()
