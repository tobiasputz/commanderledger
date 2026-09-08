# Commander Ledger v5 — playgroup update

This update keeps the same iPhone **Add to Home Screen** workflow. It does not require a native app, a new Railway service, a new domain, or new secrets.

## Safest Railway update

1. In the running app, open **Playgroup studio → Data care → Create backup now** and download the newest backup.
2. Keep the existing Railway service, `/data` volume, public domain, and variables.
3. Replace the contents of your GitHub repository with the contents of this `commander-ledger` folder, then commit/push. Do not upload the outer folder as an extra directory level.
4. Railway will redeploy automatically. Startup adds the v5 tables without replacing existing players, decks, games, or settings.
5. Wait for **Deploy successful**, open the app, and refresh Safari. The navigation must show **Live game** and **Playgroup studio**; opening the studio shows **COMMANDER LEDGER v5** above its title.
6. Open **Playgroup studio → Data care → Integrity check**. It should report `OK`.

If the old design is cached on iPhone, close the Home Screen app completely and reopen it; if necessary, visit the HTTPS URL once in Safari and refresh there.

## Existing Railway variables

Keep these values and your existing password hash:

```text
PORT=8000
COMMANDER_MODE=hosted
COMMANDER_PUBLIC_URL=https://commanderledger-production.up.railway.app
COMMANDER_DB=/data/commander.db
COMMANDER_BACKUPS=/data/backups
COMMANDER_REQUIRE_MOUNT=true
COMMANDER_PASSWORD_HASH=<keep your existing secret value>
```

No additional variable is required. Optional `COMMANDER_DATABASE_URL` enables a PostgreSQL game database, but authentication and scheduled backup files still require `/data`. SQLite on the mounted volume remains the simplest setup.

## What is new

- **Live game:** life, commander damage, poison, energy, experience, commander tax, turns, timer, random starting player, eliminations, undo/redo, wake lock, recovery, multi-device conflict protection, and conversion into a permanent record.
- **Player portal:** invite an existing player. Players manage only their decks and submit their own feedback. Group scores stay sealed until every enabled participating account submits. Private notes remain visible to their author through the portal and to the owner through full database backups.
- **Deck laboratory:** Scryfall mana curve, card types, editable role heuristics, color/legality warnings, duplicates, partial prices, unresolved lines, and overlap with other decks. It deliberately does not invent a power score or claim complete combo detection.
- **Safe source refresh:** check Moxfield/Archidekt, review the diff, then apply with a reason. Local changes block stale previews. Automatic checks never apply changes.
- **Seasons and recaps:** date-bounded records, milestones, streaks, rivalries, commanders, moments, and a downloadable recap image.
- **Leagues:** attendance, fair 3–5 player pods, byes, repeat-opponent reduction, frozen scoring, game matching, locked rounds, correction reasons, standings, and CSV export.
- **Data care:** daily JSON backups (30 scheduled copies retained), downloads, restore preview, integrity validation, duplicate hints, and an owner audit log.

## Player invitations

1. Open **Playgroup studio → Player accounts**.
2. Choose a player and tap **Create invitation**.
3. Send the complete link privately. Its secret is after `#`, so it is not sent in the web request or server log.
4. The player opens it within 48 hours, chooses a username and a passphrase of at least 12 characters, then signs in normally.
5. A new invitation acts as a password reset. Disabling or unlinking revokes sessions without deleting the player or decks.

Credentials are intentionally outside game-data JSON backups. After restoring a backup from another instance, review account-to-player mappings.

## Operational notes

- Live games save to the server and keep a recovery copy in that iPhone browser. Undo is device-local. Concurrent saves stop with a conflict instead of silently overwriting newer state.
- Scheduled jobs run while Railway is awake; sleeping services do not run jobs while stopped. Manual backup remains available.
- Scryfall analysis/artwork require internet. Prices cover only returned cards/currencies and are estimates.
- Moxfield can deny automated access; the text-export fallback remains. Archidekt depends on its public endpoint.
- Changing a recorded game’s player set invalidates sealed group feedback and removes ratings published from it, allowing clean resubmission.
- `/api-documentation` is owner-only in hosted mode and is not a third-party compatibility promise.

## Rollback

Startup creates a database snapshot before migration. To roll back data, stop the service and restore a known-good SQLite snapshot to `/data/commander.db`. Deploying old v4 code alone is not a complete database rollback.
