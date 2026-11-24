#!/usr/bin/env python3
"""Fill the site with the app's published releases before it's deployed.

Reads the app repository's release feed once, then:
- writes the newest version for each platform into every element marked
  data-version="iOS", "macOS", "tvOS" or "latest";
- writes the release notes into changelog/index.html, between the
  <!-- releases --> and <!-- /releases --> markers, with the Arcfin Sync
  plugin's releases (from its own feed) under their own filter;
- writes the plugin's newest version into elements marked
  data-version="plugin";
- writes badges/version.svg, the app's newest version and build, which the
  app's README shows. Badge services fetch from servers Cloudflare sometimes
  challenges, so the badge is made here, from the feed this already reads;
- unpacks each platform's newest screenshots (screenshots-<platform>.zip,
  attached by the app's screenshots workflow) into assets/shots/auto/, over
  the copies in the repo. Pages use them by the name the app's screenshot
  test gives them, e.g. iPhone-01-home.webp, so a new release replaces each
  one in place.

If the feed can't be read, the versions and changelog are copied from the
live site instead, so a feed outage never rolls the site back to the older
snapshot in the repo. If the live site can't be read either, the repo's
copy is used.
"""

import email.utils
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

SITE = sys.argv[1] if len(sys.argv) > 1 else "site/arcfin.psmattas.com"
FEED = os.environ.get("RELEASES_FEED", "https://git.psmattas.com/ArcFin/ArcFin/releases.rss")
PLUGIN_FEED = os.environ.get("PLUGIN_RELEASES_FEED", FEED.replace("/ArcFin/ArcFin/", "/ArcFin/Arcfin-Sync/"))
# The runner reads the feed from inside the network, where Gitea writes
# some links with its internal address. They're rewritten to the public one.
INTERNAL = os.environ.get("GITEA_INTERNAL_URL", "").rstrip("/")
PUBLIC = "https://git.psmattas.com"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
# Builds are tagged v<version>-build-<build>.<unix time>, one tag for every platform that
# uploaded that night, and the release title lists them. Releases up to 0.4.0 have a tag per
# platform, <Platform>-<version>-build-<build>, and sort as if built at time 0.
TAG = re.compile(r"/releases/tag/v(\d+)\.(\d+)\.(\d+)-build-(\d+)\.(\d+)$")
OLD_TAG = re.compile(r"/releases/tag/(iOS|macOS|tvOS)-(\d+)\.(\d+)\.(\d+)-build-(\d+)$")
TITLE_PLATFORMS = {"iOS & iPadOS": "iOS", "macOS": "macOS", "tvOS": "tvOS"}
PLATFORMS = [("iOS", "iPhone & iPad", "ios"), ("macOS", "Mac", "mac"), ("tvOS", "Apple TV", "tv")]
PLUGIN_TAG = re.compile(r"/releases/tag/v(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")
I18N = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "i18n")


def translator(lang):
    path = os.path.join(I18N, f"{lang}.json")
    strings = {}
    if lang != "en" and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            strings = {k: v for k, v in json.load(f).items() if v}
    return lambda text: strings.get(text, text)


def warn(message):
    print(f"::warning::{message}")


def tag_platforms(tag, title=""):
    """The (platform, key) pairs a release tag covers; key is (major, minor, patch, build, time)."""
    old = OLD_TAG.search("/releases/tag/" + tag)
    if old:
        platform, *numbers = old.groups()
        return [(platform, tuple(int(n) for n in numbers) + (0,))]
    new = TAG.search("/releases/tag/" + tag)
    if not new:
        return []
    key = tuple(int(n) for n in new.groups())
    named = [TITLE_PLATFORMS[p.strip()] for p in title.split("·")[1:] if p.strip() in TITLE_PLATFORMS]
    return [(platform, key) for platform in named]


def read_feed():
    with urllib.request.urlopen(FEED, timeout=20) as response:
        root = ET.fromstring(response.read())
    releases = []
    for item in root.iter("item"):
        link = item.findtext("link", "")
        for platform, key in tag_platforms(link.rsplit("/releases/tag/", 1)[-1], item.findtext("title", "")):
            releases.append({
                "platform": platform,
                "key": key,
                "link": link,
                "date": email.utils.parsedate_to_datetime(item.findtext("pubDate")),
                "body": item.findtext(CONTENT) or "",
            })
    return releases


