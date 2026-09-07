# Put Commander Ledger on your iPhone

## Recommended: Railway, starting with its free allowance

Checked against official provider documentation on **7 September 2026**.

| Option | Current entry price | Fit for this project |
|---|---|---|
| Railway Free | $0 subscription; $1 of resource credit/month after the initial $5, up-to-30-day trial | Best first attempt for occasional use. Supports a 0.5 GB persistent volume. Not an unlimited always-on free server. |
| Railway Hobby | $5/month minimum, including $5 of usage; excess usage is additional | Simplest paid continuation. It is a billing floor, not a $5 maximum. |
| Render Starter + 1 GB disk | Approximately $7.25/month before taxes/extra usage | Straightforward alternative with the included Blueprint. Paid disk required. |
| Render Free with this SQLite app | Not suitable | Local files disappear on restarts/spin-down/redeploy; free web services cannot attach persistent disks. |

Sources: [Railway pricing](https://railway.com/pricing), [Railway free trial](https://docs.railway.com/pricing/free-trial), [Railway volume limits](https://docs.railway.com/volumes/reference), [Render pricing](https://render.com/pricing), [Render free-service storage limits](https://render.com/docs/free).

**My recommendation:** try Railway with one app service, one persistent volume, and Serverless enabled. Upgrade to Hobby only if the free allowance is insufficient or your trial's outbound-network restrictions prevent Scryfall access. Your actual cost depends on usage; no free-forever or exact monthly-cost guarantee is possible. Watch Railway's usage estimate and set spending controls in your account.

Railway's Serverless mode sleeps inactive services and wakes them on an incoming request. Enable it and redeploy for the setting to take effect. This app has no background network polling and uses local SQLite rather than an always-connected external database, which makes sleeping practical. The first request after sleeping can be slower. [Railway Serverless](https://docs.railway.com/deployments/serverless)

Unverified Railway trials restrict outbound networking. Connect your GitHub account for automatic verification; if Railway does not verify it, Scryfall may be unavailable until you upgrade. Game entry still works with manual names. [Full versus limited trial](https://docs.railway.com/pricing/free-trial)

## 1. Prepare the project and your password

Extract the whole ZIP. Open PowerShell in the `commander-ledger` folder. If you already ran the previous version, keep its `data` and `backups` directories; do not overwrite or remove them. Version 3 automatically upgrades the database to schema 0002 on startup and accepts both old version-1 and new version-2 JSON backups. Download a JSON backup before upgrading. See UPDATE_V3.md for the existing-deployment walkthrough.

If needed, install/update dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Generate your hosted login password hash:

```powershell
.\.venv\Scripts\python.exe -m app.cli password
```

Choose a unique passphrase of at least 12 characters. The prompt hides the password and asks you to repeat it. Copy the resulting `scrypt$...$...` value for the hosting dashboard. You will type the **original password** to sign in on your phone, not the hash.

Never put the password or its hash in GitHub, screenshots or game notes. Railway's variable editor accepts the hash literally; do not add quotes. Keep the original password in your password manager.

## 2. Put the code in a private GitHub repository

Create a private repository in your GitHub account and upload the **contents of the `commander-ledger` folder**. `Dockerfile`, `railway.json`, `requirements.txt`, `app/`, `migrations/` and `alembic.ini` must be at the repository root.

The ZIP is deliberately delivered without databases, secrets, virtual environments or runtime caches. Upload those clean source files, not your personal `data`, `backups`, `.env` or `.venv` directories. If using git, the included `.gitignore` excludes those runtime paths. If uploading through GitHub's website, choose files/folders yourself; the upload interface does not apply `.gitignore` as a filter.

You do not need Docker installed on your laptop. Railway builds the included Dockerfile for you.

## 3. Create the Railway service

1. Sign in at [Railway](https://railway.com/) and create a project using **Deploy from GitHub repo**.
2. Select the private repository and the app service. Railway should detect the Dockerfile. Keep **one replica**; the app intentionally uses one Python worker with SQLite.
3. Add a **persistent volume attached to this app service**, mounted at **`/data`**. Do this before entering any real games. A free-plan volume has a 0.5 GB limit; monitor usage as backups accumulate.
4. In the service's Networking settings, choose **Generate Domain**. Use the app's listening port, normally **8000** unless Railway provides a `PORT` value. Copy the resulting HTTPS origin, for example `https://your-generated-name.up.railway.app`.
5. Add these service variables:

| Variable | Value |
|---|---|
| `COMMANDER_MODE` | `hosted` |
| `COMMANDER_PASSWORD_HASH` | The complete hash from step 1 |
| `COMMANDER_PUBLIC_URL` | The generated `https://…` origin; no path |
| `COMMANDER_DB` | `/data/commander.db` |
| `COMMANDER_BACKUPS` | `/data/backups` |
| `COMMANDER_REQUIRE_MOUNT` | `true` |
| `COMMANDER_SCRYFALL` | `true` |

6. Enable **Serverless** in the service's deployment settings to reduce idle usage, then deploy/redeploy the pending configuration. The included `railway.json` supplies the Docker build and `/healthz` health check.
7. Open the generated HTTPS address. You should see **Sign in**, not the game dashboard. Sign in with your original password.

An initial deploy may fail until the domain, password and volume are configured. That is intentional: online mode refuses to start unprotected or with a missing data mount. If the volume is missing, attach it rather than disabling the mount check.

Official references: [Docker deployment](https://docs.railway.com/builds/dockerfiles), [persistent volumes](https://docs.railway.com/volumes), [public networking](https://docs.railway.com/networking/public-networking).

## 4. Bring your existing games online

On your original local app, go to **Settings & backups → Download complete JSON backup**. On the hosted app, sign in, go to the same settings page and restore that JSON backup. Restore replaces the hosted dataset after validation and creates a safety snapshot first.

The hosted app always uses `/data/backups` from the hosting environment, even if an imported local backup remembers a Windows path. Login credentials and sessions are stored separately from game backups and are not changed by a JSON restore.

From this point, use the **hosted URL on both laptop and phone** so they share one dataset. The old local database is a separate copy; there is no background synchronization between it and the hosted database.

## 5. Use it on your iPhone

Open the hosted HTTPS address in Safari, sign in, and use Safari's **Add to Home Screen** action. The project includes an app manifest and home-screen icons. Your computer can be switched off: Railway runs the Python server.

The login lasts up to seven days unless you sign out, rotate the password or the session is invalidated. This is a home-screen web app, **not an offline-sync app**. It still needs mobile data or Wi-Fi to reach the server. Cached Scryfall data helps when Scryfall itself is down; it does not make a disconnected phone able to reach your hosted ledger.

## Scryfall features

- Commander-name suggestions while typing, including a second commander after a semicolon.
- An explicit **Look up on Scryfall** button in deck editing, quick deck creation and game-entry commander fields.
- Full card image, Oracle text, type line, color identity and Commander-format legality.
- **Use these names & colors** applies the returned canonical names and combined color identity where the form has a color-identity field. Lookup does not silently overwrite a saved deck.
- **Show Scryfall commander details** on permanent deck profiles.
- Custom, previewed and misspelled names remain saveable without lookup.

Only card-name queries are sent to Scryfall. Player names, private notes, ratings and game history are not sent. Card images load directly from Scryfall's image servers, so displaying one requires internet and reveals the normal network request to that image host.

API responses are cached in `/data/scryfall-cache.sqlite3`: autocomplete for one day, card details for seven days, with stale-cache fallback when the API is unavailable. Requests are serialized with at least 550 ms between completions and the next request (conservative for the named-card endpoint's 2/sec limit). A 429 response pauses further requests instead of retrying in a loop. Cached responses are bounded to 3,000 entries. Set `COMMANDER_SCRYFALL=false` to disable outgoing API requests; already-cached metadata may still be shown.

Format legality is **not** proof a card can be your commander. The app displays Oracle text but does not certify partner/background pairings or Commander deck legality. Two-name lookups clearly label that limitation.

References: [Scryfall API](https://scryfall.com/docs/api), [rate limits](https://scryfall.com/docs/api/rate-limits), [autocomplete](https://scryfall.com/docs/api/cards/autocomplete), [named cards](https://scryfall.com/docs/api/cards/named).

## Backups and updates

- `/data/commander.db`: your game data.
- `/data/auth.sqlite3`: hashed session tokens and login-throttle state. Never commit or share it.
- `/data/scryfall-cache.sqlite3`: regenerable public card metadata cache.
- `/data/backups/`: full game-database snapshots.

Hosted startup creates at most one automatic database backup per UTC day, rather than one on every cold start. Migration, merge, restore and manual backups still run when needed. Snapshots on the same volume protect against editing mistakes, **not loss of the volume or hosting account**. Download JSON backups periodically to your own device and before changing hosts. Backups are not automatically pruned; monitor the free volume's storage limit.

For an update, push only updated source files to GitHub and let Railway redeploy the same service with the same volume. Never delete/recreate the volume to update code. A brief interruption during a single-instance SQLite deployment is expected.

For a password change or reset, run the password command again, update `COMMANDER_PASSWORD_HASH` in Railway and redeploy. The changed hash invalidates all existing sessions. JSON restore cannot restore your login password.

## Render alternative

Connect the same repository through Render's **New Blueprint** flow and select the included `render.yaml`. It requests a paid Starter web service and a 1 GB disk at `/data`; review the displayed charges before creating it. Supply the password hash and generated HTTPS origin as environment variables. A first build may fail until its final URL is supplied; set it and redeploy.

Use the free Hobby **workspace** if offered; the actual web service and persistent disk are paid. Do not change the instance to Free while keeping SQLite. Render's free filesystem is ephemeral, and its free Postgres is not a permanent workaround because that database expires after 30 days. [Render's free limits](https://render.com/docs/free)

## Security and deployment boundaries

Online mode adds an owner-password login, scrypt password hashing, expiring/revocable random sessions, HttpOnly/Secure/SameSite cookies, CSRF tokens, exact-origin write checks, host validation, login throttling, frame blocking and no-store private responses. Credentials are environment configuration; game exports omit credential/session stores.

This remains a **single-owner application**. Sharing the password grants full access to all games, edits, backups and private notes. There are no separate player accounts or read-only roles. TLS terminates at the hosting provider. Only health status, login and static assets are public; the API, exports, card lookup and HTML game pages require login.

The Docker image deliberately starts in hosted mode. `compose.yaml` is included for advanced self-hosting behind an HTTPS reverse proxy; it is not required for Railway. Missing production configuration fails closed. No provider account, subscription or live deployment has been created by this package.

## Troubleshooting

- **Server configuration incomplete:** check the password hash and exact `COMMANDER_PUBLIC_URL`, including `https://`.
- **Persistent volume missing:** attach the volume to the app service at `/data`, then redeploy.
- **Unrecognized host:** the configured public URL must match the address you are opening. This version accepts one canonical hostname.
- **Session verification failed:** reload/sign in again, then retry. Unsaved form contents are not persisted as drafts.
- **Too many login attempts:** wait ten minutes. The app uses per-peer and global limits; behind the provider's proxy, multiple clients may share a peer limit.
- **Scryfall unavailable:** check Railway trial verification/outbound networking; continue with manual names. An upstream rate limit waits before trying again.
- **Free credits exhausted / service stopped:** inspect provider usage and plan status. Download backups before allowing a plan/volume to expire.
- **Updates lost data:** confirm the service is still using its original volume and `/data/commander.db`; do not seed demo data into your real ledger.
