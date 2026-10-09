# NFL Defensive Coordinator Analytics

[![Deploy pocket analysis page](https://github.com/billu615/NFLxAWS-Big-Data-Bowl/actions/workflows/pages.yml/badge.svg)](https://github.com/billu615/NFLxAWS-Big-Data-Bowl/actions/workflows/pages.yml)

This repository contains NFL Big Data Bowl projects that turn player-tracking data into practical defensive coaching visuals. The primary target audience is an **NFL defensive coordinator**, with supporting value for defensive-line coaches, secondary coaches, scouts, and analysts.

The goal is to answer actionable questions such as:

- Where and when does the defense create pressure?
- Which matchups or rush paths disrupt the quarterback?
- Where does coverage leave usable space for the offense?
- How can tracking data direct coaches to the right film?

## Projects

### 1. Defensive Pocket Command

[Open the pocket-analysis dashboard](https://billu615.github.io/NFLxAWS-Big-Data-Bowl/pocket_analysis/)

An interactive dashboard for examining how pass rushers compress and penetrate the quarterback's pocket. Coaches can select a game and play, scrub through tracking frames, and review:

- Animated quarterback, blocker, and pass-rusher movement
- Pocket shape and rusher paths
- First-threat time and approach lane
- Nearest-rusher distance timeline
- Initial blocker–rusher assignments
- PFF hurry, hit, and sack outcomes
- A defensive coaching summary for each play

A threat is currently defined as a rusher coming within **2.5 yards** of the moving quarterback. This is an exploratory reference, not an official NFL or PFF pressure definition.

### 2. Coverage Void Map

`Coverage Void Map` will analyze NFL Big Data Bowl player-tracking data to show how defensive coverage changes during a play. Animated heat maps will highlight open field space, helping coaches identify coverage gaps and defensive breakdowns.

The planned project will include:

- Game and play selection
- Coverage-scheme and outcome filters
- Animated open-space heat maps
- Defensive coverage-gap analysis
- A Flask web application
- A command-line exploration tool

This project will live in a separate `coverage_void_map/` folder and **has not been added yet**.

## Data

The current analysis covers Weeks 1–8 of the 2021 NFL season:

- 122 games
- 8,557 passing plays
- Player and football positions at approximately 10 frames per second
- PFF player roles, initial blocking assignments, hurries, hits, and sacks

Raw data is expected under `nfl-big-data-bowl-regional-event-data/data/` and is ignored by Git.

## Repository layout

```text
Initial Analysis/       Exploratory Jupyter notebooks
pocket_analysis/        Published pocket dashboard and generated data
coverage_void_map/      Planned coverage project; not added yet
.github/workflows/      GitHub Pages deployment
```

Notebooks:

- [Initial data overview](Initial%20Analysis/01_data_overview.ipynb)
- [Pocket situation analysis](Initial%20Analysis/02_pocket_situation_analysis.ipynb)

## Run the pocket dashboard locally

```bash
uv sync
uv run python pocket_analysis/scripts/build_dashboard_data.py
uv run python -m http.server 8000 --directory .
```

Then open <http://localhost:8000/pocket_analysis/>. Stop the server with `Ctrl+C`.

## Publish with GitHub Pages

1. Open **Repository Settings → Pages**.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. Push dashboard changes to `main` or rerun **Deploy pocket analysis page**.
4. Monitor the deployment in the **Actions** tab.

## Interpretation and publication notes

These tools are intended to index and explain film, not replace coaching review or serve as standalone player grades. Pocket boundaries, threat thresholds, coverage responsibility, stunts, switches, quarterback movement, and play context all require further validation.

The generated dashboard files contain a reduced derivative of player tracking for pocket participants. Confirm that the NFL Big Data Bowl terms permit public redistribution before publishing `pocket_analysis/data/games/`. Raw source CSV files remain ignored by Git and are not copied into the Pages artifact.
