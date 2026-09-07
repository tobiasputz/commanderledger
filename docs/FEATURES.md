# Implemented scope

| Area | Included |
|---|---|
| Local runtime | Python/FastAPI; SQLite/SQLAlchemy; Alembic; no account; bundled HTMX/Plotly; no frontend build |
| Players | Create/edit, archive/restore, preferred name, notes, color, similar-name warning, safe merge, profiles |
| LGS opponents | Game-local anonymous seats, nicknames, descriptions, commander text, links, notes, multi-appearance conversion |
| Decks | Multiple decks per owner, commander/secondary text, identity, archetype, bracket, budget, notes, statuses, retirement dates, links, text snapshot, color |
| Ownership | Transfer through owner edit, interval history, historical participant snapshots, copy with new identity |
| Game entry | Quick/detailed form, add/remove/reorder seats without reload, player-specific active decks, inline deck creation, winner/start controls |
| Results | Sole win, shared victory, draw, abandoned, no contest, unknown; coherent result/seat validation |
| Detail fields | Location/event, setting, date, duration, turns, elimination order, ending, notes, tags, memorable moment, ratings |
| Enjoyment | Overall/deck/social ratings, optional named rater, configurable five labels, mean/median/distribution/sample/trend, explicit private-note access |
| Statistics | Eligible counts, outright win rate, fractional shared credit, expected share by pod size, performance difference/ratio, date range, small samples |
| Analytics | All twelve requested chart categories; filters; minimum-sample rankings; LGS/private and known/mixed segments |
| Profiles | Player/deck/event/location histories; owned/played decks, result breakdowns, duration, enjoyment, date comparison, matchups |
| Matchups | Player/deck/commander/archetype co-participation records; favorable/difficult at threshold; repeated opponent categories deduplicated per pod |
| Home | Primary record action, recent games, frequent player/deck shortcuts, summary counts, current session, duplicate pod |
| Editing | Game/player/deck/location/event/rating editing; transactional writes; duplicate keys; archived/trash restoration; timestamps |
| Search/tables | Global search; game filters/sort/server pagination; collection filter/sort/pagination; generic data-table filter/sort/pagination |
| Recovery | Online SQLite snapshots; settings directory/manual backup; startup/pre-migration/pre-merge/pre-restore snapshots; full JSON restore validation |
| Exports | Full JSON; CSV games/participants/players/decks/ratings; text game history; private notes omitted from ordinary exports |
| Interface | Dark/light theme; responsive layouts; focus/skip-link support; native touch controls; status/errors; empty states |
| Delivery | Windows and Unix launchers; initialization/demo/backup commands; pinned requirements; environment example; migrations; tests; README |

## Explicit choices

- Secondary commanders/partners/backgrounds share the commander text field. Color theme satisfies the optional deck image-or-color requirement.
- No-winner-recorded is represented as **unknown**, distinct from a completed **draw**.
- Expected share is theoretical `mean(1/pod size)`; draws have zero actual win credit and remain eligible.
- Pod/game filters include opponents in the selected pods. Deck status filters use current record status.
- Player enjoyment labels refer to **games involving them** and **decks they played**. No objective personality score is computed.
- Permanent identity statistics update after conversions/merges, while historical display snapshots stay readable as originally entered.
- Anonymous conversion does not infer permanent deck identities or assume matching nicknames are the same person.
- Restore replaces the full dataset; undoing a merge requires its safety backup.
- Decklist text is a current deck snapshot, not a per-game versioned decklist.
- SQL/API validation and server rendering are automated. Real-browser visual/mobile QA was blocked by local-server access restrictions; the screenshot entries in the README are placeholders.

## Deferred / outside scope

Rules-complete commander/partner validation remains manual. Scryfall suggestions, metadata, images and caching are now implemented, as is single-owner hosted authentication. There is no managed cloud account created for you, external deck-site importer, CSV import, draft autosave, live life counter or tournament tiebreak engine. These are documented scope limits, not nonfunctional controls in the UI.

## v2 additions

- Scryfall autocomplete, fuzzy-name lookup with explicit apply, Oracle text, images and combined color identity.
- Persistent, bounded response cache; conservative API throttle and outage fallback.
- Owner login with scrypt hash, revocable sessions, CSRF checks, login throttling and protected data/export routes.
- Dockerfile, Railway config, Render Blueprint and optional Compose file. Persistent-volume mount guard.
- iPhone home-screen manifest/icons; no offline synchronization.
- HOSTING.md with verified provider comparison and complete setup instructions.
