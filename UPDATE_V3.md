# Update your running Railway app to Commander Ledger v3

You do not need another Railway service, database, volume, domain, or paid API to use the new local features. Keep the setup that already works. These changes add data to your existing SQLite database on `/data`.

## Easiest update: use your existing GitHub repository

1. Open your working Commander Ledger website. Go to **Settings & backups** and download a **JSON backup**. Keep it on your computer.
2. Download and extract the updated `Commander_Ledger.zip`.
3. Open the same GitHub repository connected to your Railway service. Select its deployed branch (usually `main`).
4. Choose **Add file → Upload files**. Upload the **contents inside `commander-ledger`**, including folders. The `Dockerfile`, `railway.json`, `app` and `migrations` folders/files should be at the repository root, as before. Do not upload the ZIP itself or nest the whole project inside another `commander-ledger` folder.
5. Commit the update. If GitHub limits how many files you can upload together, use GitHub Desktop: clone your existing repository, copy the extracted source files into that checkout, commit, and push. Upload all changed files together, including `migrations/versions/0002_collection.py`, `app/routes/features.py`, and the new JavaScript files.
6. Open Railway and watch the existing app deploy. If automatic deployments are disabled, trigger a deployment of the latest repository commit.
7. The startup migration backs up your SQLite file and adds the new tables and columns automatically. Do not run database commands manually or recreate the volume.
8. Once the deployment is healthy, reopen the site on your iPhone. If an old page is still open, close it and reopen it to load the updated scripts. Finish/save any currently open game before upgrading.

Keep these working variables:

| Variable | Value |
|---|---|
| `PORT` | `8000` |
| `COMMANDER_PUBLIC_URL` | `https://commanderledger-production.up.railway.app` |
| `COMMANDER_DB` | `/data/commander.db` |
| `COMMANDER_BACKUPS` | `/data/backups` |
| `COMMANDER_MODE` | `hosted` |
| `COMMANDER_REQUIRE_MOUNT` | `true` |
| `COMMANDER_PASSWORD_HASH` | Keep your existing value |

Keep the domain's target port at **8000** and the volume mounted at **/data**. The update contains no personal database, password, or authentication state.

If you originally deployed using the Railway CLI instead of GitHub, run `railway up` from the extracted source folder after linking it to the **existing** app service and environment. Do not create a second project.

## Smart deck import

**Deck collection → Import from link**. Select the owner, paste a public Moxfield or Archidekt HTTPS link, and press **Load preview**. The name, commanders, colors, source link, and playable decklist are filled in. Check the editable fields, then create the deck.

Multiple marked commanders/backgrounds are kept. Sideboards and maybeboards have separate fields. Custom Archidekt categories excluded from the main deck are retained under sideboard. Card quantities are retained; section text is sorted for comparison. This imports card names and quantities, not a complete printing/foil inventory. It does not guess bracket, budget, or archetype. Scryfall fills missing commander colors when available; pairing legality is not inferred.

When the owner already has that source deck, choose **Update existing** or **Create separate copy**. A deck in Trash must be restored before updating it. Manual creation, manual commander descriptions, the existing text-file upload, and quick creation during game entry still work.

**Refresh from source** on an imported deck loads the latest source data and shows added/removed lines and changed metadata before you save. A quantity change appears as a removed old line and an added new line. Updating keeps your deck identity, owner history, local notes, archetype, budget, and bracket. Card changes create a new immutable version.

### If Moxfield refuses the import

A live Archidekt import succeeded during verification. Moxfield returned an access denial from this environment. The Moxfield adapter is implemented and tested against representative response data, but an app update cannot guarantee access to a provider that denies requests.

First confirm the deck is public. If access is still refused, use the source site's **Export → text**, then the import dialog's **Source unavailable?** section to upload/paste the exported list and fill the name/commander. You can also use the ordinary manual entry form. Ask Moxfield support about approved API access for your personal tracker if you want reliable automatic imports. If Moxfield explicitly issues a User-Agent identifier, set `MOXFIELD_USER_AGENT` to that approved value in Railway. Do not copy browser cookies or attempt to bypass its challenge pages.

Imports fetch only fixed provider endpoints, do not follow redirects, have a 12-second network timeout and 5 MiB response cap, cache successful previews for five minutes (up to 100 cached decks), and back off after provider rate limits. Refresh bypasses cached results. The provider APIs are external dependencies and their response formats can change.

## Delete and restore decks

On a deck card choose **Delete**. Confirm to move it to Trash. Select **Status → Trash** to find it again, then choose **Restore**. Deleted decks disappear from new-game deck selectors and suggestions. Historical games, ownership, statistics, and versions remain intact. Retiring/dismantling is still available separately. Restoring preserves the deck's previous active/retired/dismantled status.

