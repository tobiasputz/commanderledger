# Commander Ledger v4 — artwork and usability

Start with **UPDATE_V4.md** to update your existing Railway service.

Commander art from Scryfall now decorates your collection, profiles, games and entry form. Tap art for a larger card view with artist credits. The update also adds mobile bottom navigation, an owner filter, quick-play actions, improved light/dark styling, readable connection errors and a per-device artwork switch. No additional database migration or Railway variables are needed for v3 users.

## Previous release: v3 — collection and table update

Already running on Railway? Start with **UPDATE_V3.md**. Keep your existing service, variables, domain, and `/data` volume.

New in v3:
- Public Archidekt/Moxfield link import with editable preview, duplicate detection, source refresh and text-export fallback. Moxfield may require approved API access; a live request was denied during verification.
- Deck Trash and Restore without deleting historical games or statistics.
- Immutable decklist versions with per-version results and optional version selection at game entry.
- Saved named-player pods, game-night continuation, and Save & next game.
- Device-local unfinished-entry recovery, retaining the same submission key for safe retries.
- Deck rotation suggestions and monthly recaps on **At the table & recaps**.
- Automatic schema migration and backward-compatible JSON restore.

# Commander Ledger · v2

A local-first Commander game tracker built with Python 3.12, FastAPI, SQLite, SQLAlchemy, Alembic, Jinja2, HTMX and Plotly. Local use requires no account, cloud service, Node.js installation or frontend build. After the initial Python dependency installation, local game tracking works offline; optional Scryfall suggestions and images use the internet. HTMX and Plotly JavaScript are bundled locally; there are no CDN requests, analytics or external fonts.

## Online and iPhone use

**Start with [HOSTING.md](HOSTING.md)** for the Railway setup, current free/paid comparison, owner-password generation, migration of existing games and iPhone home-screen instructions. This release adds optional Scryfall suggestions/card previews and secure single-owner online mode. The app has not been deployed to a hosting account for you.

Local mode remains available without login by default. Hosted mode requires a password hash, exact HTTPS origin and persistent storage, and fails closed if configuration is missing. Scryfall lookup is optional; manual game entry remains independent of it.

## Start here — Windows

