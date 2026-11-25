#!/usr/bin/env python3
"""Publishes the legal pages and the app's licences as JSON, for the app to show.

  python3 scripts/legal.py site/arcfin.psmattas.com

Writes, under legal/v1/:
- index.json: the Privacy Policy, Terms of Use and Data Protection notice, each as Markdown
  made from the English page's <article class="prose">, with its effective date. The pages
  are the binding text and the only source, so the app never carries a copy of its own.
  Also the screen's Data Sources credits, from scripts/legal-sources.json, in every
  language the app has (keyed by the app's language codes, "en" first), each with the
  platforms it shows on when it isn't all of them.
- licenses/<version>-<build>.json for each app release that has a licenses.json attached
  (the nightly makes it from that build's pinned packages), and licenses/latest.json, the
  newest. The app asks for its own version and build and falls back to latest.json.
  If the releases can't be read, the repo's latest.json stays.

The v1 paths are a contract with every shipped build: add fields, never rename or remove.
"""

import html
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

ORIGIN = "https://arcfin.psmattas.com"
SCHEMA = 1
PAGES = [("privacy", "Privacy Policy"), ("terms", "Terms of Use"), ("data-protection", "Data Protection")]
# The same feed the Deploy workflow gives releases.py, turned into its API address.
FEED = os.environ.get("RELEASES_FEED", "https://git.psmattas.com/ArcFin/ArcFin-Apple/releases.rss")
RELEASES = FEED.removesuffix("/releases.rss").replace("://", "\0", 1).replace("/", "/api/v1/repos/", 1).replace("\0", "://") + "/releases"
# Inside the network Gitea writes some links with its internal address.
INTERNAL = os.environ.get("GITEA_INTERNAL_URL", "").rstrip("/")
PUBLIC = "https://git.psmattas.com"
TAG = re.compile(r"^v(\d+\.\d+\.\d+)-build-(\d+(?:\.\d+)?)$")


def escape(text):
    return re.sub(r"([\\`*_\[\]<>#|])", r"\\\1", text)