## Deck versions

Choose **Versions** on a deck card. Named snapshots can be saved with labels such as “September rebuild”. Editing the commander, colors or decklist/sideboard/maybeboard automatically preserves the previous state and creates a new version when content changes.

New games default to the current deck at save time. Expand/select the **Deck version** field on the participant card if entering a game played with an older build. Editing an existing game preserves its recorded version unless you explicitly choose a different one. Existing games from before this update remain **Unrecorded**; the app does not assume today's decklist was used in them. You may explicitly assign a version when you know it.

Version history shows game counts, eligible results, win rate, average pod size, and available opponent enjoyment ratings. Small samples are marked. These comparisons describe your recorded games; they do not establish whether deck changes caused different results. A named version is a snapshot, not a restore operation on the current deck.

## Saved pods and game nights

**At the table & recaps → Saved pods**: create a named group, choose players, and arrange their seat order. Use **Use pod** to start an entry; choose the decks actually played. You can add LGS randoms in that entry. Pods can also be saved from the current entry and loaded directly above its form. Pod membership is synced through your server; only unfinished drafts are device-local.

Continue a game night by selecting the location and game-night event in your first entry. Use **Save & next game with this pod**, or **Next game · same pod** on a saved game. This carries forward players, available decks, location, setting and event. It resets the date to now, winners, starting player, ratings, elimination order, duration, turns, notes, tags and memorable moment. No new game is recorded until you save. Deleted/retired decks must be reselected when they are no longer available.

## Recover an unfinished entry on your iPhone

The open entry form saves a draft to that browser as you edit. If you reopen the same entry page, choose **Resume draft**. Creating a game, continuing a particular game and editing a particular game have separate draft keys. Drafts expire after seven days. Saved games clear their draft; a failed request keeps it and reuses the submission key so retries do not create a second game.

You can continue editing an already open page during a connection interruption, then save when connected. This is **draft recovery**, not full offline installation or cross-device synchronization. Safari and a Home Screen app may have separate browser storage. Browser storage restrictions, clearing website data, or changing the domain can remove drafts. The form displays a notice if storage is unavailable.

## Suggestions and recap

**At the table & recaps → What should I play?** filters your active, nondeleted decks by owner and optional bracket estimate. Choose least recently played or fewest games. Never-played decks come first. Recommendations use recorded play history, not an external power rating.

The monthly recap shows games, named players, distinct deck records/descriptions, timed minutes, rated favorite games and memorable moments. Anonymous appearances are counted as appearances, not unique people. Missing durations/ratings are not interpreted as zero. Favorite ratings are hidden when the sensitive-statistics setting is enabled.

## Quick check after deploying

- Confirm old games are visible.
- Create a deck manually and import a public Archidekt deck.
- Delete that test deck and restore it from Trash.
- Create a pod, start an entry, type a note, then reopen it and resume the draft.
- Save the test game and check its version and monthly recap.
- Download a new JSON backup. Version-2 backups include deck versions, trash and saved pods. Old version-1 JSON backups can still be restored into v3.

## Local use and rollback

For local use, copy the updated source into your existing folder while preserving `data`, `backups`, `.env`, and `.venv`. Start using the same launch script. Dependencies are unchanged. Startup performs the same migration.

Before a Railway code rollback, consider database compatibility. New JSON backups use format version 2, which older releases cannot restore. The safest recovery is to fix forward on v3 or restore your pre-update backup with the matching code version in a separate test environment first. Restoring any JSON backup replaces the current records; it is not a merge. Keep the original pre-update download and never delete the Railway volume to troubleshoot an update.

## Verification

The release was checked with the existing regression suite plus new migration, backup, import, trash, pod, version, suggestion and recap tests. JavaScript DOM workflow simulations cover form recovery and collection/table actions. A live Archidekt response was imported successfully; a live Moxfield request was denied and exercised the fallback message. No deployment into your Railway account or real iPhone/Safari visual test was performed here.

## Sign-in form recovery

This update reuses a valid login-form cookie across tabs and refreshes the form token immediately before submission. This addresses stale sign-in pages and tabs invalidating one another. CSRF checks, HTTPS cookies, password verification and rate limits remain enabled.

If you see the old “Your sign-in form expired” message before installing the update, close old login tabs, open `https://commanderledger-production.up.railway.app/login` directly in your browser, and sign in from that freshly loaded page. If it continues, ensure cookies are permitted for this site. The message is about the browser session; it does not mean you must regenerate your password hash.
