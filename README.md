# Arcfin Site

The marketing/legal site for [Arcfin](https://apps.apple.com/us/app/arcfin/id6813273961) — a premium native Jellyfin client for iOS and iPadOS. Static site only, no backend, no proxy, no build step. Served from `arcfin.psmattas.com`.

Structured the same way as [RiffCheck](https://git.psmattas.com/psmattas/RiffCheck)'s site: a plain `site/<domain>/` tree of hand-written HTML, deployed as-is by Caddy.

## Pages

| Path | Purpose |
|---|---|
| `/` | Landing page — App Store / TestFlight badges, feature summary |
| `/privacy` | Privacy Policy (required by App Store Connect) |
| `/terms` | Terms of Use — supplements Apple's Standard EULA |
| `/data-protection` | GDPR/CCPA-oriented data protection notice |
| `/support` | Support contact info (required by App Store Connect) |

All four legal/support pages are linked from Arcfin's own Settings screen, not just the site footer.

## Deploy

1. Copy the contents of `site/arcfin.psmattas.com/` to `/srv/sites/arcfin.psmattas.com` on the host.
2. Add [`arcfin.caddy`](./arcfin.caddy) to wherever the other public-facing app sites live (e.g. `06_apps.caddy`), alongside the `hsts_headers` snippet it imports.
3. `caddy reload`.

## Updating the legal pages

The Privacy Policy, Terms of Use, and Data Protection pages describe Arcfin's actual data flows (what talks to your own Jellyfin/Jellyseerr/Streamystats server directly, what stays on-device, what third-party services like YouTube/Google Cast are involved). If Arcfin's feature set changes in a way that changes what data it touches, these pages need to be kept in sync — they're not boilerplate.

## License

All rights reserved — see [`LICENSE`](./LICENSE). No reuse or redistribution.
