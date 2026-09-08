# Commander Ledger v4 — artwork and usability update

## Update your existing Railway app

1. Download a JSON backup from **Settings & backups**.
2. Extract `Commander_Ledger.zip` and upload the contents of `commander-ledger` into the same GitHub repository, replacing existing source files. Include the new `app/static/appearance.js` and `appearance.css` files.
3. Let your existing Railway app redeploy. Keep its domain, variables and `/data` volume.
4. Close old app tabs and reopen the site on your iPhone to load the new styles and scripts.

No new variables, dependencies, database migrations or paid services are required when upgrading from v3. Older installations still receive the automatic v3 database upgrade. See UPDATE_V3.md for the full deployment walkthrough.

## What changed

- Commander artwork from Scryfall appears in deck collections, deck profiles, saved-game participant cards, game-entry seats, deck suggestions and a featured deck on the overview.
- Tap artwork to view a larger card and its artist credit, with a link to Scryfall. Both commanders can appear side by side; cards with two faces use their front-face art.
- Artwork uses exact commander names. Custom or unavailable cards keep a styled text fallback instead of being assigned a guessed image. Scryfall autocomplete/manual lookup remain available for correcting names.
- Images load as they approach the visible part of the page. Metadata lookups are deduplicated within each page and reuse the existing server cache and conservative rate limiter. Artwork does not block recording or saving games. Only commander names go to Scryfall, not player details, notes or game results. Images load directly from Scryfall's image host.
- Artist credits remain visible; card images link to their source. Artwork remains the property of its respective artists and Wizards of the Coast.
- **Settings → Make it yours** contains a theme button and **Show commander artwork** switch. Turning art off prevents new automatic artwork lookups/image loads and reduces mobile data use. Preferences apply to this browser/device. Images already requested before switching off may finish downloading.
- The mobile bottom navigation puts Home, Decks, Record Game, Table and Settings within reach. Save actions sit above it with safe-area spacing for iPhones.
- Updated light/dark surfaces, spacing, cards, keyboard-focus outlines and reduced-motion support. Input text is large enough to avoid common iPhone focus zoom.
- Deck collection has an owner filter, clearer ownership/color/bracket labels and a **Play this deck** shortcut. Secondary actions are grouped under **More actions**. Restore stays visible in Trash.
- Deck versions selected during entry display their own recorded commander artwork where available.
- Connection failures and unexpected server responses now show readable recovery messages without automatically retrying writes.
- The overview's collection total excludes Trash; the settings privacy description now reflects the hosted sign-in model.

## Quick tour

Open **Deck collection**, select an owner, then tap a commander's art or **Play this deck**. On iPhone, use **Settings** in the bottom bar to switch theme or disable artwork. Your existing manual entry, imports, deck versions, pods, drafts, statistics, backups and login recovery are retained.

## Verification and limits

The Python regression suite and additional exact-name image, cache, face and fallback tests passed. DOM simulations cover artwork attribution, duplicate request suppression, the card viewer and the data-saving preference. Artwork depends on Scryfall availability and correct names; the app remains usable when it is unavailable. This update does not change Moxfield's external API access restrictions. Real-device Safari visual verification was not performed in this environment.
