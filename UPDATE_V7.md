# v7 — a dedicated phone interface and visual decklists

## Update Railway

1. Download a complete JSON backup from Settings in the running app.
2. Replace the contents of the existing GitHub repository with the contents of this ZIP's `commander-ledger` folder and commit/push.
3. Wait for Railway to deploy, then fully close and reopen your iPhone Home Screen shortcut. Keep your existing domain, variables, password hash, and `/data` volume. No database migration is added in v7.
4. On your phone, the new bottom tabs are **Home · Decks · Live · Games · More**. Desktop retains the existing sidebar and dashboard.

## Phone interface

- The phone home screen has large Start live game, Record a game, My decks, and Pods & recaps tiles.
- A compact header replaces the desktop navigation. Search opens in a sheet. More contains players, analytics, studio, events, locations, settings, theme controls, sign-out and the Home Screen guide.
- Filters collapse into a drawer-like section. Data tables become labeled record cards, retaining filtering, pagination and sorting. A separate button reverses the selected sort order.
- Collection cards and forms have larger touch targets. Dialogs open as bottom sheets. Studio sections are selected as tabs instead of one long phone page.
- The separate player portal also receives the phone shell, without exposing administrator routes or other players' private data.
- Compact windows up to 760 px use this interface. Short landscape touch screens also use it. Wider desktop windows retain the desktop interface.

## Live counter badges

Each quadrant now has a corner strip showing poison and nonzero energy, experience and commander tax. **⚔ max** shows the highest damage received from a single commander, not damage added across all opponents. Use the Damage button for each source separately. Tap the badges to open counters.

The existing tap/hold life controls, undo, recovery and save-conflict protection remain in place.

## Decklist viewer

- In Deck collection, choose **View decklist**. On a deck profile, use **Inside the deck → Open decklist**. Player-portal decks also have this button.
- **Text** is the default and does not request card images.
- Select **Card stacks** for overlapping card images grouped by card type. Tap a card to enlarge it; double-faced cards offer a Flip card button when images exist.
- The viewer includes Main deck, Commanders, Sideboard and Maybeboard tabs via its section selector. Unrecognized lines and missing images remain visible rather than silently dropping cards.
- Text/card-stack preference is saved in this browser's local storage and reused for other decks and future visits. It is per device, not account-wide. Switch back to Text to stop loading card images.
- Images and card metadata come from Scryfall in bounded batches with the existing server cache/rate limit. Unavailable metadata shows a named placeholder. It is a visual browser for the saved list, not an Archidekt editor or exact-printing inventory system. Up to 300 new distinct names are loaded per opened section.

## Home Screen help

First-time phone visitors receive a dismissible guide. On the sign-in screen it is offered as a button so it does not interrupt password entry. Once opened, the guide is remembered on this device. It is not automatically shown when already running from a Home Screen icon. Reopen it through More → Home Screen guide.

On iPhone the guide explains Safari → Share (sometimes under More) → Add to Home Screen → Add, and keeping Open as Web App enabled if available. It links to [Apple's instructions](https://support.apple.com/guide/iphone/open-as-web-app-iphea86e5236/ios). Android visitors receive Chrome menu instructions.

## Verification

70 backend tests pass, including safe image URLs, double-faced cards, request bounds and service-failure handling. DOM tests cover phone/desktop mode, navigation, filters, first-visit and standalone help, image/text preference retention, image reuse, studio tabs, live touch operations and existing entry workflows. The environment did not provide a working browser engine for a rendered Safari/iPhone check, so try a temporary table and a decklist on your phone after updating.