1. Extract the **entire ZIP** into a normal folder, for example `C:\Users\YourName\CommanderLedger`. Do not run the launcher from inside the ZIP preview.
2. Install **Python 3.12** from [python.org](https://www.python.org/downloads/). Enable the Python launcher during installation.
3. Double-click **`start_windows.bat`**. On first launch it creates `.venv`, installs dependencies and initializes the database. An internet connection is needed for that initial installation.
4. Open **http://127.0.0.1:8000** in your browser. Keep the terminal window open while using the tracker. Press Ctrl+C in the terminal to stop it.
5. Add players and decks, then select **Record game**. Alternatively, immediately record a pod of anonymous players using commander descriptions.

The launcher never inserts demo records. Your initial database is empty.

To install and run manually in PowerShell:

```powershell
cd "C:\Users\YourName\CommanderLedger"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.cli init
.\.venv\Scripts\python.exe -m app.cli serve
```

Activation is optional. These commands do not need PowerShell execution-policy changes.

If an old virtual environment points to an uninstalled Python version, rename the `.venv` folder and run the launcher again. Do **not** remove `data` or `backups`. If port 8000 is occupied, use `python -m app.cli serve --port 8001` with your virtual environment's Python, then open port 8001 instead.

## Linux and macOS

Install Python 3.12 or newer and the operating system's venv support if needed, then:

```bash
cd commander-ledger
chmod +x start.sh
./start.sh
```

Manual equivalent:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.cli init
.venv/bin/python -m app.cli serve
```

Direct dependencies are pinned to the versions used for verification. Python 3.12 is the tested interpreter. The Windows launcher selects Python 3.12 explicitly; with a newer interpreter, create `.venv` manually using that interpreter first.

## Try the demonstration

The deterministic demo includes **6 named players, 12 decks, 72 games, 3 locations and 3 events**, several anonymous opponents, two- through five-player pods, wins, shared victories, draws, abandoned games, no-contests, unknown results, ratings, and a retired deck.

To seed your empty database before recording real games:

```powershell
.\.venv\Scripts\python.exe -m app.cli demo
```

On Linux/macOS, use `.venv/bin/python -m app.cli demo`.

Seeding refuses a database that already has players or games. For a separate demo database, set an environment variable in a fresh terminal before running the commands:

```powershell
$env:COMMANDER_DB = "$PWD\data\demo.db"
.\.venv\Scripts\python.exe -m app.cli demo
.\.venv\Scripts\python.exe -m app.cli serve --port 8001
```

Linux/macOS:

```bash
export COMMANDER_DB="$PWD/data/demo.db"
.venv/bin/python -m app.cli demo
.venv/bin/python -m app.cli serve --port 8001
```

Closing this terminal clears the temporary environment variable. The distributed project contains no populated database or personal information.

## Using the tracker

### Record a game quickly

Choose players in seat/turn order, pick their decks, mark the winner and save. Date/time defaults to the browser's current local time. Pod size is derived from the participant cards, preventing disagreement between the stated size and actual participants.

- **Named player** adds a regular player; their active decks become available immediately.
- **Add LGS random** creates a game-local seat, never a permanent player record. Enter a commander or a deck description; a nickname is optional.
- **Create a deck for this player** opens a small inline dialog and selects the newly saved deck.
- ↑ and ↓ reorder seats. **Started** marks a known starting player independently of seat order; leave it blank when unknown.
- Select **Detailed entry** for turn count, elimination order, ending, notes, memorable moments, archetypes, deck links, tags and social-experience ratings.
- A saved game requires only a date, two or more participants, each seat's deck/commander description, and a result. A one-winner or shared-victory result also requires its winner selection.
- The save button disables while submitting. A stable submission key prevents repeated clicks or retries from creating another game.

**Duplicate pod** creates an unsaved form with participants, decks, location, event and setting copied. It resets the date to now and clears winners, starting-player selection, ratings, duration, elimination order and game notes. Nothing is saved until you submit.

### Players, decks and historical accuracy

Use the collection pages to create, edit, archive/retire and restore records. Their filter, sort and pagination controls help manage larger collections. Similar player names trigger a warning rather than a hard block, because different people can share a name.

Each deck has its own UUID. Multiple builds with the same commander are separate decks. Store secondary commanders, partners or backgrounds together in the **Commander(s)** field, separated by a semicolon. Color identity accepts W/U/B/R/G/C letters. Bracket and budget are optional user estimates; the app does not assess deck legality or power.

Changing a deck's owner records an ownership interval. Copying a deck creates a new UUID and ownership record without copying game results. Retiring or dismantling a deck keeps its complete history and permits reactivation. Deck links accept any valid HTTP(S) website; opening a link is the user's choice and requires internet access. Deck-site APIs are not used.

Game participants store snapshots of the player name, deck name, commander text, archetype, links and owner. Renaming a player, changing a deck or transferring ownership does not rewrite these snapshots. Ordinary edits of a game preserve the snapshots on unchanged seats. Selecting a different player/deck for a seat intentionally creates a new snapshot for that seat. Decklist text is a current editable snapshot on the deck record, not a per-game version history.

When entering a backdated game, known ownership intervals determine the owner snapshot. If the application has no interval covering that date, it falls back to the current owner. It cannot reconstruct deck contents, names or ownership from before they were recorded. Use distinct deck records for major rebuilds that need independent statistics.

### Remember an LGS player later

Open a game and select **Convert to named player** on an anonymous seat. Choose an existing player or enter a new name, then explicitly select any other anonymous appearances you know belong to that person. The app never automatically assumes matching nicknames mean the same person. Their old display labels remain in the game snapshots, while all selected appearances contribute to the permanent player's statistics. This action does not automatically create a permanent deck from an anonymous description.

### Merge duplicates

On Players, choose the duplicate and the record to keep. The app refuses a merge when both identities occupy the same game. It moves participant statistics, current decks, ownership references and ratings to the retained identity, archives the source and keeps historical names. A database backup is created before merging. Restore that backup to undo a merge; there is no one-click unmerge.

### Ratings and privacy

The five-point scale defaults to Very unenjoyable / Unenjoyable / Neutral / Enjoyable / Very enjoyable. Labels are configurable under Settings; stored values remain integers 1–5.

Three independent kinds are supported:

1. **Overall**: enjoyment of the game.
2. **Deck**: enjoyment playing against one participant's deck.
3. **Sportsmanship**: the game's optional social experience.

Quick-entry ratings are attributed to the app owner. On the game page, add ratings from a named participant. Named raters cannot rate their own deck as an opponent deck. Each `(game, kind, target seat, rater)` has one current rating; submitting it again updates that rating. Ratings can be edited or removed.

Private notes appear only after explicitly opening **Edit / private note**. They are excluded from general game pages, ordinary game JSON and CSV exports. Full backup JSON and SQLite snapshots include them. **Hide subjective ratings in summaries** removes enjoyment panels/charts from general presentation. It is a display preference, not a separate access role. Hosted mode requires the owner login, but anyone with that login can read private notes. Local mode has no login unless COMMANDER_PASSWORD_HASH is configured.

### Search, profiles and analytics

Global search covers players, decks, commander descriptions, locations, events, game notes, tags and deck links. Game history supports date, player, deck, location, event, pod size, setting, pod type, commander, archetype and tag filters, sorting, pagination and a trash view.

Analytics adds a minimum-games threshold (default 5) and current deck-status filter. Filters select **whole games/pods containing the selected entity**. Rankings then describe participant performances within those pods, including opponents; they do not restrict every chart to only the selected participant. Current deck-status filtering selects pods containing a deck with that status; it does not reconstruct historical deck status.

Profiles show histories, results, ownership, deck associations, date comparisons, pod-based matchups, location/seat breakdowns, enjoyment distributions and recent form through newest-first game history. Matchups can group by player, deck, commander text or archetype. A player with a borrowed deck is credited as the participant; the stored owner is independent.

Event and location pages summarize games, named participants, deck identities/descriptions, results, duration, enjoyment and memorable notes. Select a current event in Settings to show it on the home page and default new game entry to that session.

Every data table supports client-side sorting, filtering and 15-row pagination. Game history uses server-side pagination (20 games per page). Profiles retain complete game histories; the global game-history page is more efficient for large histories.

## Statistical definitions

All statistics exclude soft-deleted games. Anonymous seats count toward pod size and all game results but never inflate the permanent-player count.

| Quantity | Definition |
|---|---|
| Games | All nondeleted appearances for this player/deck, including incomplete results |
| Eligible games, `N` | Results `win`, `shared` or `draw` only |
| Outright wins, `W` | Eligible games with result `win` where this participant won |
| Shared wins, `S` | Games with result `shared` where this participant is a shared winner |
| Draws, `D` | Games with result `draw`; every seat receives a draw |
| Losses | `N − W − S − D`; nonwinning seats in shared-victory games lose |
| Outright win rate | `W / N`; not defined when `N = 0` |
| Fractional win credit | 1 for a sole winner; `1/k` for each of `k` shared winners; 0 for other outcomes |
| Actual win share | Sum of fractional win credit divided by `N` |
| Expected win share | Mean of `1 / pod_size` across eligible games; not `1 / mean(pod_size)` |
| Difference | Actual win share minus expected win share, displayed in percentage points |
| Performance ratio | Actual win share divided by expected win share |
| Average pod size | Arithmetic mean pod size across eligible games |
| Date range beside performance | First and last eligible game dates |
| Average duration | Mean of submitted durations, including all nondeleted result types; missing durations omitted |

A four-player win, a three-player loss, a five-player two-way shared win and a four-player draw produce an outright win rate of **25%**, actual win share **37.5%**, and expected win share approximately **25.83%**. The abandoned/no-contest/unknown games in the same history do not enter those denominators.

Draws are included in the eligible denominator and receive zero win credit. Consequently, a draw-heavy group can average below its theoretical expected share. This is an explicitly chosen convention, not an estimate adjusted for draw probability. Shared wins are displayed separately and are **not** counted as outright wins. Unknown/no-winner-recorded is excluded; use Draw for a completed game intentionally declared a draw.

Ratings are arithmetic means and medians of submitted values only. Missing ratings are never zero. Distributions report counts for each value 1–5. Every displayed average includes its number of ratings. A fixed **fewer-than-five** warning marks a small sample independently of the configurable ranking threshold. Recent enjoyment is the mean of the newest five available ratings, compared with the next five when present; fewer available observations are labeled by their count. These warnings are not statistical confidence intervals.

A player's **game enjoyment** aggregates overall ratings in games involving that player. Their **opponent deck enjoyment** aggregates submitted deck ratings targeting their seats. Neither is a score for the person's character. If multiple people rate a game, each submitted rating is one observation; the application does not pretend those observations are independent samples or normalize them into one vote per game.

Performance rankings require the configured number of eligible games. Enjoyment rankings require both that many game appearances and that many submitted deck ratings. Dashboard most-played leaders use the eligible-game ranking threshold; the home page also offers unthresholded frequency shortcuts. Equal rates may appear adjacent without a special tie-break claim.

### Multiplayer matchups

These are **co-participation/pod records**, never simulated one-versus-one results. For a selected player/deck, a matchup row includes games where a matching opponent participated and reports the selected entity's result. Repeated matching archetypes/commanders within a pod count the game once for that row. One game may occur in several different rows, so rows should not be summed. Favorable/difficult labels use fractional win share only after the minimum eligible sample is met. Matchup enjoyment measures submitted ratings of the selected entity's deck within those pods.

The anonymous aggregate counts **participant appearances**, so a game with two randoms contributes two anonymous seats. LGS/home and known/mixed segments count **games**, not appearances. Untracked commander text is grouped literally: spelling variants or semicolon ordering may create separate commander groups.

## Backups, exports and recovery

- Default database: `data/commander.db`.
- Default backup directory: `backups/`. Choose another directory in Settings or use `COMMANDER_BACKUPS` before first configuration.
- Automatic timestamped SQLite snapshots run on server startup (at most once per UTC day in hosted mode), before migrations, before player merges, and before JSON restoration. They use SQLite's online backup API rather than copying a live file.
- **Create database backup** creates an immediate snapshot in the configured directory.
- **Download complete JSON backup** preserves stable IDs, all tables, settings, archived/deleted records, relationships and private notes.
- **Restore a JSON backup** validates the format, columns, foreign keys, data types, URLs, colors and game invariants in an isolated database first. It then creates a safety snapshot and replaces records in one transaction. Invalid uploads leave existing records intact. Maximum JSON upload size is 50 MiB.
- Restore replaces the full dataset; it is not a merge import. Imported settings include the original backup directory, so check that path after moving to another computer.
- CSV exports include stable identifiers for joins. They are exports, not round-trip imports; formula-like strings are prefixed with an apostrophe to reduce spreadsheet formula execution. Private rating notes are omitted.
- Human-readable history is plain UTF-8 text. Decklists can be pasted or imported from a local text file in the deck editor.
- Trash retains games for restoration. Archiving players/locations/events and retiring decks preserves results. Rating removal has a confirmation but no rating recycle bin; use a prior backup if recovery is needed.

To recover directly from a SQLite snapshot: **stop the server**, retain the current `data/commander.db` under another name, copy the desired `.sqlite3` backup to `data/commander.db`, then restart. If `COMMANDER_DB` is configured, restore to that path instead. Avoid restoring while the app is open. Backups accumulate without automatic pruning so that the app does not silently delete your recovery points.

## Phone on the same network

Your computer runs the server; the phone uses its browser. Start with:

```powershell
.\.venv\Scripts\python.exe -m app.cli serve --host 0.0.0.0 --port 8000
```

On Linux/macOS: `.venv/bin/python -m app.cli serve --host 0.0.0.0 --port 8000`.

Find your computer's LAN IPv4 address (`ipconfig` on Windows). On the same Wi-Fi network, open `http://YOUR-COMPUTER-LAN-IP:8000` on your phone. You may need to allow Python on the computer's **private** network firewall profile. The terminal and computer must remain running. No internet is required on that LAN.

Local mode binds to loopback and has no authentication by default; hosted mode uses the password login described in HOSTING.md. Anyone who can reach a LAN-exposed instance can read and edit its data, including backup/private-note functions. Use it only on a trusted network; do not port-forward it or expose it publicly. Cross-origin writes are blocked, but that is not a substitute for access control.

## Project structure and database

```text
commander-ledger/
  app/
    main.py                 Application lifecycle and same-origin middleware
    db.py                   Database configuration and sessions
    cli.py                  init, demo, serve and backup commands
    models/__init__.py      SQLAlchemy schema
    schemas/__init__.py     Pydantic request validation
    services/
      games.py              Transactional game/rating operations and snapshots
      stats.py              Shared statistics and filters
      backup.py             SQLite backups, JSON restore and CSV export
      demo.py               Deterministic optional seed data
      migrate.py            Startup migration initialization
    routes/
      api.py                JSON endpoints and exports
      pages.py              Server-rendered screens and Plotly charts
    templates/              Jinja2 pages and reusable components
    static/                 Responsive CSS and browser JavaScript
      vendor/               Bundled offline HTMX and Plotly
  migrations/
    schema_v1.py             Frozen initial schema; independent of future models
    versions/0001_initial.py
    env.py                  Backup-before-migration hook
  tests/                    Calculation, integrity, HTTP and migration tests
  docs/                     Schema and QA notes
  requirements.txt
  alembic.ini
  .env.example
  start_windows.bat
  start.sh
```

| Table | Role and relationships |
|---|---|
| players | Permanent identity; display/preferred names, notes, color, archive flag |
| decks | UUID identity; current owner → players; commander text, status, links, decklist and metadata |
| ownerships | Deck → decks; owner → players; ownership start/end intervals |
| locations / events | Reusable named, archivable records |
| games | Date, result, setting, optional location/event, duration, notes, tags, deletion flag, unique submission key |
| participants | Game → games; nullable player/deck; nullable owner snapshot; historical names/commander/links; seat, start, winner, elimination |
| ratings | Game → games; optional target → participants; optional rater → players; kind, 1–5 value and private note |
| settings | JSON-valued preferences by key |

Records use UUID primary keys and created/updated timestamps. SQLite foreign keys are enabled for every application connection. Database checks enforce result vocabulary, positive durations, rating ranges and unique seats/known players within a game; service validation enforces cross-record relationships and winner logic. Game writes and restores commit only after their dependent operations succeed. Core entities are archived or soft-deleted instead of physically removed through the UI.

Migrations use Alembic. The initial schema is frozen in `migrations/schema_v1.py` so future model edits cannot silently change migration 0001. To run upgrades manually: `python -m alembic upgrade head`. A backup is created before each online migration command, including downgrade. Do not use downgrade casually; it can remove tables.

## Testing and verification

Run tests from the project directory using the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Linux/macOS: `.venv/bin/python -m pytest -q`.

Tests use isolated SQLite databases and cover win rates, variable pod sizes, expected share, shared victories, draws, abandoned games, missing ratings, anonymous seats and conversion, historical ownership, filtering, archiving/restoring, duplicate submissions, merge conflicts, rating privacy, CSV/JSON round trips, rejected backups, migrations and all main page responses. They do not require Node.js.

See `docs/QA.md` for the final verification record and `docs/FEATURES.md` for scope. The supplied dependency versions may emit deprecation warnings from the framework's test client; these do not represent failed application tests.

### Screenshot placeholders

- **Overview:** hero, game/player/deck counts, recent pods, frequently used players and decks.
- **Quick entry:** participant cards with regular/LGS selectors, deck choices, winner and rating controls.
- **Analytics:** filters, contextual performance tables and interactive Plotly charts.
- **Mobile:** single-column participant cards and horizontally scrollable data tables.

These are explicitly placeholders, not claims that screenshots were captured.

## Known limitations and deferred enhancements

- Scryfall autocomplete, card images, Oracle metadata, canonical names, color identities and durable API caching are implemented. Commander eligibility and partner/background rules validation remain advisory/manual.
- Real-browser visual and mobile interaction verification could not be completed in the build environment because its remote browser blocked access to the local server. Server-rendering, automated service/API tests and JavaScript checks are recorded separately in QA; CSS responsiveness is implemented but not visually certified here.
- This is a single-owner local/hosted application, not a multi-account service. Named-rater attribution is an owner-entered field, not an authenticated submission from that player.
- Commander/secondary-commander names are stored as one text field; no card database, spelling normalization, legality engine or automatic deck-site import is included. Color themes and Scryfall card previews are supported; arbitrary image uploads are not included.
- Historical participant metadata is captured, but full decklist contents are not versioned per game. Ownership before the earliest recorded interval cannot be inferred.
- Brackets and budget are manual estimates; no currency conversion, valuation or bracket-rule checks are performed.
- Analytics loads the filtered game history in memory. This suits a personal playgroup; very large histories may require SQL aggregation and profile-history pagination.
- No autosaved unfinished drafts, live life totals, tournament tiebreak systems, offline phone synchronization or automatic backup pruning. The requested completed-game workflow remains usable without these enhancements.
- SQLite/JSON backup restoration replaces the dataset. CSV imports and merging independent databases are not implemented.

## Upstream references

Implementation references: [FastAPI](https://fastapi.tiangolo.com/tutorial/), [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/orm/quickstart.html), [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [HTMX](https://htmx.org/docs/) and [Plotly](https://plotly.com/python/). Bundled third-party scripts retain their upstream licensing; see `THIRD_PARTY_NOTICES.md`.
