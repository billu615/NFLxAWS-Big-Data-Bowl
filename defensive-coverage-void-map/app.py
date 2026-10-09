"""
Coverage Void Map — Defensive Breakdown Tool (Flask web app)
================================================================
A coach-facing single-page tool for the NFL Big Data Bowl regional data set.

A defensive coach picks a game and a play; the app renders the Coverage Void
animation (a distance-to-nearest-defender heat map, red = open space, green =
tightly covered) from snap to outcome, states the result from the DEFENSE'S
point of view, and breaks down the coverage shell that was called.

All heat-map math and the frame renderer are shared with the CLI script via
`coverage_core` — this module never re-implements that logic.

Run (Windows / PowerShell):
    py -m pip install -r requirements.txt
    py app.py
    # open http://127.0.0.1:5000
"""

import math
import os

import numpy as np
import pandas as pd
from flask import Flask, abort, jsonify, render_template, request, send_file

import coverage_core as core

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Load the static tables once at startup. Tracking files are loaded per request
# (one file is small, ~0.1s) but the generated GIFs are cached on disk.
# ---------------------------------------------------------------------------
PLAYS = core.load_plays()
GAMES = pd.read_csv(os.path.join(core.DATA, "games.csv"))
GAMES_INDEX = GAMES.set_index("gameId")
ON_DISK_GAMES = set(core.available_games())

