"""
Coverage Void Map command-line tool
====================================================================
For every point on the field, calculate the distance to the nearest defender.
A larger distance means the area is farther from a defender, more sparsely
covered, and more open. The heat map uses red for open space and green for
tightly covered space so a coach can identify coverage voids at a glance.

The shared heat-map math and animation renderer live in `coverage_core.py` and
are used by both this CLI and the Flask web app. This script contains only the
command-line reporting and analysis entry points.

Outputs:
  1. Play animation (snap through outcome): out/anim_<game>_<play>.gif/.mp4
  2. Pass-release snapshot with Voronoi boundaries:
     out/snapshot_<game>_<play>.png
  3. Coverage comparison (Cover-3 vs. Cover-2, etc.):
     out/coverage_compare.png

Examples:
  py coverage_void_map.py
  py coverage_void_map.py --list
  py coverage_void_map.py --game 2021090900 --play 137
"""

import argparse
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial import Voronoi, cKDTree, voronoi_plot_2d

from coverage_core import (
    FIELD_Y,
    FRAME_DPI,
    GRID,
    OUT,
    available_games,
    create_landscape_field_figure,
    distance_field,
    draw_field,
    event_frame,
    frame_positions,
    load_plays,
    load_tracking,
    normalize_play_direction,
    play_view_bounds,
    render_void_animation,
)


# ---------------------------------------------------------------------------
# 1. Continuous play animation using the shared renderer
# ---------------------------------------------------------------------------
def animate_play(plays, game_id, play_id):
    row = plays[(plays.gameId == game_id) & (plays.playId == play_id)]
    if row.empty:
        raise SystemExit(f"play {game_id}/{play_id} is not in plays.csv")
    coverage = row.iloc[0].get("pff_passCoverage", "NA")

    gif_path = os.path.join(OUT, f"anim_{game_id}_{play_id}.gif")
    title_lines = [
        f"Coverage Void Map  |  {coverage}  |  Game {game_id}  Play {play_id}",
    ]
    render_void_animation(
        plays, game_id, play_id, gif_path, title_lines
    )
    print(f"[OK] Animation GIF: {gif_path}")

    # Export MP4 when the local ffmpeg integration is available.
    try:
        import imageio.v2 as imageio

        images = imageio.imread(gif_path)
        mp4_path = os.path.join(OUT, f"anim_{game_id}_{play_id}.mp4")
        imageio.mimsave(
            mp4_path,
            [images] if images.ndim == 3 else images,
            fps=10,
        )
        print(f"[OK] Animation MP4: {mp4_path}")
    except Exception as error:
        print(f"[skip] MP4 export failed (ffmpeg may be unavailable): {error}")
    return gif_path


