# Arcfin Site

[![Deploy](https://git.psmattas.com/ArcFin/arcfin-site/actions/workflows/deploy.yml/badge.svg?branch=main)](https://git.psmattas.com/ArcFin/arcfin-site/actions?workflow=deploy.yml)

The website for [Arcfin](https://git.psmattas.com/ArcFin/ArcFin), an open-source Jellyfin client for iPhone, iPad, Mac and Apple TV. It lives at **[arcfin.psmattas.com](https://arcfin.psmattas.com)**.

The site is plain, hand-written HTML and CSS: no framework, no build step and no backend. Visits are counted with Cloudflare Web Analytics, which sets no cookies; the app itself has no analytics at all. What's in `site/arcfin.psmattas.com/` is exactly what's served.

> Looking for the app? Its code, issues and releases are in **[ArcFin/ArcFin](https://git.psmattas.com/ArcFin/ArcFin)**.

---

## Pages

| Path | What it's for |
|---|---|
| `/` | Landing page: features, platforms, privacy, open source, roadmap, FAQ and the TestFlight link |
| `/support` | Help and FAQ, plus contacts. TestFlight's release notes link here, and App Store Connect requires it |
| `/roadmap` | History since May 2026, what's on TestFlight now and the plan to 1.0.0 |
| `/changelog` | Every TestFlight build's release notes, filterable by platform. Built from the app's releases on each deploy |
| `/contribute` | How to help with code, issues, translations and testing |
| `/privacy` | Privacy Policy. Required by App Store Connect |
| `/terms` | Terms of Use, alongside Apple's Standard EULA |
| `/data-protection` | UK/EU GDPR and CCPA notice |

The app's Settings screen links to the support and legal pages, so **keep their paths stable**.

## Layout

```
scripts/releases.py         Adds versions and the changelog at deploy time
scripts/fingerprint.py      Adds ?v=<hash> to asset links at deploy time
robots.txt, sitemap.xml     For search engines; the sitemap is built by scripts/i18n.py
scripts/i18n.py             Builds the translated pages from i18n/<lang>.json
i18n/                       One translation file per language
site/arcfin.psmattas.com/
├── index.html              Landing page
├── 404/ roadmap/ screenshots/ changelog/ support/ contribute/ privacy/ terms/ data-protection/
├── de/ es/ fr/ … zh-hans/  Translated pages, built by scripts/i18n.py
└── assets/
    ├── site.css            Every style. Colours mirror the app's DT tokens, light and dark
    ├── site.js             Scroll fade-in and mobile menu only; pages work without it
    ├── shots/              App screenshots (WebP); auto/ holds the ones from each release
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

Screenshots live in `assets/shots/` as WebP: 660 px wide for portrait, 1400 px for landscape.

Most come from the app itself, in `assets/shots/auto/`. Each TestFlight tag build runs a UI test against Jellyfin's public demo server and attaches `screenshots-<platform>.zip` to that release ([ArcFin/ArcFin#266](https://git.psmattas.com/ArcFin/ArcFin/issues/266)). Each file is named after its device and screen, like `iPhone-01-home.webp`, `iPad-06-library.webp` or `AppleTV-09-stats.webp`, and pages use those names directly: the [Screenshots page](https://arcfin.psmattas.com/screenshots/) shows every device, and each feature on the landing page has a toggle that shows it on iPhone, iPad, Mac and Apple TV, for the devices that have that screen.

At deploy time, `scripts/releases.py` downloads the newest **published** zip for each platform and unpacks it over the copies in `assets/shots/auto/`, so each picture is replaced in place by the newest release. That happens on the runner and the result goes to the server; nothing is committed back. The copies in the repo are only the fallback when no zip can be read, so refresh them now and then. Drafts aren't visible to the deploy, so a release's screenshots go live once it's published.

To show a new screen, add a `<figure>` for it on the Screenshots page with its `width` and `height`. Only the Lock Screen's Now Playing and the download Live Activity (`now-playing.webp`, `download-activity.webp`) are taken by hand, since a UI test can't show the Lock Screen; replace those with a file of the same name and aspect ratio. Use a demo library with public-domain titles, not a personal server.

## Keeping it accurate

The landing page, Privacy Policy and Data Protection pages describe what the app actually does: which services it talks to (your Jellyfin server, and optionally Seerr, TMDB, Wikidata, YouTube and Google Cast), what stays on the device and which permissions it asks for. When the app changes what data it touches, or gains a platform or service, update those pages and their effective date in the same change. They aren't boilerplate.

The roadmap strip on `/` and the history on `/roadmap` are written by hand and follow the [app's milestones](https://git.psmattas.com/ArcFin/ArcFin/milestones). When a version ships, move its step to done, add it to the history with its date, and add the new text to `i18n/<lang>.json` (`python3 scripts/i18n.py check` lists what's missing). The build count on both is filled in from the releases on each deploy.

## Languages

The site is available in the same eleven languages as the app. English is the source; the other ten live in folders such as `/de/` and `/zh-hans/`.

- **Translated pages:** Home, Roadmap, Support, Contribute and Changelog. The legal pages stay English only, because the English text is the binding one. Translated pages link to them and say so.
- **Translations** live in `i18n/<lang>.json`, which maps each piece of English text (a heading, paragraph, list item, button or image description) to its translation. Inline markup such as `<strong>` and links stays in the translation.
- **Building:** `python3 scripts/i18n.py build` writes the translated pages from the English ones and refreshes the language menu and `hreflang` links on every page. The deploy runs it too, so a translated page can never fall behind its English page. Anything without a translation stays in English rather than breaking.
- **Checking:** `python3 scripts/i18n.py check` lists the English text each language hasn't translated yet. Run it after changing English text.
- **Release notes** on the changelog stay in English; its labels, dates and filters are translated.
- **Choosing a language:** visitors pick one from the globe menu. If their browser prefers a supported language, a small banner offers it; the site never redirects on its own. The choice is remembered in the browser.

The first translations were machine made. To fix one, open a Translation issue in the [app repository](https://git.psmattas.com/ArcFin/ArcFin/issues/new/choose) and mention the page and language.

## Deployment

Every push to `main` deploys automatically. The [Deploy workflow](.gitea/workflows/deploy.yml) runs on the project's own Gitea Actions runner (Ubuntu) and uses rsync over SSH to mirror `site/arcfin.psmattas.com/` to the web server. Files removed from the repo are removed from the server too. A deploy also runs every hour, and can be started by hand from the Actions tab.

The site sits behind Cloudflare, which keeps CSS, scripts and images for hours. So before syncing, [`scripts/fingerprint.py`](scripts/fingerprint.py) adds a content hash to every `/assets/` link (`site.css?v=…`). A changed file gets a new URL and shows up straight away; HTML isn't cached. Keep links in the HTML as plain `/assets/…` paths and let the deploy add the hashes.

### Versions and changelog

Two things on the site aren't edited by hand: the version on each platform card and in the hero badge, and the `/changelog` page. Before syncing, the deploy runs [`scripts/releases.py`](scripts/releases.py), which reads the app repository's [release feed](https://git.psmattas.com/ArcFin/ArcFin/releases.rss). It then:

- writes the newest release for each platform into every element marked `data-version="iOS"`, `"macOS"`, `"tvOS"` or `"latest"`;
- rebuilds the changelog between the `<!-- releases -->` markers in `changelog/index.html`, grouped by version and build, with a platform filter. The badges and the TestFlight review note are left out;
- unpacks the newest screenshots for each platform (see [Updating screenshots](#updating-screenshots)).

A newly published release shows up within the hour. Nothing is committed to this repository, so no bot needs push access, a token or a signing key. If the feed can't be read, the deploy copies the versions and changelog from the live site instead, so an outage never rolls the site back to the older snapshot in the repo. To refresh that copy, run the script locally and commit the result:

```sh
python3 scripts/releases.py site/arcfin.psmattas.com
```

## Search engines, errors and headers

- `python3 scripts/i18n.py build` also writes `sitemap.xml`, listing every page with its language versions, and FAQ structured data for each page with questions, in its own language. `robots.txt` points search engines at the sitemap.
- `/404/` (and `/de/404/` and so on) is the not-found page. [`arcfin.caddy`](arcfin.caddy) serves it in the language of the folder that was asked for, with a real 404 status.
- `arcfin.caddy` also sets the security headers: a content security policy that allows only the site's own files and Cloudflare Web Analytics, plus referrer, permissions, framing and opener policies. Inline scripts are allowed only because Cloudflare injects one for its bot checks. If those are ever turned off, drop `'unsafe-inline'` from `script-src`.
- Changes to `arcfin.caddy` aren't deployed by the workflow. Copy it to the server, run `caddy validate`, then `caddy reload`.

## Feedback

This repository is code only, so issues and pull requests are turned off here. If something on the site is wrong, out of date or hard to use, please [open an issue in the app repository](https://git.psmattas.com/ArcFin/ArcFin/issues/new/choose) and mention the page, or email [support.arcfin@psmattas.com](mailto:support.arcfin@psmattas.com).

## License

The site's content, design and images are **all rights reserved**. See [`LICENSE`](./LICENSE). The app's source code is separately licensed under the AGPL-3.0, and the Arcfin name and logo are trademarks covered by neither.