def read_plugin_feed():
    """The plugin's releases, newest first. Tagged v<major>.<minor>.<patch>."""
    with urllib.request.urlopen(PLUGIN_FEED, timeout=20) as response:
        root = ET.fromstring(response.read())
    releases = []
    for item in root.iter("item"):
        match = PLUGIN_TAG.search(item.findtext("link", ""))
        if not match:
            continue
        releases.append({
            "key": tuple(int(n or 0) for n in match.groups()[:3]),
            "link": item.findtext("link"),
            "date": email.utils.parsedate_to_datetime(item.findtext("pubDate")),
            "body": item.findtext(CONTENT) or "",
        })
    return sorted(releases, key=lambda r: r["key"], reverse=True)


KINDS = {"new": "new", "improved": "improved", "fixed": "fixed", "removed": "removed",
         "under the hood": "hood", "changes": "none"}


def clean(body, t):
    """Returns the notes as HTML, plus the compare and release PR links from the footer line."""
    if INTERNAL:
        body = body.replace(INTERNAL, PUBLIC)
    # Badges and the TestFlight review note are for the release page, not the site.
    body = re.sub(r"<p[^>]*>(?:(?!</p>).)*?(?:testflight-badge|img\.shields\.io)(?:(?!</p>).)*</p>\s*", "", body, flags=re.S)
    body = re.sub(r"<blockquote>(?:(?!</blockquote>).)*When will I get this build\?.*?</blockquote>\s*", "", body, flags=re.S)
    body = re.sub(r"<p[^>]*>Built from <code>main</code>(?:(?!</p>).)*</p>\s*", "", body, flags=re.S)
    body = re.sub(r"<(script|style|iframe)\b.*?</\1>", "", body, flags=re.S | re.I)
    body = re.sub(r"\son\w+=(\"[^\"]*\"|'[^']*')", "", body)
    body = re.sub(r"\s(dir|data-markdown-generated-content|class|target)=\"[^\"]*\"", "", body)

    links = {}
    footer = re.search(r"<p>\s*<strong>Full changes:</strong>(.*?)</p>\s*", body, flags=re.S)
    if footer:
        compare = re.search(r'href="([^"]*/compare/[^"]*)"', footer.group(1))
        pr = re.search(r'Release PR\s*<a href="([^"]*)"[^>]*>(#\d+)</a>', footer.group(1))
        if compare:
            links["compare"] = compare.group(1)
        if pr:
            links["pr"] = (pr.group(1), pr.group(2))
        body = body[:footer.start()] + body[footer.end():]

    def heading(match):
        title = match.group(1).strip()
        kind = KINDS.get(title.lower(), "other")
        if kind != "other":
            title = html.escape(t(html.unescape(title)))
        return f'<h4 class="cl-kind {kind}">{title}</h4>'

    body = re.sub(r"<h2>(.*?)</h2>", heading, body)

    def summary(match):
        # A folded section, "Under the hood" with a count after it from the nightly notes.
        title, count = re.match(r"(.*?)\s*(\(\d+\))?$", match.group(1).strip()).groups()
        kind = KINDS.get(title.lower(), "other")
        label = html.escape(t(html.unescape(title))) if kind != "other" else title
        return f'<summary class="cl-kind {kind}">{label}{" " + count if count else ""}</summary>'

    body = re.sub(r"<summary>(.*?)</summary>", summary, body, flags=re.S)
    return body.strip(), links


def build_number(key):
    """A build's number as TestFlight shows it: 2.1795491084, or 1 for the older tags."""
    return f"{key[3]}.{key[4]}" if key[4] else str(key[3])


def version_labels(releases):
    newest = {}
    for r in releases:
        if r["platform"] not in newest or r["key"] > newest[r["platform"]]:
            newest[r["platform"]] = r["key"]
    labels = {p: f"{k[0]}.{k[1]}.{k[2]} (build {build_number(k)})" for p, k in newest.items()}
    labels["latest"] = ".".join(map(str, max(v[:3] for v in newest.values())))
    return labels


