# v6 — phone-first life table

## Install on your existing Railway app

1. Download a complete JSON backup from your current app's Settings.
2. Extract this ZIP and replace the contents of the existing GitHub repository with the contents of `commander-ledger`.
3. Commit/push and wait for Railway to redeploy. Keep the same variables, domain, and `/data` volume. No new migration or configuration is required for v5 users.
4. Close your iPhone Home Screen web app fully, then reopen it. Open **Live game**. Setup must say **Phone table · v6** and the in-game menu says **Table tools · v6**.

## Use at the table

- Pick 2–6 players with the preset buttons (four is the default). Choose saved players/decks to obtain their commander art, or start immediately with anonymous seats. Blank descriptions become “Untracked commander”.
- Once started, the screen is partitioned into fixed player areas. The ordinary ledger navigation disappears. Four players use a 2×2 grid. Opposite players' panels face across the table.
- Tap the left or right half of a player's area for −1/+1 life. Hold for repeated −10/+10. Release to stop.
- Tap **⚔ Damage** to open commander damage, or **◎** for poison, energy, experience and commander tax. Every counter uses large plus/minus buttons; previous/next buttons switch counters without scrolling. Swipe sideways/up/down provides shortcuts but is not required.
- Commander-damage changes also adjust life. Command-zone casts determine displayed tax. Winner/elimination controls are on the counter screen.
- The central buttons undo the last change, open the menu, and advance the turn. Menu tools include redo, timer pause/resume, wake lock where available, random starting player, d20 and coin, finish, and exit.
- Commander artwork fills each panel behind the life number, with a dark overlay for readability and artist attribution. If unavailable, a colored background remains. Enable artwork in Settings if you previously disabled it.
- Use **Finish game** after selecting the winner from their counter screen. Optional text entry is not needed for tracking or finishing.

## Preserved behavior

This is a presentation update over the original live controller: server revisions, undo/redo, local recovery, conflict detection and conversion into permanent game history are retained. Existing unfinished v5 tables can be resumed. Unsaved state remains in the original browser's local recovery store; this is not a full offline app.

The design follows common partitioned life-counter interactions, including the Lotus reference requested. It is not a full clone of Lotus's independent card-search, Planechase or other game-mode catalog.

## Verification and limits

68 backend tests pass. Automated DOM tests against a temporary live server cover tap, hold, undo, swipe, commander-damage/life linkage, poison adjustment, menu access and persistence. Script syntax also passes. A real iPhone/Safari layout test was not available in this environment; browser installation timed out. Test one temporary table on your phone before your next game night.

Four-player play is the primary phone layout. More seats remain fixed on screen but have smaller controls; a tablet is preferable for unusually large pods. Setup and the rest of the ledger retain normal forms. Only optional setup customization can require typing; live counter operation does not.
