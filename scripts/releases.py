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


def clean(body):
    if INTERNAL:
        body = body.replace(INTERNAL, PUBLIC)
    # Badges and the TestFlight review note are for the release page, not the site.
    body = re.sub(r"<p[^>]*>(?:(?!</p>).)*?(?:testflight-badge|img\.shields\.io)(?:(?!</p>).)*</p>\s*", "", body, flags=re.S)
    body = re.sub(r"<blockquote>(?:(?!</blockquote>).)*When will I get this build\?.*?</blockquote>\s*", "", body, flags=re.S)
    body = re.sub(r"<(script|style|iframe)\b.*?</\1>", "", body, flags=re.S | re.I)
    body = re.sub(r"\son\w+=(\"[^\"]*\"|'[^']*')", "", body)
    body = re.sub(r"\s(dir|data-markdown-generated-content|class)=\"[^\"]*\"", "", body)
    body = re.sub(r"<h2>", "<h4>", body).replace("</h2>", "</h4>")
    return body.strip()


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
    filters = "".join(
        f'<input type="radio" name="cl-platform" id="cl-{css}" value="{css}"{" checked" if css == "ios" else ""}>'
        f'<label for="cl-{css}">{html.escape(name)}</label>'
        for _, name, css in PLATFORMS)
    out = [f'<div class="cl-filter" role="radiogroup" aria-label="Platform">{filters}</div>']
    version = None
    for key in sorted(builds, reverse=True):
        if key[:3] != version:
            if version is not None:
                out.append("</section>")
            version = key[:3]
            out.append(f'<section class="cl-version"><h2>Arcfin {".".join(map(str, version))}</h2>')
        entries = builds[key]
        date = max(e["date"] for e in entries.values())
        out.append(f'<article class="cl-build"><header><h3>Build {key[3]}</h3>'
                   f'<time datetime="{date:%Y-%m-%d}">{date.day} {date:%B %Y}</time></header>')
        for platform, name, css in PLATFORMS:
            entry = entries.get(platform)
            if not entry:
                continue
            out.append(f'<div class="cl-notes {css}"><p class="cl-platform">{html.escape(name)}</p>'
                       f'{clean(entry["body"])}'
                       f'<p class="cl-more"><a href="{html.escape(entry["link"])}">Release page</a></p></div>')
        out.append("</article>")
    if version is not None:
        out.append("</section>")
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