def changelog(releases, t, plugin=()):
    builds = {}
    for r in releases:
        builds.setdefault(r["key"], {})[r["platform"]] = r
    keys = sorted(builds, reverse=True)
    versions = []
    for key in keys:
        if key[:3] not in versions:
            versions.append(key[:3])

    def vid(version):
        return "v" + "-".join(map(str, version))

    filters = "".join(
        f'<input type="radio" name="cl-platform" id="cl-{css}" value="{css}"{" checked" if css == "ios" else ""}>'
        f'<label for="cl-{css}">{html.escape(t(name))}</label>'
        for _, name, css in PLATFORMS + ([("plugin", "Plugin", "plugin")] if plugin else []))
    jump = "".join(f'<li class="cl-app"><a href="#{vid(v)}">{".".join(map(str, v))}</a></li>' for v in versions)
    jump += "".join(f'<li class="cl-plugin"><a href="#plugin-{vid(r["key"])}">{".".join(map(str, r["key"]))}</a></li>'
                    for r in plugin)
    out = ['<div class="cl-layout">',
           '<aside class="cl-side">'
           f'<div class="cl-filter" role="radiogroup" aria-label="{html.escape(t("Platform"))}">{filters}</div>'
           f'<nav class="cl-jump" aria-label="{html.escape(t("Versions"))}"><p>{html.escape(t("Versions"))}</p><ul>{jump}</ul></nav>'
           '</aside>',
           '<div class="cl-list">']
    version = None
    for index, key in enumerate(keys):
        if key[:3] != version:
            if version is not None:
                out.append("</section>")
            version = key[:3]
            out.append(f'<section class="cl-version" id="{vid(version)}"><h2>Arcfin {".".join(map(str, version))}</h2>')
        entries = builds[key]
        date = max(e["date"] for e in entries.values())
        latest = f'<span class="cl-latest">{html.escape(t("Latest"))}</span>' if index == 0 else ""
        build = html.escape(t("Build {n}").replace("{n}", build_number(key)))
        out.append(f'<article class="cl-build"><header><h3>{build}{latest}</h3>'
                   f'<time datetime="{date:%Y-%m-%d}">{date.day} {date:%B %Y}</time></header>')
        # One release can cover several platforms: its notes appear once, marked for each.
        shown = {}
        for platform, name, css in PLATFORMS:
            entry = entries.get(platform)
            if entry:
                shown.setdefault(entry["link"], (entry, []))[1].append(css)
        for entry, classes in shown.values():
            css = " ".join(classes)
            notes, links = clean(entry["body"], t)
            more = [f'<a href="{html.escape(entry["link"])}">{html.escape(t("Release notes"))}</a>']
            if "compare" in links:
                more.append(f'<a href="{html.escape(links["compare"])}">{html.escape(t("Code changes"))}</a>')
            if "pr" in links:
                label = html.escape(t("Release PR {pr}").replace("{pr}", links["pr"][1]))
                more.append(f'<a href="{html.escape(links["pr"][0])}">{label}</a>')
            out.append(f'<div class="cl-notes {css}">{notes}'
                       f'<p class="cl-more">{"".join(more)}</p></div>')
        out.append("</article>")
    if version is not None:
        out.append("</section>")
    for index, r in enumerate(plugin):
        number = ".".join(map(str, r["key"]))
        notes, _ = clean(r["body"], t)
        latest = f'<span class="cl-latest">{html.escape(t("Latest"))}</span>' if index == 0 else ""
        out.append(f'<section class="cl-version cl-plugin-version" id="plugin-{vid(r["key"])}"><h2>Arcfin Sync {number}</h2>'
                   f'<article class="cl-build"><header><h3>{html.escape(t("Server plugin"))}{latest}</h3>'
                   f'<time datetime="{r["date"]:%Y-%m-%d}">{r["date"].day} {r["date"]:%B %Y}</time></header>'
                   f'<div class="cl-notes plugin">{notes}'
                   f'<p class="cl-more"><a href="{html.escape(r["link"])}">{html.escape(t("Release notes"))}</a></p></div>'
                   '</article></section>')
    out.append("</div></div>")
    return "\n".join(out)


