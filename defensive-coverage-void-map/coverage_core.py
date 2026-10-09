"""
Coverage Void Map — shared core
================================================================
Shared, side-effect-free helpers for the Coverage Void Map tool.

The "Coverage Void" idea: for every grid point on the field, compute the
distance to the nearest defender. A larger distance means that patch of field
is farther from any defender, more sparsely covered, and therefore more open.
Mapped to color, this becomes a heat map (red = open space, green = tightly
covered) that lets a coach see where a coverage shell leaves a void.

This module is imported by both the command-line script `coverage_void_map.py`
and the Flask web app `app.py`, so the heat-map math lives in exactly one
place. The per-frame animation renderer `render_void_animation()` is the
single source of truth for drawing frames; the CLI and web app both call it,
differing only in the output path and on-frame title.
"""

import glob
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TRACK = os.path.join(DATA, "tracking")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

# NFL field: 120 yards (including both end zones) by 53.3 yards.
# Tracking coordinates use x in [0, 120] and y in [0, 53.3].
FIELD_X, FIELD_Y = 120.0, 53.3
GRID = 1.0  # Grid resolution in yards.

# Every animation frame uses the same landscape canvas and axes placement.
FRAME_WIDTH, FRAME_HEIGHT, FRAME_DPI = 1280, 640, 100
MIN_VIEW_SPAN = 60.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_plays():
    return pd.read_csv(os.path.join(DATA, "plays.csv"))


def tracking_path(game_id):
    return os.path.join(TRACK, f"tracking_{game_id}.csv")


def load_tracking(game_id):
    return pd.read_csv(tracking_path(game_id))


def available_games():
    """Return game IDs that have a tracking file on disk."""
    files = glob.glob(os.path.join(TRACK, "tracking_*.csv"))
    return sorted(
        int(os.path.basename(path).split("_")[1].split(".")[0])
        for path in files
    )


# ---------------------------------------------------------------------------
# Play orientation and stable display bounds
# ---------------------------------------------------------------------------
def normalize_play_direction(trk_play):
    """
    Return a copy rotated so the offense always advances left to right.

    A left-moving play is rotated 180 degrees rather than reflecting only its
    x-coordinate. Rotating both x and y preserves the offense-relative left
    and right sides of the formation.
    """
    normalized = trk_play.copy()
    directions = normalized["playDirection"].dropna()
    if not directions.empty and str(directions.iloc[0]).lower() == "left":
        normalized["x"] = FIELD_X - normalized["x"]
        normalized["y"] = FIELD_Y - normalized["y"]
    normalized["playDirection"] = "right"
    return normalized


def play_view_bounds(trk_play, margin=3.0, min_span=MIN_VIEW_SPAN):
    """
    Return one stable x-range for every frame of a play.

    The range includes every tracked position plus a small margin and expands
    short plays to a minimum 60-yard window. That keeps the field recognizably
    horizontal while retaining a useful play-level zoom.
    """
    x_values = pd.to_numeric(trk_play["x"], errors="coerce").dropna()
    if x_values.empty:
        return 0.0, FIELD_X

    xmin = max(0.0, float(x_values.min()) - margin)
    xmax = min(FIELD_X, float(x_values.max()) + margin)
    target_span = min(float(min_span), FIELD_X)

    if xmax - xmin < target_span:
        midpoint = (xmin + xmax) / 2.0
        xmin = midpoint - target_span / 2.0
        xmax = midpoint + target_span / 2.0
        if xmin < 0.0:
            xmax -= xmin
            xmin = 0.0
        if xmax > FIELD_X:
            xmin -= xmax - FIELD_X
            xmax = FIELD_X

    return max(0.0, xmin), min(FIELD_X, xmax)


