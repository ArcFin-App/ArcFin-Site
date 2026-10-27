#!/usr/bin/env python3
"""Fill the site with the app's published releases before it's deployed.

Reads the app repository's release feed once, then:
- writes the newest version for each platform into every element marked
  data-version="iOS", "macOS", "tvOS" or "latest";
- writes the release notes into changelog/index.html, between the
  <!-- releases --> and <!-- /releases --> markers.

If the feed can't be read, the HTML already in the repo is left as is and
the deploy carries on.
"""

import email.utils
import html
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

SITE = sys.argv[1] if len(sys.argv) > 1 else "site/arcfin.psmattas.com"
FEED = os.environ.get("RELEASES_FEED", "https://git.psmattas.com/ArcFin/ArcFin/releases.rss")
# The runner reads the feed from inside the network, where Gitea writes
# some links with its internal address. They're rewritten to the public one.
INTERNAL = os.environ.get("GITEA_INTERNAL_URL", "").rstrip("/")
PUBLIC = "https://git.psmattas.com"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
TAG = re.compile(r"/releases/tag/(iOS|macOS|tvOS)-(\d+)\.(\d+)\.(\d+)-build-(\d+)$")
PLATFORMS = [("iOS", "iPhone & iPad", "ios"), ("macOS", "Mac", "mac"), ("tvOS", "Apple TV", "tv")]


def warn(message):
    print(f"::warning::{message}")


def read_feed():
    with urllib.request.urlopen(FEED, timeout=20) as response:
        root = ET.fromstring(response.read())
    releases = []
    for item in root.iter("item"):
        match = TAG.search(item.findtext("link", ""))
        if not match:
            continue
        platform, *numbers = match.groups()
        releases.append({
            "platform": platform,
            "key": tuple(int(n) for n in numbers),
            "link": item.findtext("link"),
            "date": email.utils.parsedate_to_datetime(item.findtext("pubDate")),
            "body": item.findtext(CONTENT) or "",
        })
    return releases


KINDS = {"new": "new", "improved": "improved", "fixed": "fixed", "removed": "removed",
         "under the hood": "hood", "changes": "none"}


def clean(body):
    """Returns the notes as HTML, plus the compare and release PR links from the footer line."""
    if INTERNAL:
        body = body.replace(INTERNAL, PUBLIC)
    # Badges and the TestFlight review note are for the release page, not the site.
    body = re.sub(r"<p[^>]*>(?:(?!</p>).)*?(?:testflight-badge|img\.shields\.io)(?:(?!</p>).)*</p>\s*", "", body, flags=re.S)
    body = re.sub(r"<blockquote>(?:(?!</blockquote>).)*When will I get this build\?.*?</blockquote>\s*", "", body, flags=re.S)
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
        return f'<h4 class="cl-kind {kind}">{title}</h4>'

    body = re.sub(r"<h2>(.*?)</h2>", heading, body)
    return body.strip(), links


def version_labels(releases):
    newest = {}
    for r in releases:
        if r["platform"] not in newest or r["key"] > newest[r["platform"]]:
            newest[r["platform"]] = r["key"]
    labels = {p: f"{a}.{b}.{c} (build {n})" for p, (a, b, c, n) in newest.items()}
    labels["latest"] = ".".join(map(str, max(v[:3] for v in newest.values())))
    return labels


def changelog(releases):
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
        f'<label for="cl-{css}">{html.escape(name)}</label>'
        for _, name, css in PLATFORMS)
    jump = "".join(f'<li><a href="#{vid(v)}">{".".join(map(str, v))}</a></li>' for v in versions)
    out = ['<div class="cl-layout">',
           '<aside class="cl-side">'
           f'<div class="cl-filter" role="radiogroup" aria-label="Platform">{filters}</div>'
           f'<nav class="cl-jump" aria-label="Versions"><p>Versions</p><ul>{jump}</ul></nav>'
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
        latest = '<span class="cl-latest">Latest</span>' if index == 0 else ""
        out.append(f'<article class="cl-build"><header><h3>Build {key[3]}{latest}</h3>'
                   f'<time datetime="{date:%Y-%m-%d}">{date.day} {date:%B %Y}</time></header>')
        for platform, name, css in PLATFORMS:
            entry = entries.get(platform)
            if not entry:
                continue
            notes, links = clean(entry["body"])
            more = [f'<a href="{html.escape(entry["link"])}">Release notes</a>']
            if "compare" in links:
                more.append(f'<a href="{html.escape(links["compare"])}">Code changes</a>')
            if "pr" in links:
                more.append(f'<a href="{html.escape(links["pr"][0])}">Release PR {links["pr"][1]}</a>')
            out.append(f'<div class="cl-notes {css}">{notes}'
                       f'<p class="cl-more">{"".join(more)}</p></div>')
        out.append("</article>")
    if version is not None:
        out.append("</section>")
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


def main():
    try:
        releases = read_feed()
    except Exception as error:
        warn(f"Couldn't read the release feed ({error}); the site keeps the versions and changelog already in the repo.")
        return
    if not releases:
        warn("The release feed has no platform releases; the site keeps what's already in the repo.")
        return

    labels = version_labels(releases)
    for platform, label in sorted(labels.items()):
        print(f"{platform}: {label}")
    span = re.compile(r'(<span data-version="(\w+)">)[^<]*(</span>)')
    software = re.compile(r'("softwareVersion":")[^"]*(")')

    def stamp(text):
        text = span.sub(lambda m: m.group(1) + labels[m.group(2)] + m.group(3) if m.group(2) in labels else m.group(0), text)
        return software.sub(lambda m: m.group(1) + labels["latest"] + m.group(2), text)

    for root, _, files in os.walk(SITE):
        for name in files:
            if name.endswith(".html"):
                rewrite(os.path.join(root, name), stamp)

    notes = changelog(releases)
    marker = re.compile(r"(<!-- releases -->).*?(<!-- /releases -->)", re.S)
    rewrite(os.path.join(SITE, "changelog", "index.html"),
            lambda text: marker.sub(lambda m: m.group(1) + "\n" + notes + "\n" + m.group(2), text))


if __name__ == "__main__":
    main()