def rewrite(path, change):
    with open(path, encoding="utf-8") as f:
        before = f.read()
    after = change(before)
    if after != before:
        with open(path, "w", encoding="utf-8") as f:
            f.write(after)
        print(f"updated {os.path.relpath(path, SITE)}")


LIVE = os.environ.get("LIVE_SITE", "https://arcfin.psmattas.com").rstrip("/")
DYNAMIC = re.compile(r'<span data-(?:version|count)="\w+">[^<]*</span>|"softwareVersion":"[^"]*"')
BLOCK = re.compile(r"<!-- releases -->.*?<!-- /releases -->", re.S)


def request(url):
    # Cloudflare turns away Python's default user agent.
    return urllib.request.Request(url, headers={"User-Agent": "arcfin-site-deploy"})


def fetch_live(path):
    with urllib.request.urlopen(request(LIVE + path), timeout=20) as response:
        return response.read().decode("utf-8")


def keep_live():
    """Copies the dynamic parts of each page from the live site into the build."""
    copied = 0
    for root, _, files in os.walk(SITE):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(root, name)
            rel = "/" + os.path.relpath(path, SITE).replace(os.sep, "/")
            try:
                live = fetch_live(rel[: -len("index.html")] if rel.endswith("index.html") else rel)
            except Exception:
                continue
            values = iter(DYNAMIC.findall(live))
            live_block = BLOCK.search(live)

            def change(text):
                text = DYNAMIC.sub(lambda m: next(values, m.group(0)), text)
                if live_block:
                    text = BLOCK.sub(lambda _: live_block.group(0), text)
                return text

            rewrite(path, change)
            copied += 1
    print(f"kept the live versions and changelog on {copied} pages")
    try:
        live = fetch_live("/" + BADGE)
        with open(os.path.join(SITE, BADGE), "w", encoding="utf-8") as f:
            f.write(live)
        print("kept the live version badge")
    except Exception as error:
        warn(f"Couldn't read the live version badge ({error}); keeping the repo's.")


BADGE = "badges/version.svg"


def badge(text):
    """A flat badge, "version | <text>", sized from the text (Verdana 11px is about 6.5px a character)."""
    label_w, value_w = 51, round(len(text) * 6.5) + 10
    width = label_w + value_w
    text = html.escape(text)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" aria-label="version: {text}">'
           f'<title>version: {text}</title>'
           '<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
           '<stop offset="1" stop-opacity=".1"/></linearGradient>'
           f'<clipPath id="r"><rect width="{width}" height="20" rx="3" fill="#fff"/></clipPath>'
           f'<g clip-path="url(#r)"><rect width="{label_w}" height="20" fill="#555"/>'
           f'<rect x="{label_w}" width="{value_w}" height="20" fill="#007ec6"/>'
           f'<rect width="{width}" height="20" fill="url(#s)"/></g>'
           '<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
           f'<text x="{label_w / 2}" y="14" fill="#010101" fill-opacity=".3">version</text>'
           f'<text x="{label_w / 2}" y="13">version</text>'
           f'<text x="{label_w + value_w / 2}" y="14" fill="#010101" fill-opacity=".3">{text}</text>'
           f'<text x="{label_w + value_w / 2}" y="13">{text}</text></g></svg>\n')
    path = os.path.join(SITE, BADGE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)


SHOT_NAME = re.compile(r"(?:iPhone|iPad|Mac|AppleTV)-\d\d-[a-z-]+\.webp")


