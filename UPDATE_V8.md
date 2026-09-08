# v8 — shared play access, seat mapping, and table polish

## Update Railway

1. Download a complete JSON backup from **Settings** in the running app.
2. Replace the contents of the existing GitHub repository with the contents of this ZIP's `commander-ledger` folder and commit/push.
3. Let Railway redeploy, then fully close/reopen the Home Screen app or browser tab on phones so the v8 JavaScript/CSS is loaded.
4. Keep the existing domain, environment variables, owner password hash and `/data` volume. **v8 adds no database migration.**

## Invited players are now real table users

A player invitation no longer creates a deck-only portal. After signing in, a player account gets a dedicated non-admin navigation shell with:

- **Player home** with quick actions.
- **Start live game** and resume live tables they are seated in.
- **Record game** using the normal game-entry workflow.
- **My game history** and safe game-detail pages for games they participated in.
- **My decks**, including create, edit, import, trash/restore, decklist view, and direct **Play live** / **Record game** actions.
- Existing private post-game feedback.

These abilities are permission-enforced on the server, not merely hidden in the interface. A player account must be seated in any game/live table it creates, can only open live tables it is seated in, and can only mutate its own decks. Administrator pages, account controls, backups, global analytics, player/global record management, already-recorded game editing, and other owner APIs remain owner-only.

The play screens use a redacted catalog for player accounts: enough player/deck/location/event metadata to set up a table, without exposing other players' decklists, notes, backup settings, or administrator-only data. Generic game JSON is also kept owner-only so sealed/administrator-side rating information is not exposed through an API shortcut.

## Rearrange the life tracker to match the physical table

Seat order can now be changed **before** a live game starts and **during** a live game.

- Desktop live cards include **← Seat / Seat →** controls.
- Setup rows include move-up / move-down controls.
- Phone **Table tools → Arrange seats** opens a dedicated seat arranger with move controls plus **Rotate left / Rotate right**.
- The phone arranger labels each seat with its current screen position (for example, **top left** or **bottom right**) so it is easier to match the device to the actual table.

Reordering is state-safe: the active player, starting player, and commander-damage source indices are remapped with the player. Moving a player therefore does not accidentally turn damage from one commander's source into another's.

## Phone life-tracker polish

The visible `−` and `+` symbols now sit inside their halves of each player quadrant instead of crowding the central dashboard. The large half-card touch zones are retained, so taps remain forgiving while the UI is visually cleaner. The center hub is also slightly more compact, including in landscape mode.

The existing corner counter badges, tap ±1, hold ±10, swipe access to commander damage/counters, undo/redo, wake lock, save/recovery, conflict protection, dice/coin tools, and finish-game workflow remain intact.

## Daily-driver shortcuts

- Player home now leads with **Start live / Record game / My games / My decks**.
- Each player-owned deck has one-tap **Play live** and **Record game** actions.
- A member game detail includes **Next game · same pod**.
- Member mobile navigation exposes the play features directly rather than sending users into administrator menus.
- Quick game entry automatically starts an invited user in their own seat and only offers inline deck creation for that user's seat.

## Verification

The full Python test suite passes with the new member-access coverage, including checks that members can create games/live tables and manage their own decks while administrator routes and other players' deck mutations remain forbidden. Modified JavaScript files pass Node syntax checking and the Python package passes bytecode compilation.

No real-device pixel-perfect certification is claimed from this build environment. The most important phone changes are deliberately implemented with simple CSS/layout primitives and explicit touch controls; try one temporary 4-player live table after deploying to confirm the screen geometry on your particular phone.