class Markdown(HTMLParser):
    """The prose of a legal page as Markdown: headings, paragraphs, lists, tables, bold,
    code and links. Anything else keeps only its text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.blocks = []
        self.inline = None
        self.links = []
        self.table = None
        self.row = None
        self.kind = None

    def start_inline(self, kind):
        self.inline, self.kind = [], kind

    def end_inline(self):
        text = re.sub(r"[ \t\r\n]+", " ", "".join(self.inline or [])).strip()
        kind, self.inline, self.kind = self.kind, None, None
        return kind, text

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and attrs.get("class") == "prose":
            self.depth = 1
            return
        if not self.depth:
            return
        if tag == "article":
            self.depth += 1
        elif tag in ("h2", "h3", "p", "li") and self.inline is None:
            self.start_inline(tag)
        elif tag == "div" and "summary-box" in (attrs.get("class") or "") and self.inline is None:
            self.start_inline("quote")
        elif tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.start_inline(tag)
        elif self.inline is not None:
            if tag == "strong" or tag == "b":
                self.inline.append("**")
            elif tag == "em" or tag == "i":
                self.inline.append("*")
            elif tag == "code":
                self.inline.append("`")
            elif tag == "br":
                self.inline.append(" ")
            elif tag == "a":
                href = attrs.get("href") or ""
                if href.startswith("/"):
                    href = ORIGIN + href
                self.links.append(href)
                self.inline.append("[")

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "article":
            self.depth -= 1
            return
        if self.inline is not None:
            if tag in ("strong", "b"):
                self.inline.append("**")
                return
            if tag in ("em", "i"):
                self.inline.append("*")
                return
            if tag == "code":
                self.inline.append("`")
                return
            if tag == "a":
                href = self.links.pop() if self.links else ""
                self.inline.append(f"]({href})" if href.startswith(("http", "mailto:")) else "]()")
                return
        if tag in ("td", "th") and self.kind == tag:
            self.row.append(self.end_inline()[1].replace("|", "\\|"))
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            rows, self.table = self.table, None
            if rows:
                width = max(len(r) for r in rows)
                lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
                lines.insert(1, "|" + " --- |" * width)
                self.blocks.append("\n".join(lines))
        elif (tag == self.kind) or (tag == "div" and self.kind == "quote"):
            kind, text = self.end_inline()
            if not text:
                return
            text = text.replace("[]()", "")
            self.blocks.append({"h2": "## ", "h3": "### ", "li": "- ", "quote": "> "}.get(kind, "") + text)

    def handle_data(self, data):
        if self.depth and self.inline is not None:
            self.inline.append(escape(data))

    def markdown(self):
        out = []
        for block in self.blocks:
            # List items of one list sit together; everything else is its own paragraph.
            if out and block.startswith("- ") and out[-1].startswith("- "):
                out[-1] += "\n" + block
            else:
                out.append(block)
        return "\n\n".join(out).strip() + "\n"


def page(site, slug, title):
    with open(os.path.join(site, slug, "index.html"), encoding="utf-8") as f:
        source = f.read()
    parser = Markdown()
    parser.feed(source)
    effective = re.search(r"Effective ([0-9]{1,2} [A-Z][a-z]+ [0-9]{4})", source)
    if not effective:
        sys.exit(f"{slug}: no effective date")
    text = parser.markdown()
    if len(text) < 500:
        sys.exit(f"{slug}: the page's prose came out nearly empty")
    return {"id": slug, "title": title, "effective": effective.group(1), "url": f"{ORIGIN}/{slug}/",
            "format": "markdown", "text": text}


def request(url):
    return urllib.request.Request(url, headers={"User-Agent": "arcfin-site-deploy"})


def licences(folder):
    """Each release's licenses.json under its version and build; the newest also as latest.json."""
    published = []
    try:
        page_number = 1
        while True:
            with urllib.request.urlopen(request(f"{RELEASES}?limit=50&page={page_number}"), timeout=30) as response:
                batch = json.load(response)
            if not batch:
                break
            for release in batch:
                match = TAG.match(release.get("tag_name", ""))
                asset = next((a for a in release.get("assets", []) if a.get("name") == "licenses.json"), None)
                if match and asset:
                    published.append((match.group(1), match.group(2), asset["browser_download_url"]))
            page_number += 1
    except Exception as error:
        print(f"::warning::Couldn't read the app's releases ({error}); keeping the repo's licences.")
        return

    def order(item):
        return tuple(int(p) for p in item[0].split(".")) + tuple(int(p) for p in item[1].split("."))

    newest = None
    for version, build, url in sorted(published, key=order):
        try:
            if INTERNAL:
                url = url.replace(PUBLIC, INTERNAL)
            with urllib.request.urlopen(request(url), timeout=60) as response:
                data = json.load(response)
            if data.get("schema") != SCHEMA or not data.get("components"):
                raise ValueError("not a v1 licence file")
        except Exception as error:
            print(f"::warning::Skipping the licences of {version} ({build}): {error}")
            continue
        write(os.path.join(folder, f"{version}-{build}.json"), data)
        newest = data
    if newest:
        write(os.path.join(folder, "latest.json"), newest)
    print(f"licences: {len(published)} builds")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    site = args[0]
    out = os.path.join(site, "legal", "v1")
    documents = [page(site, slug, title) for slug, title in PAGES]
    with open(os.path.join(os.path.dirname(__file__), "legal-sources.json"), encoding="utf-8") as f:
        sources = json.load(f)
    write(os.path.join(out, "index.json"), {"schema": SCHEMA, "documents": documents, "sources": sources})
    print("legal: " + ", ".join(f"{d['title']} ({d['effective']})" for d in documents))
    if "--no-licences" not in sys.argv:
        licences(os.path.join(out, "licenses"))


if __name__ == "__main__":
    main()