# ---------------------------------------------------------------------------
# 2. Pass-release snapshot with defender Voronoi boundaries
# ---------------------------------------------------------------------------
def snapshot_play(plays, game_id, play_id):
    row = plays[
        (plays.gameId == game_id) & (plays.playId == play_id)
    ].iloc[0]
    def_team = row["defensiveTeam"]
    coverage = row.get("pff_passCoverage", "NA")

    tracking = load_tracking(game_id)
    trk_play = tracking[
        (tracking.gameId == game_id) & (tracking.playId == play_id)
    ].copy()
    trk_play = normalize_play_direction(trk_play)

    frame_id = event_frame(
        trk_play, ["pass_forward", "autoevent_passforward"]
    )
    if frame_id is None:
        frame_id = event_frame(
            trk_play, ["ball_snap", "autoevent_ballsnap"]
        )
    if frame_id is None:
        frame_id = int(trk_play.frameId.min())

    defenders, offense, ball = frame_positions(
        trk_play, frame_id, def_team
    )
    xmin, xmax = play_view_bounds(trk_play)
    XX, YY, distances = distance_field(defenders, xmin, xmax)
    if np.isfinite(distances).any():
        vmax = max(float(np.nanpercentile(distances, 95)), 8.0)
    else:
        vmax = 15.0
    levels = np.linspace(0.0, vmax, 26)

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

    # Voronoi boundaries show each defender's nearest-control region.
    if len(defenders) >= 4:
        try:
            voronoi = Voronoi(defenders)
            voronoi_plot_2d(
                voronoi,
                ax=ax,
                show_points=False,
                show_vertices=False,
                line_colors="white",
                line_width=0.8,
                line_alpha=0.5,
            )
        except Exception:
            pass

    draw_field(ax, xmin, xmax)
    if len(defenders):
        ax.scatter(
            defenders[:, 0],
            defenders[:, 1],
            c="#1f77ff",
            s=120,
            edgecolors="white",
            linewidths=1.4,
            zorder=5,
            label="Defense",
        )
    if len(offense):
        ax.scatter(
            offense[:, 0],
            offense[:, 1],
            c="#ffffff",
            s=90,
            edgecolors="black",
            zorder=5,
            label="Offense",
        )
    if len(ball):
        ax.scatter(
            ball[:, 0],
            ball[:, 1],
            c="#8B4513",
            s=60,
            marker="D",
            edgecolors="white",
            zorder=6,
            label="Ball",
        )

    ax.set_title(
        f"Coverage Void at pass release  |  {coverage}  |  "
        f"Game {game_id}  Play {play_id}\n"
        "Offense →  |  White lines = defender Voronoi regions  |  "
        "Red = open space",
        fontsize=11,
        pad=8,
    )
    ax.legend(
        loc="upper right",
        ncol=3,
        fontsize=8,
        framealpha=0.7,
    )
    colorbar = fig.colorbar(heat_map, cax=colorbar_ax)
    colorbar.set_label("Distance to nearest defender (yd)", fontsize=9)
    colorbar.ax.tick_params(labelsize=8)

    output_path = os.path.join(
        OUT, f"snapshot_{game_id}_{play_id}.png"
    )
    fig.savefig(output_path, dpi=FRAME_DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[OK] Pass-release snapshot: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# 3. Average void comparison by coverage family
# ---------------------------------------------------------------------------
def coverage_compare(
    plays,
    coverages=("Cover-3", "Cover-2", "Cover-1", "Quarters"),
    n_per=120,
):
    """
    Average pass-release defender spacing for each coverage family.

    Plays are aligned to the ball and rotated to the same offensive direction.
    To control runtime, each coverage uses at most `n_per` plays from the first
    12 tracking files.
    """
    games = available_games()
    use_games = games[:12]

    rel_xs = np.arange(-10, 35 + GRID, GRID)
    rel_ys = np.arange(-FIELD_Y / 2, FIELD_Y / 2 + GRID, GRID)
    relative_x, relative_y = np.meshgrid(rel_xs, rel_ys)
    relative_points = np.column_stack(
        [relative_x.ravel(), relative_y.ravel()]
    )

    accumulated = {
        coverage: np.zeros(relative_x.shape) for coverage in coverages
    }
    counts = {coverage: 0 for coverage in coverages}

    for game_id in use_games:
        try:
            tracking = load_tracking(game_id)
        except FileNotFoundError:
            continue
        pass_frames = tracking[
            tracking.event.isin(["pass_forward", "autoevent_passforward"])
        ]
        if pass_frames.empty:
            continue
        key_frames = (
            pass_frames.groupby(["gameId", "playId"])
            .frameId.min()
            .reset_index()
        )

        game_plays = plays[plays.gameId == game_id]
        for _, key_frame in key_frames.iterrows():
            play_id = key_frame.playId
            play_row = game_plays[game_plays.playId == play_id]
            if play_row.empty:
                continue
            play_row = play_row.iloc[0]
            coverage = play_row["pff_passCoverage"]
            if coverage not in coverages or counts[coverage] >= n_per:
                continue

            def_team = play_row["defensiveTeam"]
            frame = tracking[
                (tracking.playId == play_id)
                & (tracking.frameId == key_frame.frameId)
            ]
            ball = frame[frame.team == "football"][["x", "y"]].values
            defenders = frame[frame.team == def_team][["x", "y"]].values
            if len(ball) == 0 or len(defenders) < 6:
                continue

            ball_x, ball_y = ball[0]
            direction = frame.playDirection.iloc[0]
            dx = defenders[:, 0] - ball_x
            dy = defenders[:, 1] - ball_y
            if direction == "left":
                dx = -dx
                dy = -dy

            relative_defenders = np.column_stack([dx, dy])
            tree = cKDTree(relative_defenders)
            distances, _ = tree.query(relative_points, k=1)
            accumulated[coverage] += distances.reshape(relative_x.shape)
            counts[coverage] += 1

    active = [coverage for coverage in coverages if counts[coverage] > 0]
    if not active:
        print("[warn] Not enough pass-release samples for coverage comparison.")
        return None

    panel_count = len(active)
    fig, axes = plt.subplots(
        1,
        panel_count,
        figsize=(6.2 * panel_count, 5.6),
        dpi=110,
        squeeze=False,
    )
    axes = axes[0]
    means = {
        coverage: accumulated[coverage] / counts[coverage]
        for coverage in active
    }
    vmax = max(np.percentile(mean, 97) for mean in means.values())

    for ax, coverage in zip(axes, active):
        mean = means[coverage]
        heat_map = ax.contourf(
            relative_x,
            relative_y,
            mean,
            levels=22,
            cmap="RdYlGn_r",
            vmin=0,
            vmax=vmax,
        )
        ax.axvline(0, color="white", lw=1.2, ls="--", alpha=0.7)
        ax.scatter(
            [0],
            [0],
            c="#8B4513",
            s=70,
            marker="D",
            edgecolors="white",
            zorder=5,
        )
        ax.set_title(
            f"{coverage}  (n={counts[coverage]} plays)", fontsize=12
        )
        ax.set_xlabel("Downfield distance from ball (yd)")
        ax.set_ylabel("Lateral distance (yd)")
        ax.set_aspect("equal")
        fig.colorbar(heat_map, ax=ax, fraction=0.046, pad=0.02)

    fig.suptitle(
        "Average Coverage Void by scheme "
        "(red = systematically open) at pass release",
        fontsize=14,
        y=1.02,
    )
    fig.tight_layout()
    output_path = os.path.join(OUT, "coverage_compare.png")
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    print(f"[OK] Coverage comparison: {output_path}")
    for coverage in active:
        print(f"      {coverage}: {counts[coverage]} plays")
    return output_path


# ---------------------------------------------------------------------------
# Select representative examples
# ---------------------------------------------------------------------------
def pick_example(plays, coverage="Cover-3"):
    games = available_games()
    for game_id in games[:6]:
        try:
            tracking = load_tracking(game_id)
        except FileNotFoundError:
            continue
        pass_frames = tracking[
            tracking.event.isin(["pass_forward", "autoevent_passforward"])
        ]
        candidates = plays[
            (plays.gameId == game_id)
            & (plays.pff_passCoverage == coverage)
        ]
        for play_id in candidates.playId.unique():
            if (pass_frames.playId == play_id).any():
                return game_id, int(play_id)
    row = plays.iloc[0]
    return int(row.gameId), int(row.playId)


def list_examples(plays):
    games = set(available_games())
    available_plays = plays[plays.gameId.isin(games)]
    for coverage in ["Cover-3", "Cover-2", "Cover-1", "Quarters"]:
        rows = available_plays[
            available_plays.pff_passCoverage == coverage
        ].head(3)
        print(f"\n== {coverage} ==")
        for _, row in rows.iterrows():
            description = str(row.playDescription)[:70]
            print(
                f"  --game {int(row.gameId)} --play {int(row.playId)}   "
                f"{description}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Generate defensive Coverage Void visualizations."
    )
    parser.add_argument("--game", type=int, default=None)
    parser.add_argument("--play", type=int, default=None)
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--no-compare",
        action="store_true",
        help="Skip the aggregate coverage comparison to save time.",
    )
    parser.add_argument(
        "--only-compare",
        action="store_true",
        help="Generate only the aggregate coverage comparison.",
    )
    args = parser.parse_args()

    plays = load_plays()

    if args.list:
        list_examples(plays)
        return

    if not args.only_compare:
        if args.game and args.play:
            game_id, play_id = args.game, args.play
        else:
            game_id, play_id = pick_example(plays, "Cover-3")
            print(
                "[info] No play specified; selected "
                f"Game {game_id}, Play {play_id}."
            )
        snapshot_play(plays, game_id, play_id)
        animate_play(plays, game_id, play_id)

    if not args.no_compare:
        coverage_compare(plays)

    print("\nComplete. Outputs are in the out/ directory.")


if __name__ == "__main__":
    main()
