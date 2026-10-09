# Defensive Coverage Void Map

A coach-facing Flask application for exploring NFL tracking data. Select a game
and play to generate a full-width animated **Coverage Void Map**, review the
called coverage, and evaluate the result from the defense's perspective.

## Public demo

**[Open the GitHub Pages demo](https://billu615.github.io/NFLxAWS-Big-Data-Bowl/defensive-coverage-void-map/)**

The public site contains a curated set of representative Cover-1, Cover-2, and
Cover-3 plays. The local Flask application supports every game and play for
which tracking data is available.

## What the tool shows

- **Coverage density:** every grid point is colored by its distance to the
  nearest defender. Red is open space farther from a defender; green is tightly
  covered space.
- **Play animation:** the stable 1280 × 640 field view runs from the snap through
  the pass outcome and marks the `pass_forward` frame.
- **Consistent direction:** left-moving plays are rotated 180 degrees so the
  offense always advances from left to right while formation left/right is
  preserved.
- **Defensive result:** interceptions, sacks, incompletions, completions, and QB
  scrambles are summarized from the defense's perspective.
- **Coverage analysis:** the app reports the coverage family and type, defensive
  personnel, defenders in the box, offensive formation, drop-back, play-action
  status, structural weak points, and the largest downfield void at release.

## Dataset required (not included)

**The NFL tracking dataset is not included in this repository.** Before running
the application, place the CSV files in a `data/` directory beside `app.py`:

```text
defensive-coverage-void-map/
├── app.py
├── coverage_core.py
├── coverage_void_map.py
├── requirements.txt
├── templates/
│   └── index.html
└── data/
    ├── games.csv
    ├── plays.csv
    ├── players.csv                    # optional for this application
    └── tracking/
        ├── tracking_<gameId>.csv
        └── ...
```

Required columns include the standard regional-event fields used by the NFL Big
Data Bowl files: `gameId`, `playId`, `frameId`, `team`, `x`, `y`, `event`, and
`playDirection` in tracking; game metadata in `games.csv`; and play result,
situation, personnel, and PFF coverage fields in `plays.csv`.

Only games with a matching `data/tracking/tracking_<gameId>.csv` file appear in
the web selector. The release moment is read from `pass_forward` or
`autoevent_passforward`; the dataset does not use a `pass_released` event.

## Windows setup and run commands

The following commands use the Windows `py` launcher and were tested with
Python 3.11. Run them from this folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open **http://127.0.0.1:5000**. Choose a game, choose a play, and select
**Generate Breakdown**. The first request renders a GIF; subsequent requests
for the same play use the local `out/cache/` copy.

If PowerShell blocks virtual-environment activation, the application can still
be run with exact interpreter paths:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Command-line usage

The CLI uses the same renderer and distance-field implementation as the web
application:

```powershell
py coverage_void_map.py --list
py coverage_void_map.py --game 2021090900 --play 137 --no-compare
py coverage_void_map.py --only-compare
```

A play run writes a pass-release PNG and looping GIF to `out/`; it also attempts
an MP4 export when ffmpeg is available. The aggregate command compares average
void locations across Cover-1, Cover-2, Cover-3, and Quarters samples.

## Defensive result mapping

| Offensive result | Defensive headline |
|---|---|
| Interception | `DEFENSE WIN — Interception` |
| Sack | `DEFENSE WIN — Sack` |
| Incomplete pass | `DEFENSE WIN — Pass Broken Up / Incomplete` |
| Completion for no gain or a loss | `DEFENSE WIN — Completion for no gain/loss` |
| Completion for 1–9 yards | `DEFENSE OK — Short completion` |
| Completion for 10+ yards | `DEFENSE BEATEN — Completion` |
| QB scramble | `DEFENSE PRESSURE — QB Scramble` |

The breakdown also reports down and distance and whether the offense gained a
first down.

## Project files

```text
app.py                 Flask routes, result mapping, and coverage analysis
coverage_core.py       Shared data loading, heat-map math, and GIF renderer
coverage_void_map.py   CLI snapshot, animation, and coverage comparison
templates/index.html   Responsive, full-width coach interface
requirements.txt       Python runtime dependencies
```

Generated files are stored under `out/` and should not be committed. Raw data,
virtual environments, generated media, and credentials should also remain
local.
