# NFL Defensive Pocket Analysis

[![Deploy pocket analysis page](https://github.com/billu615/NFLxAWS-Big-Data-Bowl/actions/workflows/pages.yml/badge.svg)](https://github.com/billu615/NFLxAWS-Big-Data-Bowl/actions/workflows/pages.yml)

An NFL Big Data Bowl project that uses player tracking and Pro Football Focus (PFF) scouting labels to study how defensive pass rushers compress and penetrate the quarterback's pocket.

The project is designed around questions a defensive coordinator or defensive-line coach can act on:

1. **Where did the rush threaten the pocket?**
2. **How quickly did the threat reach the quarterback?**
3. **Which rusher–blocker matchup produced the result?**
4. **Did the rush maintain containment while creating pressure?**

## Interactive dashboard

**Dashboard URL:** https://billu615.github.io/NFLxAWS-Big-Data-Bowl/pocket_analysis/

The dashboard provides a game-and-play selector with synchronized playback:

- Animated pocket-collapse map
- Frame slider, play/pause, reset, and playback-speed controls
- Quarterback, core offensive line, help blockers, and pass rushers
- Initial blocker–rusher assignments and rusher paths
- Nearest-rusher distance timeline
- First-threat time and approach lane
- PFF hurry, hit, and sack results
- Defensive coaching summary for each play
- Shareable URLs containing the selected game and play

All plays are standardized so the offense moves from left to right. Directional labels are stated from the offense's perspective first, such as **“offense left / defense right.”**

## Football concept

The **offense forms the pocket** around its quarterback. Defensive pass rushers try to deform that protected space by winning around an edge, creating interior push, opening a path for a teammate, or forcing the quarterback away from the intended launch point.

Sacks alone provide an incomplete evaluation. A successful rush can also create:

- A hurry or quarterback hit
- A forced movement or early throw
- A protection adjustment
- An escape lane for the quarterback
- Pressure that arrives too late to receive a box-score result

Tracking data lets us inspect how every rep develops rather than evaluating only the final outcome.

## Dataset

The analysis uses the NFL Big Data Bowl pass-protection dataset:

- Weeks 1–8 of the 2021 NFL season
- 122 games
- 8,557 source passing plays
- 8,532 plays with complete dashboard pocket measurements
- 264,729 animation frames
- Player and football positions sampled at approximately 10 Hz
- PFF player roles, initial blocker assignments, hurries, hits, and sacks

The 25 omitted plays did not contain all timing, quarterback, rusher, or core-line information required by the extraction rules.

The raw dataset is expected at:

```text
nfl-big-data-bowl-regional-event-data/data/
├── games.csv
├── plays.csv
├── players.csv
├── pffScoutingData.csv
└── tracking/
```

The source-data directory is intentionally ignored by Git.

## Key measurements

### Pocket phase

The measured pocket phase starts at the snap and ends at the first pass release, sack, declared run, or five-second limit.

### First threat

A **first threat** is the first frame where a pass rusher comes within **2.5 yards** of the moving quarterback:

- **Quick threat:** no later than 2.0 seconds
- **On-time threat:** after 2.0 seconds but no later than 2.5 seconds
- **Late threat:** after 2.5 seconds

This is an exploratory proximity measure—not an official NFL or PFF pressure definition.

### Pocket shape

The dashboard approximates the pocket with a triangle connecting the quarterback and the two widest core offensive linemen. It provides an understandable representation of pocket width and front cushion, but it is not an official pocket boundary.

### PFF pressure result

PFF hurry, hit, and sack credits are displayed separately from tracking-derived proximity. Disagreement between the two is treated as a film-review prompt rather than proof that either measurement is wrong.

## Defensive coordinator use cases

The dashboard can help coaches:

- Locate recurring left-edge, interior, and right-edge threats
- Compare how quickly different rushers reach the quarterback
- Identify blocker matchups to target in a weekly game plan
- Review whether rush depth creates quarterback escape lanes
- Separate quick disruption from late cleanup pressure
- Find productive rushes that do not appear in sack totals
- Build focused film queues for meetings and player development

The tracking analysis should direct coaches to useful film—not replace film review or become a standalone player grade.

## Repository structure

```text
.
├── Initial Analysis/
│   ├── 01_data_overview.ipynb
│   └── 02_pocket_situation_analysis.ipynb
├── pocket_analysis/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── pages-root.html
│   ├── data/
│   │   ├── manifest.json
│   │   └── games/<gameId>.json
│   ├── scripts/build_dashboard_data.py
│   └── README.md
└── .github/workflows/pages.yml
```

### Initial notebooks

- [Initial data overview](Initial%20Analysis/01_data_overview.ipynb)
- [Pocket situation analysis](Initial%20Analysis/02_pocket_situation_analysis.ipynb)

## Local setup

This project uses [uv](https://docs.astral.sh/uv/) for the Python environment.

```bash
uv sync
```

Regenerate the static dashboard data from the raw CSV files:

```bash
uv run python pocket_analysis/scripts/build_dashboard_data.py
```

The builder processes one game at a time and writes compact JSON under `pocket_analysis/data/games/`. The browser only downloads the selected game.

## Preview the dashboard locally

Browsers block the dashboard's `fetch()` calls when opening `index.html` directly. Start a local HTTP server from the project root:

```bash
uv run python -m http.server 8000 --directory .
```

Then open:

**http://localhost:8000/pocket_analysis/**

Stop the server with `Ctrl+C`.

## GitHub Pages deployment

The deployment workflow is located at `.github/workflows/pages.yml` and publishes only the static dashboard assets.

To enable deployment:

1. Open **Repository Settings → Pages**.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. Push a dashboard change to `main`, or rerun **Deploy pocket analysis page** from the Actions tab.
4. Wait for the deployment workflow to complete successfully.

The Pages artifact contains:

```text
/index.html                       # Redirects to the dashboard
/pocket_analysis/index.html
/pocket_analysis/app.js
/pocket_analysis/styles.css
/pocket_analysis/data/
```

The raw source data, preprocessing code, notebooks, and other repository files are not included in the public Pages artifact.

## Method limitations

- A 2.5-yard radius does not independently prove that a defender won the rep.
- Distance does not fully describe leverage, blocker control, or the quarterback's throwing motion.
- The triangular pocket approximation cannot represent every curved or asymmetric pocket.
- Initial assignments can change after chips, twists, stunts, and protection switches.
- Planned rollouts and scrambles require different interpretation from traditional dropbacks.
- Coverage and quarterback decision-making affect how long the rush has to arrive.
- Player evaluation requires role adjustment, opponent context, minimum-rep rules, and uncertainty estimates.

## Data publication notice

The generated dashboard files contain a reduced derivative of player tracking for pocket participants. Confirm that the NFL Big Data Bowl terms permit public redistribution before publishing `pocket_analysis/data/games/`. Raw source CSV files remain ignored by Git and are not copied into the Pages artifact.

Coverage Void Map
This project analyzes NFL Big Data Bowl player-tracking data to visualize how defensive coverage changes during a play. It generates animated heat maps that highlight open space on the field, making it easier to identify coverage gaps and defensive breakdowns. The project includes a Flask web app and a command-line tool for exploring games, plays, coverage schemes, and outcomes from a defensive perspective.