def screenshots():
    """Unpacks each platform's newest screenshots. Any failure keeps the repo's shots."""
    feed = urllib.parse.urlsplit(FEED)
    repo = feed.path.rsplit("/releases.rss", 1)[0]
    api = f"{feed.scheme}://{feed.netloc}/api/v1/repos{repo}/releases?limit=50"
    try:
        with urllib.request.urlopen(request(api), timeout=20) as response:
            releases = json.load(response)
    except Exception as error:
        warn(f"Couldn't read the releases for screenshots ({error}); keeping the repo's.")
        return
    shots = os.path.join(SITE, "assets", "shots")
    auto = os.path.join(shots, "auto")
    for platform, _, _ in PLATFORMS:
        asset_name = f"screenshots-{platform}.zip"
        newest = None
        for release in releases:
            asset = next((a for a in release.get("assets", []) if a.get("name") == asset_name), None)
            if not asset:
                continue
            # The zip's name says the platform, so a new-style tag needn't list it in its title.
            for _, key in tag_platforms(release.get("tag_name", ""), release.get("name", "")) or [(None, None)]:
                if key is not None and (newest is None or key > newest[0]):
                    newest = (key, release["tag_name"], asset["browser_download_url"])
        if newest is None:
            continue
        url = newest[2].replace(PUBLIC, INTERNAL) if INTERNAL else newest[2]
        try:
            with urllib.request.urlopen(request(url), timeout=60) as response:
                archive = zipfile.ZipFile(io.BytesIO(response.read()))
        except Exception as error:
            warn(f"Couldn't download {asset_name} from {newest[1]} ({error}); keeping the repo's.")
            continue
        os.makedirs(auto, exist_ok=True)
        names = [n for n in archive.namelist() if SHOT_NAME.fullmatch(os.path.basename(n))]
        for name in names:
            with open(os.path.join(auto, os.path.basename(name)), "wb") as f:
                f.write(archive.read(name))
        print(f"screenshots: {len(names)} from {newest[1]}")


def main():
    screenshots()
    try:
        releases = read_feed()
        if not releases:
            raise ValueError("no platform releases in the feed")
    except Exception as error:
        warn(f"Couldn't read the release feed ({error}); keeping what's live on {LIVE}.")
        keep_live()
        return

    labels = version_labels(releases)
    newest = max(r["key"] for r in releases)
    badge(f"{newest[0]}.{newest[1]}.{newest[2]} (build {build_number(newest)})")
    try:
        plugin = read_plugin_feed()
    except Exception as error:
        warn(f"Couldn't read the plugin's release feed ({error}); the changelog leaves it out.")
        plugin = []
    for platform, label in sorted(labels.items()):
        print(f"{platform}: {label}")
    count = str(len(releases))
    print(f"releases: {count}")
    counter = re.compile(r'(<span data-count="releases">)[^<]*(</span>)')
    span = re.compile(r'(<span data-version="(\w+)">)[^<]*(</span>)')
    software = re.compile(r'("softwareVersion":")[^"]*(")')

    shown = dict(labels)
    if plugin:
        shown["plugin"] = ".".join(map(str, plugin[0]["key"]))
        print(f"plugin: {shown['plugin']}")

    def stamp(text):
        text = span.sub(lambda m: m.group(1) + shown[m.group(2)] + m.group(3) if m.group(2) in shown else m.group(0), text)
        text = counter.sub(lambda m: m.group(1) + count + m.group(2), text)
        return software.sub(lambda m: m.group(1) + labels["latest"] + m.group(2), text)

    for root, _, files in os.walk(SITE):
        for name in files:
            if name.endswith(".html"):
                rewrite(os.path.join(root, name), stamp)

    marker = re.compile(r"(<!-- releases -->).*?(<!-- /releases -->)", re.S)
    for root, _, files in os.walk(SITE):
        if os.path.basename(root) != "changelog" or "index.html" not in files:
            continue
        path = os.path.join(root, "index.html")
        with open(path, encoding="utf-8") as f:
            lang = re.search(r'<html lang="([^"]+)"', f.read()).group(1)
        notes = changelog(releases, translator(lang), plugin)
        rewrite(path, lambda text: marker.sub(lambda m: m.group(1) + "\n" + notes + "\n" + m.group(2), text))

    newest = max(r["date"] for r in releases).strftime("%Y-%m-%d")
    entry = re.compile(r"(<loc>[^<]*/changelog/</loc>\s*<lastmod>)[^<]*(</lastmod>)")
    rewrite(os.path.join(SITE, "sitemap.xml"), lambda text: entry.sub(lambda m: m.group(1) + newest + m.group(2), text))


if __name__ == "__main__":
    main()
