# Arcfin Site

The website for [Arcfin](https://git.psmattas.com/ArcFin/ArcFin), an open-source Jellyfin client for iPhone, iPad, Mac and Apple TV. Static site only: no backend, no proxy, no build step. Served from `arcfin.psmattas.com`.

Plain hand-written HTML under `site/<domain>/`, deployed as-is by Caddy.

## Pages

| Path | Purpose |
|---|---|
| `/` | Landing page: features, platforms, privacy, open source, roadmap, FAQ, TestFlight link |
| `/support` | Help and FAQ (linked from TestFlight's "What to Test" text), plus contacts. Required by App Store Connect |
| `/contribute` | Code, issues, translations, testing, DCO, forks |
| `/privacy` | Privacy Policy. Required by App Store Connect |
| `/terms` | Terms of Use, alongside Apple's Standard EULA |
| `/data-protection` | GDPR/CCPA notice |

The legal and support pages are also linked from Arcfin's own Settings screen, so keep their paths stable.

## Assets

- `assets/site.css` holds every style. Colours mirror the app's `DT` tokens (`Arcfin/DesignTokens.swift`), with light values under `prefers-color-scheme: light`.
- `assets/site.js` only fades sections in on scroll and closes the mobile menu. Pages work without it.
- `assets/shots/` holds app screenshots as WebP: 660px wide for portrait, 1400px for landscape. Swap a file with one of the same name and size to update a screenshot.
- `assets/og.png` is the 1200×630 link preview image.

## Deploy

1. Copy the contents of `site/arcfin.psmattas.com/` to `/srv/sites/arcfin.psmattas.com` on the host.
2. Add [`arcfin.caddy`](./arcfin.caddy) to wherever the other public-facing app sites live (e.g. `06_apps.caddy`), alongside the `hsts_headers` snippet it imports.
3. `caddy reload`.

## Keeping it accurate

The landing page, Privacy Policy and Data Protection pages describe what the app actually does: which services it talks to (your Jellyfin server, and optionally Seerr, TMDB, Wikidata, YouTube and Google Cast), what stays on the device and which permissions it asks for. When a feature changes what data the app touches, or adds a platform or service, update these pages and their effective date. They aren't boilerplate.

The roadmap section on `/` follows the Gitea milestones; update it when a version ships.

## License

All rights reserved. See [`LICENSE`](./LICENSE). No reuse or redistribution.