# ---------------------------------------------------------------------------
# Distance field: for the given defender coordinates, distance from every grid
# point to the nearest defender.
# ---------------------------------------------------------------------------
def distance_field(def_xy, xmin, xmax, grid=GRID):
    """
    Return (XX, YY, D), where D[i, j] is the distance in yards from a grid
    point to the nearest defender.
    """
    xs = np.arange(xmin, xmax + grid, grid)
    ys = np.arange(0, FIELD_Y + grid, grid)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.column_stack([XX.ravel(), YY.ravel()])
    if len(def_xy) == 0:
        D = np.full(XX.shape, np.nan)
        return XX, YY, D
    tree = cKDTree(def_xy)
    distances, _ = tree.query(pts, k=1)
    return XX, YY, distances.reshape(XX.shape)


# ---------------------------------------------------------------------------
# Extract defender, offense, and ball coordinates for one play frame.
# ---------------------------------------------------------------------------
def frame_positions(trk_play, frame_id, def_team):
    frame = trk_play[trk_play.frameId == frame_id]
    defenders = frame[frame.team == def_team][["x", "y"]].values
    offense = frame[
        (frame.team != def_team) & (frame.team != "football")
    ][["x", "y"]].values
    ball = frame[frame.team == "football"][["x", "y"]].values
    return defenders, offense, ball


def play_window(trk_play):
    """Return the frame range from the snap through arrival or outcome."""
    events = trk_play[["frameId", "event"]].drop_duplicates()

    def first_frame(names):
        hit = events[events.event.isin(names)]
        return int(hit.frameId.min()) if len(hit) else None

    start = first_frame(["ball_snap", "autoevent_ballsnap"])
    if start is None:
        start = int(trk_play.frameId.min())
    end = first_frame([
        "pass_arrived",
        "pass_outcome_caught",
        "pass_outcome_incomplete",
        "pass_outcome_interception",
        "qb_sack",
        "tackle",
    ])
    if end is None:
        end = int(trk_play.frameId.max())
    return start, end


def event_frame(trk_play, names):
    events = trk_play[trk_play.event.isin(names)]
    return int(events.frameId.min()) if len(events) else None


# ---------------------------------------------------------------------------
# Shared landscape field layout
# ---------------------------------------------------------------------------
def create_landscape_field_figure():
    """Create a fixed 1280x640 canvas whose field uses nearly all its width."""
    fig = plt.figure(
        figsize=(FRAME_WIDTH / FRAME_DPI, FRAME_HEIGHT / FRAME_DPI),
        dpi=FRAME_DPI,
        facecolor="#f5f6f7",
    )
    # Explicit axes avoid tight/equal-aspect layout shrinking a short play into
    # a narrow vertical strip. The remaining right edge holds the color bar.
    ax = fig.add_axes([0.018, 0.06, 0.91, 0.77])
    colorbar_ax = fig.add_axes([0.942, 0.06, 0.014, 0.77])
    return fig, ax, colorbar_ax


def draw_field(ax, xmin, xmax):
    """Draw a horizontally stretched play-level field backdrop."""
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(0, FIELD_Y)
    ax.set_aspect("auto")
    ax.set_facecolor("#0b3d0b")
    ax.margins(0)

    # One vertical line every five yards.
    for yard_line in np.arange(np.ceil(xmin / 5) * 5, xmax, 5):
        ax.axvline(yard_line, color="white", lw=0.6, alpha=0.35)

    for spine in ax.spines.values():
        spine.set_color("white")
        spine.set_linewidth(1.0)
    ax.set_xticks([])
    ax.set_yticks([])


