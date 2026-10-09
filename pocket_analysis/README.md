# Defensive Pocket Command

[![Deploy pocket analysis page](https://github.com/billu615/NFLxAWS-Big-Data-Bowl/actions/workflows/pages.yml/badge.svg)](https://github.com/billu615/NFLxAWS-Big-Data-Bowl/actions/workflows/pages.yml)

**Defensive Pocket Command** is an interactive tracking dashboard for studying how NFL pass rushers compress and penetrate the quarterback's pocket. It is designed for a defensive coordinator or defensive-line coach who wants to answer three practical questions:

1. **Where did the rush threaten the pocket?**
2. **How quickly did the threat reach the quarterback?**
3. **Which rusher–blocker matchup produced the result?**

Once GitHub Pages is enabled, the dashboard is published at:

**https://billu615.github.io/NFLxAWS-Big-Data-Bowl/pocket_analysis/**

The repository's root Pages URL redirects to this dashboard.

## Football concept

The offense forms a pocket around its quarterback. Defensive pass rushers try to deform that protected space by winning around an edge, creating interior push, or opening a path for a teammate.

Sacks alone provide an incomplete picture because many successful rushes end as hurries, hits, forced movement, or quick throws. This project uses player tracking to show the development of every pass-rush rep, not only the final box-score result.

## Dataset coverage

The dashboard is built from the NFL Big Data Bowl pass-protection dataset:

- Weeks 1–8 of the 2021 NFL season
- 122 games
- 8,557 source passing plays
- 8,532 plays with complete pocket measurements
- 264,729 dashboard animation frames
- Player and football positions sampled at approximately 10 Hz
- PFF roles, initial blocker assignments, hurries, hits, and sacks

The 25 omitted plays did not contain all timing, quarterback, rusher, or core-line information required by the extraction rules.

## Dashboard features

### Game and play selection

Choose any available game and then select an individual dropback by quarter, clock, down, distance, and result. The selected game and play are added to the URL, making a specific rep shareable.

### Synchronized pocket playback

The main view combines two visuals controlled by the same frame slider:

- **Pocket collapse map:** quarterback, five core offensive linemen, help blockers, pass rushers, initial assignments, rush trails, and an estimated pocket boundary.
- **Threat timeline:** distance between the quarterback and the nearest pass rusher throughout the pocket phase.

Playback controls include play, pause, reset, frame stepping, direct slider scrubbing, and three playback speeds.

### Defensive summary

Each play reports:

- First-threat time
- Rusher approach lane
- Primary threat player
- PFF pressure result
- Duration of the pocket phase
- Initial blocker–rusher matchups
- Minimum rusher distance
- A plain-language defensive coaching read

## How to interpret the visualization

| Element | Meaning |
|---|---|
| Blue circles | Five core offensive linemen |
| Cyan diamonds | Tight ends, backs, or other help blockers |
| Red circles | Defensive pass rushers |
| Gold star | Quarterback |
| Blue shaded triangle | Estimated operating space between the QB and outside core blockers |
| Red dashed ring | Exploratory 2.5-yard threat reference around the moving QB |
| Red trails | Paths taken by pass rushers |
| Gray dashed connections | PFF's initial blocker–rusher assignments |
| Yellow vertical line | Line of scrimmage |

All plays are standardized so the offense moves from left to right. Directional labels are written from the offense's perspective first—for example, **“offense left / defense right.”**

## Metric definitions

### Pocket phase

The analysis begins at the ball snap and ends at the first pass release, sack, declared run, or five-second limit.

### First threat

The first frame where a pass rusher comes within **2.5 yards** of the moving quarterback. Timing is described as:

- **Quick threat:** no later than 2.0 seconds
- **On-time threat:** later than 2.0 seconds but no later than 2.5 seconds
- **Late threat:** after 2.5 seconds

A nearby threat is not automatically a pressure or a pass-rush win. Distance does not independently describe leverage, blocker control, throwing motion, or the quarterback's responsibility.

### Pocket shape

The dashboard approximates the pocket with a triangle connecting the quarterback and the two widest core blockers. This provides an understandable view of pocket width and front cushion, but it is not an official NFL pocket boundary.

### PFF result

PFF hurry, hit, and sack credits are displayed separately from tracking-derived proximity. A disagreement between the two is a useful film-review prompt rather than proof that either measure is incorrect.

## Defensive coordinator use cases

The dashboard can support:

- Finding recurring left-edge, interior, or right-edge pressure patterns
- Comparing how quickly different rushers reach the quarterback
- Identifying favorable blocker matchups for a weekly game plan
- Reviewing whether rush depth creates escape lanes
- Separating early disruption from late cleanup pressure
- Finding rush wins that do not appear in sack totals
- Building focused film queues for coaches and players

It should be used as a film index and explanatory tool—not as a standalone player grade.

## Extraction process

The data builder performs the following steps for each play:

1. Find the snap and end of the pocket phase.
2. Flip left-moving plays into a common direction.
3. Identify the quarterback, pass rushers, core line, and help blockers using PFF roles.
4. Calculate pocket width, front cushion, and approximate area at every frame.
5. Measure every rusher's distance to the moving quarterback.
6. Identify the first nearby threat and its approach lane.
7. Attach initial blocker assignments and PFF outcomes.
8. Write compact JSON files, one game at a time, for static browser loading.

The browser downloads only the selected game's file instead of loading the complete tracking dataset.

## Project structure

```text
pocket_analysis/
├── index.html                         # Dashboard interface
├── app.js                             # Selection, animation, and SVG rendering
├── styles.css                         # Defensive film-room visual design
├── pages-root.html                    # Redirect from the root Pages URL
├── data/
│   ├── manifest.json                  # Game selector and dataset summary
│   └── games/<gameId>.json            # Compact play data, one file per game
├── scripts/build_dashboard_data.py    # CSV-to-JSON preprocessing pipeline
└── README.md

.github/workflows/pages.yml            # GitHub Pages deployment
```

## Rebuild the dashboard data

The project uses the uv environment in the repository. From the project root, run:

```bash
uv run python pocket_analysis/scripts/build_dashboard_data.py
```

The builder reads the ignored source CSV directory and rewrites `pocket_analysis/data/`.

## Preview locally

A local HTTP server is required because browsers do not permit the dashboard's `fetch()` calls from a `file://` URL.

Run this command manually from the project root:

```bash
uv run python -m http.server 8000 --directory .
```

Then open:

**http://localhost:8000/pocket_analysis/**

Stop the server with `Ctrl+C`.

## Publish with GitHub Pages

1. Open the repository's **Settings → Pages** page.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Push dashboard changes to `main`.
4. Monitor **Actions → Deploy pocket analysis page**.
5. If the first run occurred before Pages was enabled, rerun that workflow.

The workflow creates a Pages artifact containing only:

```text
/index.html                       # Redirect
/pocket_analysis/index.html       # Dashboard
/pocket_analysis/app.js
/pocket_analysis/styles.css
/pocket_analysis/data/
```

The raw NFL source-data directory, notebooks, preprocessing script, and project files are not included in the public Pages artifact.

## Limitations and guardrails

- The 2.5-yard radius is exploratory and should be calibrated against film and expert labels.
- The estimated triangle cannot fully represent a curved, asymmetric, or broken pocket.
- Initial PFF assignments may change after chips, stunts, twists, and protection switches.
- Planned rollouts and scrambles are not equivalent to conventional pocket dropbacks.
- Coverage and quarterback decision-making influence how long the rush has to arrive.
- Player evaluation requires role adjustment, opponent context, sample-size thresholds, and uncertainty estimates.
- Tracking should direct coaches to relevant film rather than replace film review.

## Data publication notice

The generated game files contain a reduced derivative of player tracking for pocket participants. Confirm that the NFL Big Data Bowl terms permit public redistribution before publishing `pocket_analysis/data/games/`. Raw source CSV files remain ignored by Git and are never copied into the Pages artifact.
