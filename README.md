# Arcfin Site

[![Deploy](https://git.psmattas.com/ArcFin/arcfin-site/actions/workflows/deploy.yml/badge.svg?branch=main)](https://git.psmattas.com/ArcFin/arcfin-site/actions?workflow=deploy.yml)

The website for [Arcfin](https://git.psmattas.com/ArcFin/ArcFin), an open-source Jellyfin client for iPhone, iPad, Mac and Apple TV. It lives at **[arcfin.psmattas.com](https://arcfin.psmattas.com)**.

The site is plain, hand-written HTML and CSS: no framework, no build step, no backend and no tracking. What's in `site/arcfin.psmattas.com/` is exactly what's served.

> Looking for the app? Its code, issues and releases are in **[ArcFin/ArcFin](https://git.psmattas.com/ArcFin/ArcFin)**.

---

## Pages

| Path | What it's for |
|---|---|
| `/` | Landing page: features, platforms, privacy, open source, roadmap, FAQ and the TestFlight link |
| `/support` | Help and FAQ, plus contacts. TestFlight's release notes link here, and App Store Connect requires it |
| `/changelog` | Every TestFlight build's release notes, filterable by platform. Built from the app's releases on each deploy |
| `/contribute` | How to help with code, issues, translations and testing |
| `/privacy` | Privacy Policy. Required by App Store Connect |
| `/terms` | Terms of Use, alongside Apple's Standard EULA |
| `/data-protection` | UK/EU GDPR and CCPA notice |

The app's Settings screen links to the support and legal pages, so **keep their paths stable**.

## Layout

```
scripts/releases.py         Adds versions and the changelog at deploy time
site/arcfin.psmattas.com/
├── index.html              Landing page
├── changelog/ support/ contribute/ privacy/ terms/ data-protection/
└── assets/
    ├── site.css            Every style. Colours mirror the app's DT tokens, light and dark
    ├── site.js             Scroll fade-in and mobile menu only; pages work without it
    ├── shots/              App screenshots (WebP)
    ├── og.png              1200×630 link preview
    └── logo.png, favicon.png, store badges
```

Each page repeats the same header and footer, so a change to either goes in every `index.html`.

## Previewing locally

The pages use root-relative links (`/assets/…`), so serve the folder rather than opening the files directly:

```sh
cd site/arcfin.psmattas.com
python3 -m http.server 8000
```

Then open <http://localhost:8000>. Check both light and dark appearance and a phone-width window before pushing.

## Updating screenshots

Screenshots live in `assets/shots/` as WebP: 660 px wide for portrait, 1400 px for landscape. To update one, replace the file with one of the same name and aspect ratio. To add one, update the `width` and `height` on its `<img>` too. Use a demo library with public-domain titles, not a personal server.

## Keeping it accurate

The landing page, Privacy Policy and Data Protection pages describe what the app actually does: which services it talks to (your Jellyfin server, and optionally Seerr, TMDB, Wikidata, YouTube and Google Cast), what stays on the device and which permissions it asks for. When the app changes what data it touches, or gains a platform or service, update those pages and their effective date in the same change. They aren't boilerplate.

The roadmap on `/` follows the [app's milestones](https://git.psmattas.com/ArcFin/ArcFin/milestones). Update it when a version ships.

## Deployment

Every push to `main` deploys automatically. The [Deploy workflow](.gitea/workflows/deploy.yml) runs on the project's own Gitea Actions runner (Ubuntu) and uses rsync over SSH to mirror `site/arcfin.psmattas.com/` to the web server. Files removed from the repo are removed from the server too. A deploy also runs every hour, and can be started by hand from the Actions tab.

### Versions and changelog

Two things on the site aren't edited by hand: the version on each platform card and in the hero badge, and the `/changelog` page. Before syncing, the deploy runs [`scripts/releases.py`](scripts/releases.py), which reads the app repository's [release feed](https://git.psmattas.com/ArcFin/ArcFin/releases.rss). It then:

- writes the newest release for each platform into every element marked `data-version="iOS"`, `"macOS"`, `"tvOS"` or `"latest"`;
- rebuilds the changelog between the `<!-- releases -->` markers in `changelog/index.html`, grouped by version and build, with a platform filter. The badges and the TestFlight review note are left out.

A newly published release shows up within the hour. Nothing is committed to this repository, so no bot needs push access, a token or a signing key. If the feed can't be read, the deploy keeps the versions and changelog already in the repo. To refresh that copy, run the script locally and commit the result:

```sh
python3 scripts/releases.py site/arcfin.psmattas.com
```

## Feedback

This repository is code only, so issues and pull requests are turned off here. If something on the site is wrong, out of date or hard to use, please [open an issue in the app repository](https://git.psmattas.com/ArcFin/ArcFin/issues/new/choose) and mention the page, or email [support.arcfin@psmattas.com](mailto:support.arcfin@psmattas.com).

## License

The site's content, design and images are **all rights reserved**. See [`LICENSE`](./LICENSE). The app's source code is separately licensed under the AGPL-3.0, and the Arcfin name and logo are trademarks covered by neither.
