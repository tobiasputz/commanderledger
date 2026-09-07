# Verification record

Build environment: Python 3.12.13, Linux. Direct and transitive Python versions are pinned in `requirements.txt`.

## Automated Python verification

**44 tests passed** using `python -m pytest -q`.

Covered scenarios:

- Two-, three-, four- and five-player expected win shares.
- Sole wins/losses, shared victories, draws, abandoned/no-contest/unknown exclusions.
- Missing ratings, medians, sample counts and distributions.
- Pod/setting/tag/date/commander filtering and anonymous-seat aggregation.
- Repeated matchup categories counted once per pod.
- Submission-key idempotency and invalid winner/seat/player/duration rejection.
- Anonymous conversion, identity conflicts, historical display preservation.
- Renaming, copying, archiving/reactivating and owner transfers.
- Backdated ownership lookup from recorded intervals.
- Seat reordering/editing and deletion of ratings on removed seats.
- Merge conflict refusal and safe identity consolidation.
- Named-rater target validation and private-note exclusion from normal views/CSV.
- Safe custom HTTP(S) URLs and rejection of script URLs, including in backups.
- Full JSON round trip with stable IDs/relationships; invalid restore preserves data.
- CSV spreadsheet-formula escaping.
- Location/event creation, editing and summary pages.
- Cross-site write blocking.
- Alembic upgrade, repeated upgrade, backup hook, downgrade and re-upgrade.
- Successful rendering of the principal pages and edit/duplicate forms.

The framework test client emits two upstream deprecation warnings; the tests pass. Tests use isolated databases and a temporary backup-output directory.

## JavaScript verification

All six application JavaScript files pass Node's syntax checker. Node is a build-time verification tool only; it is **not required to install or use Commander Ledger**, and the application has no frontend build.

Four DOM workflow simulations passed using an external, temporary jsdom harness connected to the actual FastAPI server:

1. Create a three-seat game with two permanent decks, an anonymous commander, separate game/participant notes, winner, duration and ratings; verify persisted response.
2. Load that game, preserve both kinds of notes, reorder seats and save an edited note.
3. Duplicate its pod and verify that winner/rating/game-note fields reset.
4. Create a permanent deck from the collection editor and verify its returned identity.

The temporary Node/jsdom dependency tree is excluded from the deliverable. The Python test suite is included and remains the supported reproducible test command.

## Demo verification

The optional deterministic seeder was run successfully: six players, twelve decks, 72 games, three locations and three events. The populated database was used for main-page response/render checks and then excluded from the ZIP so first launch starts clean.

## Unverified environment-dependent behavior

The available remote browser blocked navigation to the local application server (`ERR_BLOCKED_BY_CLIENT`). No real-browser screenshots, pixel-layout assessment or physical-phone testing is claimed. Dark/light and mobile CSS are implemented but should be visually checked on the user's machine. Windows and macOS launch scripts were reviewed but could not be executed on those operating systems in this Linux environment.


## v2 security and Scryfall checks

Thirteen additional automated tests cover password hashing, missing-host-config refusal, unauthenticated data/export denial, login CSRF, Secure/HttpOnly cookies, authenticated writes, cross-origin rejection, logout revocation, expired/forged sessions, host validation and throttling; Scryfall headers, autocomplete/combined colors, durable cache, stale/disabled operation, 429 cooldown, unsafe image/link rejection and manual entry during outages.

Docker is not available in the build environment, so no Docker image build or actual Railway/Render deployment is claimed. Provider configuration is supplied for the user's account. Existing real-browser/mobile visual QA limitations remain.


Additional JavaScript DOM checks passed for second-commander autocomplete, card preview, applying canonical names and combined colors, and preservation of a custom commander during an API outage. All application scripts pass syntax checks.

Live Scryfall verification could not complete: this environment's network approval was cancelled before a response was returned. API behavior was verified with HTTPX mock transports, including failure/rate-limit paths; a successful live Scryfall response is not claimed. The proxy-dependent test also identified a missing optional SOCKS dependency; socksio is now included in requirements, and proxy setup failures degrade to manual entry.
