# Defensive Pocket Command — GitHub Pages dashboard

A static, defensive-coordinator-focused dashboard for reviewing quarterback-pocket collapse from NFL tracking data.

## Published path

The site is deployed from `main` as a path within the repository's single GitHub Pages site:

`https://billu615.github.io/NFLxAWS-Big-Data-Bowl/pocket_analysis/`

The repository's root Pages URL redirects to this path.

## What it provides

- Game and play selection across Weeks 1–8 of the 2021 season
- Slider-based animation with play, pause, reset, and frame-step controls
- Synchronized pocket map and nearest-rusher distance timeline
- Core offensive line, help blockers, pass rushers, QB, initial assignments, and rusher trails
- First-threat time, approach lane, primary threat, PFF result, and pocket-phase KPIs
- Initial blocker–rusher matchup table and an automated defensive coaching read
- URL query parameters for sharing a selected game and play

## Build the static data

From the project root:

```bash
uv run python pocket_analysis/scripts/build_dashboard_data.py
```

The builder reads the ignored raw CSV files and writes compact, per-game JSON under `pocket_analysis/data/games/`. The site loads only the selected game rather than downloading the complete tracking dataset at startup.

## Preview locally

Browsers block `fetch()` from a local `file://` page, so serve the repository through a local HTTP server:

```bash
uv run python -m http.server 8000 --directory .
```

Then open <http://localhost:8000/pocket_analysis/>. Stop the server with `Ctrl+C`.

## Deploy with GitHub Pages

1. Build and review the generated data.
2. Commit `pocket_analysis/` and `.github/workflows/pages.yml` to `main`.
3. Push `main` to GitHub.
4. Open **Settings → Pages** and set **Source** to **GitHub Actions**.
5. Open **Actions → Deploy pocket analysis page** to monitor deployment.

The workflow publishes only the dashboard assets. It creates `/pocket_analysis/` in the Pages artifact and does not expose the raw source-data directory.

## Data publication note

The generated files contain a reduced derivative of player tracking for pass-pocket participants. Confirm that the NFL Big Data Bowl terms permit public redistribution before publishing `pocket_analysis/data/games/`. The raw source CSV folder remains ignored and is never copied into the Pages artifact.

## Interpretation guardrails

- The 2.5-yard threat radius is an exploratory reference, not an official NFL or PFF pressure definition.
- The shaded pocket is an explainable triangle between the QB and outside core blockers, not an official pocket boundary.
- PFF assignments identify the initial blocked defender; stunts and switches can change responsibility later in the rep.
- All plays are normalized so the offense moves right. Lanes are labelled from the offense's perspective first.
- Use the dashboard to index and explain film, not as a standalone player grade.