# ---------------------------------------------------------------------------
# Shared animation renderer. Both the CLI and Flask app call this function.
# ---------------------------------------------------------------------------
def render_void_animation(plays, game_id, play_id, out_path, title_lines):
    """
    Render a Coverage Void animation from snap through outcome and save it as
    a looping GIF at `out_path`.

    `title_lines` contains the coach-facing text drawn on every frame.
    """
    row = plays[(plays.gameId == game_id) & (plays.playId == play_id)]
    if row.empty:
        raise ValueError(f"play {game_id}/{play_id} not found in plays.csv")
    row = row.iloc[0]
    def_team = row["defensiveTeam"]

    tracking = load_tracking(game_id)
    trk_play = tracking[
        (tracking.gameId == game_id) & (tracking.playId == play_id)
    ].copy()
    if trk_play.empty:
        raise ValueError(f"play {game_id}/{play_id} has no tracking data")

    trk_play = normalize_play_direction(trk_play)
    start, end = play_window(trk_play)
    pass_frame = event_frame(
        trk_play, ["pass_forward", "autoevent_passforward"]
    )
    xmin, xmax = play_view_bounds(trk_play)

    # Sample the same fixed field window to keep the color scale stable across
    # every frame in the animation.
    sample_step = max(1, (end - start) // 8 or 1)
    sample_frames = range(start, end + 1, sample_step)
    dmax_samples = []
    for frame_id in sample_frames:
        defenders, _, _ = frame_positions(trk_play, frame_id, def_team)
        _, _, distances = distance_field(defenders, xmin, xmax)
        if np.isfinite(distances).any():
            dmax_samples.append(np.nanpercentile(distances, 95))
    vmax = float(np.nanmax(dmax_samples)) if dmax_samples else 15.0
    vmax = max(vmax, 8.0)
    levels = np.linspace(0.0, vmax, 21)

    base_title = "\n".join(
        str(title) for title in title_lines if str(title).strip()
    )

    import imageio.v2 as imageio

    frame_paths = []
    tmpdir = os.path.join(OUT, f"_frames_{game_id}_{play_id}")
    os.makedirs(tmpdir, exist_ok=True)

    for index, frame_id in enumerate(range(start, end + 1)):
        defenders, offense, ball = frame_positions(
            trk_play, frame_id, def_team
        )
        XX, YY, distances = distance_field(defenders, xmin, xmax)

        fig, ax, colorbar_ax = create_landscape_field_figure()
        heat_map = ax.contourf(
            XX,
            YY,
            distances,
            levels=levels,
            cmap="RdYlGn_r",
            vmin=0,
            vmax=vmax,
            alpha=0.88,
            extend="max",
        )
        draw_field(ax, xmin, xmax)

        if len(defenders):
            ax.scatter(
                defenders[:, 0],
                defenders[:, 1],
                c="#1f77ff",
                s=90,
                edgecolors="white",
                linewidths=1.2,
                zorder=5,
                label="Defense",
            )
        if len(offense):
            ax.scatter(
                offense[:, 0],
                offense[:, 1],
                c="#ffffff",
                s=70,
                edgecolors="black",
                linewidths=1.0,
                zorder=5,
                label="Offense",
            )
        if len(ball):
            ax.scatter(
                ball[:, 0],
                ball[:, 1],
                c="#8B4513",
                s=45,
                marker="D",
                edgecolors="white",
                zorder=6,
                label="Ball",
            )

        release_tag = "  |  PASS RELEASED" if frame_id == pass_frame else ""
        orientation_note = (
            "Offense →  |  Red = open space  |  Green = tightly covered"
            f"{release_tag}"
        )
        title = f"{base_title}\n{orientation_note}" if base_title else orientation_note
        ax.set_title(title, fontsize=11, pad=8)
        ax.legend(
            loc="upper right",
            ncol=3,
            fontsize=8,
            framealpha=0.7,
        )

        colorbar = fig.colorbar(heat_map, cax=colorbar_ax)
        colorbar.set_label("Distance to nearest defender (yd)", fontsize=9)
        colorbar.ax.tick_params(labelsize=8)

        frame_path = os.path.join(tmpdir, f"f_{index:03d}.png")
        fig.savefig(frame_path, dpi=FRAME_DPI, facecolor=fig.get_facecolor())
        plt.close(fig)
        frame_paths.append(frame_path)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    images = [imageio.imread(path) for path in frame_paths]
    imageio.mimsave(out_path, images, duration=0.12, loop=0)

    for frame_path in frame_paths:
        try:
            os.remove(frame_path)
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass
    return out_path