CACHE_DIR = os.path.join(core.OUT, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Simple per-game tracking cache so repeated /api/plays and /api/play calls on
# the same game do not re-read the CSV from disk every time.
_TRACKING_CACHE = {}


def get_tracking(game_id):
    if game_id not in _TRACKING_CACHE:
        _TRACKING_CACHE[game_id] = core.load_tracking(game_id)
    return _TRACKING_CACHE[game_id]


def _clean(value, default=""):
    """Return a JSON-safe scalar: turn NaN/None into `default`."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    return value


def _to_int(value):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Defensive-perspective result mapping (exact wording per the spec).
# ---------------------------------------------------------------------------
_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def down_distance_str(row):
    down = _to_int(row.get("down"))
    ytg = _to_int(row.get("yardsToGo"))
    if down is None or ytg is None:
        return ""
    return f"{_ORDINAL.get(down, str(down) + 'th')} & {ytg}"


def defensive_result(row):
    """
    Translate the offensive play outcome into the defense's point of view.

    Returns a dict with:
      headline            : the exact result string a coach reads
      tier                : "win" | "ok" | "pressure" | "beaten" (drives UI color)
      down_distance       : e.g. "3rd & 7"
      first_down_conceded : True if the yards gained reached the line to gain
    """
    pr = _clean(row.get("passResult"))
    play_result = _to_int(row.get("playResult"))
    ytg = _to_int(row.get("yardsToGo"))
    pr_val = play_result if play_result is not None else 0

    if pr == "IN":
        headline, tier = "DEFENSE WIN — Interception", "win"
    elif pr == "S":
        headline, tier = "DEFENSE WIN — Sack", "win"
    elif pr == "I":
        headline, tier = "DEFENSE WIN — Pass Broken Up / Incomplete", "win"
    elif pr == "C":
        if pr_val <= 0:
            headline, tier = "DEFENSE WIN — Completion for no gain/loss", "win"
        elif pr_val < 10:
            headline, tier = f"DEFENSE OK — Short completion ({pr_val} yds)", "ok"
        else:
            headline, tier = f"DEFENSE BEATEN — Completion for {pr_val} yds", "beaten"
    elif pr == "R":
        headline, tier = f"DEFENSE PRESSURE — QB Scramble ({pr_val} yds)", "pressure"
    else:
        headline, tier = f"Play result: {pr or 'unknown'}", "ok"

    first_down_conceded = False
    if pr in ("C", "R") and play_result is not None and ytg is not None:
        first_down_conceded = play_result >= ytg

    return {
        "headline": headline,
        "tier": tier,
        "down_distance": down_distance_str(row),
        "first_down_conceded": first_down_conceded,
    }


# ---------------------------------------------------------------------------
# Coverage strategy analysis.
# ---------------------------------------------------------------------------
# Scheme-weakness notes keyed by coverage name. Values are 2-3 sentence coaching
# notes describing where each shell is structurally vulnerable.
_SCHEME_NOTES = {
    "Cover-3": (
        "Cover-3 drops three deep and four underneath, so the seams and the "
        "curl-flat areas are the pressure points. The two deep 'honey holes' sit "
        "roughly 12-18 yards downfield just outside the hashes, between the deep "
        "third defenders and the underneath hook players."
    ),
    "Cover-2": (
        "Cover-2 keeps two deep safeties splitting the field, which opens the "
        "deep middle hole between them and the deep sideline behind the cornerback. "
        "Attack the void over the top of the corner or up the seam before the "
        "safety can close."
    ),
    "Cover-1": (
        "Cover-1 is man coverage with a single high safety, so it is beaten by "
        "man-beaters: picks and rub routes, crossers, and scramble lanes once the "
        "pocket breaks down. Isolate the matchup you like and create natural traffic."
    ),
    "Quarters": (
        "Quarters (Cover-4) splits the deep field four ways and is pattern-matched, "
        "so it is stressed by flood concepts and four-verticals that force the "
        "safeties to commit. Overload one side or run verticals to bend the "
        "pattern-match rules."
    ),
}
_DEFAULT_NOTE = (
    "Read the shell's deepest defenders and attack the space they vacate: find "
    "the void between the underneath and deep zones, or the one-on-one matchup "
    "the coverage leaves exposed."
)


def _scheme_note(coverage):
    if not coverage:
        return _DEFAULT_NOTE
    # Match on the leading shell name (e.g. "Cover-3 Seam" -> "Cover-3").
    for key, note in _SCHEME_NOTES.items():
        if str(coverage).startswith(key):
            return note
    return _DEFAULT_NOTE


def largest_void(game_id, play_id, row):
    """
    Compute the single most-open spot at the pass_forward frame using the shared
    distance_field. Restrict the search to grid points downfield of the ball
    (toward the offense's direction of travel) and take the point farthest from
    any defender.

    Returns a dict with downfield_yds, lateral_yds, side, dist_to_nearest_yds,
    and a coach-facing phrase, or None if the frame/positions are unavailable.
    """
    trk = get_tracking(game_id)
    trk_play = trk[(trk.gameId == game_id) & (trk.playId == play_id)].copy()
    if trk_play.empty:
        return None

    fr = core.event_frame(trk_play, ["pass_forward", "autoevent_passforward"])
    if fr is None:
        fr = core.event_frame(trk_play, ["ball_snap", "autoevent_ballsnap"])
    if fr is None:
        fr = int(trk_play.frameId.min())

    def_team = row["defensiveTeam"]
    defs, _off, ball = core.frame_positions(trk_play, fr, def_team)
    if len(defs) == 0 or len(ball) == 0:
        return None

    bx, by = float(ball[0][0]), float(ball[0][1])
    direction = str(trk_play[trk_play.frameId == fr].playDirection.iloc[0])

    xmin = max(0, trk_play.x.min() - 2)
    xmax = min(core.FIELD_X, trk_play.x.max() + 2)
    XX, YY, D = core.distance_field(defs, xmin, xmax)

    # Downfield = toward the offense's direction of travel from the ball.
    if direction == "left":
        downfield_mask = XX <= bx
    else:
        downfield_mask = XX >= bx

    valid = downfield_mask & np.isfinite(D)
    if not valid.any():
        valid = np.isfinite(D)
    if not valid.any():
        return None

    masked = np.where(valid, D, -np.inf)
    idx = np.unravel_index(np.argmax(masked), masked.shape)
    px, py = float(XX[idx]), float(YY[idx])
    dist = float(D[idx])

    # Downfield distance from the ball (always positive toward offense).
    downfield_yds = abs(px - bx)
    # Lateral: positive = toward one sideline; translate to left/right from the
    # defense's/offense's perspective consistently using the ball as origin.
    lateral_raw = py - by
    if direction == "left":
        lateral_raw = -lateral_raw
    side = "left" if lateral_raw < 0 else "right"
    lateral_yds = abs(lateral_raw)

    phrase = (
        f"Largest void at ~{downfield_yds:.0f} yds downfield, "
        f"{lateral_yds:.0f} yds to the {side}, "
        f"~{dist:.0f} yds from nearest defender."
    )
    return {
        "downfield_yds": round(downfield_yds, 1),
        "lateral_yds": round(lateral_yds, 1),
        "side": side,
        "dist_to_nearest_yds": round(dist, 1),
        "phrase": phrase,
    }


def coverage_analysis(row, game_id, play_id):
    coverage = _clean(row.get("pff_passCoverage"))
    cov_type = _clean(row.get("pff_passCoverageType"))
    return {
        "coverage": coverage or "Unknown",
        "coverage_type": cov_type or "Unknown",
        "defenders_in_box": _to_int(row.get("defendersInBox")),
        "personnel_d": _clean(row.get("personnelD")),
        "offense_formation": _clean(row.get("offenseFormation")),
        "personnel_o": _clean(row.get("personnelO")),
        "drop_back_type": _clean(row.get("dropBackType")),
        "play_action": bool(row.get("pff_playAction")) if not (
            isinstance(row.get("pff_playAction"), float) and math.isnan(row.get("pff_playAction"))
        ) else False,
        "scheme_note": _scheme_note(coverage),
        "largest_void": largest_void(game_id, play_id, row),
    }


# ---------------------------------------------------------------------------
# Play usability: must have tracking rows and a snap/pass_forward event.
# ---------------------------------------------------------------------------
_USABLE_EVENTS = {"pass_forward", "autoevent_passforward", "ball_snap", "autoevent_ballsnap"}


def _play_row(game_id, play_id):
    r = PLAYS[(PLAYS.gameId == game_id) & (PLAYS.playId == play_id)]
    if r.empty:
        return None
    return r.iloc[0]


def game_label(game_id):
    try:
        g = GAMES_INDEX.loc[game_id]
    except KeyError:
        return f"Game {game_id}"
    week = _to_int(g.get("week"))
    return (f"Week {week}: {g.get('visitorTeamAbbr')} @ {g.get('homeTeamAbbr')} "
            f"({g.get('gameDate')})")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/games")
def api_games():
    out = []
    for gid in sorted(ON_DISK_GAMES):
        out.append({"gameId": gid, "label": game_label(gid)})
    return jsonify(out)


@app.route("/api/plays")
def api_plays():
    game_id = _to_int(request.args.get("gameId"))
    if game_id is None or game_id not in ON_DISK_GAMES:
        abort(404, description="Unknown gameId or no tracking file on disk.")

    trk = get_tracking(game_id)
    # Plays with any usable event in tracking.
    ev = trk[trk.event.isin(_USABLE_EVENTS)]
    usable_play_ids = set(ev.playId.unique().tolist())

    gplays = PLAYS[PLAYS.gameId == game_id]
    out = []
    for _, row in gplays.iterrows():
        pid = _to_int(row.get("playId"))
        if pid is None or pid not in usable_play_ids:
            continue
        dd = down_distance_str(row)
        desc = str(_clean(row.get("playDescription")))
        desc_short = desc[:60].rstrip()
        label = f"{dd} — {desc_short}" if dd else desc_short
        out.append({
            "playId": pid,
            "label": label,
            "quarter": _to_int(row.get("quarter")),
            "gameClock": _clean(row.get("gameClock")),
            "pff_passCoverage": _clean(row.get("pff_passCoverage")),
        })
    out.sort(key=lambda p: p["playId"])
    if not out:
        abort(404, description="No usable plays found for this game.")
    return jsonify(out)


@app.route("/api/play")
def api_play():
    game_id = _to_int(request.args.get("gameId"))
    play_id = _to_int(request.args.get("playId"))
    if game_id is None or play_id is None:
        abort(400, description="gameId and playId are required integers.")
    if game_id not in ON_DISK_GAMES:
        abort(404, description="Unknown gameId or no tracking file on disk.")

    row = _play_row(game_id, play_id)
    if row is None:
        abort(404, description="Unknown playId for this game.")

    result = defensive_result(row)
    analysis = coverage_analysis(row, game_id, play_id)
    situation = {
        "quarter": _to_int(row.get("quarter")),
        "gameClock": _clean(row.get("gameClock")),
        "down_distance": result["down_distance"],
        "offenseFormation": _clean(row.get("offenseFormation")),
        "personnelO": _clean(row.get("personnelO")),
        "personnelD": _clean(row.get("personnelD")),
        "defendersInBox": _to_int(row.get("defendersInBox")),
        "possessionTeam": _clean(row.get("possessionTeam")),
        "defensiveTeam": _clean(row.get("defensiveTeam")),
    }

    # Render (and cache) the GIF on disk.
    gif_path = os.path.join(CACHE_DIR, f"landscape_void_{game_id}_{play_id}.gif")
    if not (os.path.exists(gif_path) and os.path.getsize(gif_path) > 0):
        title_lines = [
            f"Coverage Void Map  |  Game {game_id}  Play {play_id}",
            result["headline"],
        ]
        try:
            core.render_void_animation(PLAYS, game_id, play_id, gif_path, title_lines)
        except ValueError as e:
            abort(404, description=str(e))

    return jsonify({
        "gameId": game_id,
        "playId": play_id,
        "gif_url": f"/gif/{game_id}/{play_id}",
        "result": result,
        "analysis": analysis,
        "situation": situation,
    })


@app.route("/gif/<int:game_id>/<int:play_id>")
def gif(game_id, play_id):
    gif_path = os.path.join(CACHE_DIR, f"landscape_void_{game_id}_{play_id}.gif")
    if not (os.path.exists(gif_path) and os.path.getsize(gif_path) > 0):
        abort(404, description="GIF not generated yet.")
    return send_file(gif_path, mimetype="image/gif")


@app.errorhandler(400)
@app.errorhandler(404)
def _json_error(err):
    return jsonify({"error": getattr(err, "description", str(err))}), err.code


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
