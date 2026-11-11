#!/usr/bin/env python3
"""Build the translated copies of the site from the English pages.

English is the source. Each language has i18n/<lang>.json, which maps an
English piece of text (a heading, paragraph, list item, button label or
attribute) to its translation. Inline markup such as <strong> or <a>
stays in the translation.

  python3 scripts/i18n.py build    write /<lang>/ pages, the language menu and hreflang links
  python3 scripts/i18n.py check    list English text that a language hasn't translated yet

Anything without a translation stays in English, so a page never breaks
because a string is missing.
"""

import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser

ROOT = os.path.join(os.path.dirname(__file__), "..")
SITE = os.path.join(ROOT, "site", "arcfin.psmattas.com")
I18N = os.path.join(ROOT, "i18n")
ORIGIN = "https://arcfin.psmattas.com"

LANGUAGES = [
    # code used in <html lang>, URL folder, name in that language
    ("en", "", "English"),
    ("de", "de", "Deutsch"),
    ("es", "es", "Español"),
    ("fr", "fr", "Français"),
    ("it", "it", "Italiano"),
    ("nl", "nl", "Nederlands"),
    ("pt-BR", "pt-br", "Português (Brasil)"),
    ("ru", "ru", "Русский"),
    ("ja", "ja", "日本語"),
    ("ko", "ko", "한국어"),
    ("zh-Hans", "zh-hans", "简体中文"),
]
# Pages that exist in every language. The legal pages stay English only,
# because the English text is the binding one.
TRANSLATED = ["", "roadmap", "screenshots", "support", "contribute", "changelog", "404"]
# Pages search engines shouldn't list.
UNLISTED = {"404"}
# Translated pages whose main text stays English (the release notes), so
# search engines are pointed at the English page instead of near-copies.
ENGLISH_CANONICAL = {"changelog"}
ENGLISH_ONLY = ["privacy", "terms", "data-protection"]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"address", "article", "aside", "blockquote", "details", "dialog", "div", "dl", "dt", "dd", "fieldset",
         "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
         "main", "nav", "ol", "p", "pre", "section", "summary", "table", "tbody", "td", "th", "thead", "tr",
         "ul", "head", "body", "html", "button"}
# Elements that hold one piece of text even when it's split across inline
# children, e.g. <p>Use <strong>Settings</strong> to …</p>.
LEAFY = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "summary", "td", "th", "dt", "dd", "figcaption",
         "label", "button", "title", "a", "span", "strong", "em", "small", "time"}
SKIP = {"releases", "languages", "hreflang"}

NOTE = 'Translated automatically from English. <a href="/contribute/#translate">Help improve this translation</a>.'
RELEASES_NOTE = "Release notes are written in English."
# Text that isn't on the English pages but is used by translated pages,
# scripts/releases.py (changelog labels) and the language menu.
EXTRA = ["Language", NOTE, RELEASES_NOTE, "Build {n}", "Latest", "Release notes", "Code changes",
         "Release PR {pr}", "Versions", "Platform", "iPhone & iPad", "New", "Improved", "Fixed",
         "Removed", "Under the hood"]
OPAQUE = {"script", "style", "svg"}
ATTRS = {"alt", "aria-label", "title", "placeholder"}
META = {"description", "og:title", "og:description", "twitter:title", "twitter:description"}


class Node:
    def __init__(self, kind, tag=None, attrs=None, text=""):
        self.kind, self.tag, self.attrs, self.text = kind, tag, attrs or [], text
        self.children = []

    def attr(self, name):
        for k, v in self.attrs:
            if k == name:
                return v
        return None

    def set_attr(self, name, value):
        for i, (k, _) in enumerate(self.attrs):
            if k == name:
                self.attrs[i] = (k, value)
                return
        self.attrs.append((name, value))


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_decl(self, decl):
        self.stack[-1].children.append(Node("raw", text=f"<!{decl}>"))

    def handle_starttag(self, tag, attrs):
        node = Node("el", tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node("el", tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(Node("text", text=data))

    def handle_entityref(self, name):
        self.stack[-1].children.append(Node("text", text=f"&{name};"))

    def handle_charref(self, name):
        self.stack[-1].children.append(Node("text", text=f"&#{name};"))

    def handle_comment(self, data):
        self.stack[-1].children.append(Node("comment", text=data))


def parse(text):
    parser = Parser()
    parser.feed(text)
    parser.close()
    return parser.root


def start_tag(node):
    parts = [node.tag]
    for k, v in node.attrs:
        parts.append(k if v is None else f'{k}="{html.escape(v, quote=True)}"')
    return "<" + " ".join(parts) + ">"


def serialize(node):
    if node.kind == "text" or node.kind == "raw":
        return node.text
    if node.kind == "comment":
        return f"<!--{node.text}-->"
    inner = "".join(serialize(c) for c in node.children)
    if node.kind == "root":
        return inner
    if node.tag in VOID:
        return start_tag(node)
    return f"{start_tag(node)}{inner}</{node.tag}>"


def has_text(node):
    if node.kind == "text":
        return node.text.strip() != ""
    if node.kind == "el" and node.tag in OPAQUE:
        return False
    return any(has_text(c) for c in node.children)


def has_direct_text(node):
    return any(c.kind == "text" and c.text.strip() for c in node.children)


def has_block(node):
    return any(c.kind == "el" and (c.tag in BLOCK or has_block(c)) for c in node.children)


def normalize(text):
    text = re.sub(r'(<span data-(?:version|count)="\w+">)[^<]*(</span>)', r"\1\2", text)
    return re.sub(r"\s+", " ", text).strip()


def units(node, skip=None):
    """Yields (element, first, last) for each piece of translatable text.

    first..last are the child indexes that hold the text; leading and
    trailing children without text (icons, dots) stay out of it.
    """
    skipping = False
    for child in node.children:
        if child.kind == "comment":
            name = child.text.strip()
            if name in SKIP:
                skipping = True
            elif name.lstrip("/") in SKIP:
                skipping = False
            continue
        if skipping or child.kind != "el" or child.tag in OPAQUE:
            continue
        if has_text(child) and not has_block(child) and (child.tag in LEAFY or has_direct_text(child)):
            kids = child.children
            idx = [i for i, k in enumerate(kids) if has_text(k)]
            yield child, idx[0], idx[-1]
        else:
            yield from units(child)


def key_of(element, first, last):
    return normalize("".join(serialize(c) for c in element.children[first:last + 1]))


def attr_nodes(node, skipping=None):
    if skipping is None:
        skipping = [False]
    if node.kind == "comment":
        name = node.text.strip()
        if name in SKIP:
            skipping[0] = True
        elif name.lstrip("/") in SKIP:
            skipping[0] = False
    if node.kind == "el" and not skipping[0]:
        if node.tag == "meta" and (node.attr("name") in META or node.attr("property") in META):
            yield node, "content"
        for name in ATTRS:
            if node.attr(name):
                yield node, name
    for child in node.children:
        if not (child.kind == "el" and child.tag == "svg"):
            yield from attr_nodes(child, skipping)


def page_path(slug):
    return f"{slug}/index.html" if slug else "index.html"


def url(folder, slug):
    parts = [p for p in (folder, slug) if p]
    return "/" + "/".join(parts) + "/" if parts else "/"


def load(code):
    path = os.path.join(I18N, f"{code}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {normalize(k): v for k, v in json.load(f).items() if v}


def localize_href(href, folder):
    if not folder or not href.startswith("/") or href.startswith("//") or href.startswith("/assets/"):
        return href
    path, sep, frag = href.partition("#")
    slug = path.strip("/")
    if slug in TRANSLATED:
        return url(folder, slug) + (sep + frag if sep else "")
    return href


def language_menu(current_code, slug, strings):
    available = slug in TRANSLATED
    items = []
    for code, folder, name in LANGUAGES:
        href = url(folder, slug if available else "")
        mark = ' aria-current="true"' if code == current_code else ""
        items.append(f'<a href="{href}" hreflang="{code}" lang="{code}" data-lang="{code}"{mark}>{name}</a>')
    note = "" if available else '<p class="lang-note">This page is only available in English.</p>'
    label = html.escape(strings.get("Language", "Language"), quote=True)
    return (f'<details class="lang-menu"><summary aria-label="{label}">'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/>'
            '<path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg></summary>'
            f'<div class="lang-sheet" role="list">{"".join(items)}{note}</div></details>')


def hreflang(slug):
    if slug not in TRANSLATED or slug in UNLISTED or slug in ENGLISH_CANONICAL:
        return ""
    links = [f'<link rel="alternate" hreflang="{code}" href="{ORIGIN}{url(folder, slug)}">' for code, folder, _ in LANGUAGES]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}{url("", slug)}">')
    return "\n  ".join(links)


def replace_between(text, name, content, anchor):
    block = f"<!-- {name} -->{content}<!-- /{name} -->"
    pattern = re.compile(rf"<!-- {name} -->.*?<!-- /{name} -->", re.S)
    if pattern.search(text):
        return pattern.sub(lambda _: block, text)
    return text.replace(anchor, block + anchor, 1)


def faq_schema(text):
    """FAQPage structured data built from the page's own questions and answers."""
    items = []
    for question, answer in re.findall(r'<details><summary>(.*?)</summary><div class="answer">(.*?)</div></details>', text, re.S):
        plain = lambda t: html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t))).strip()
        items.append({"@type": "Question", "name": plain(question),
                      "acceptedAnswer": {"@type": "Answer", "text": plain(answer)}})
    if not items:
        return ""
    data = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": items}, ensure_ascii=False)
    data = data.replace("</", "<\\/")
    return f'\n  <script type="application/ld+json">{data}</script>\n  '


def decorate(text, code, slug, strings=None):
    text = replace_between(text, "languages", language_menu(code, slug, strings or {}), '<details class="theme-menu">')
    links = hreflang(slug)
    text = replace_between(text, "hreflang", f"\n  {links}\n  " if links else "", "</head>")
    return replace_between(text, "faq-schema", faq_schema(text), "</head>")


def translate_page(source, code, folder, strings, missing, slug):
    tree = parse(source)
    for element, first, last in list(units(tree)):
        key = key_of(element, first, last)
        if key not in strings:
            missing.add(key)
            continue
        value = strings[key]
        versions = re.findall(r'<span data-((?:version|count)="\w+)">([^<]*)</span>',
                              "".join(serialize(c) for c in element.children[first:last + 1]))
        for name, current in versions:
            value = value.replace(f'<span data-{name}"></span>', f'<span data-{name}">{current}</span>')
        element.children[first:last + 1] = [Node("raw", text=value)]
    # Parse again so links inside translated text get localized too.
    tree = parse(serialize(tree))
    for node, name in attr_nodes(tree):
        key = normalize(node.attr(name))
        if key in strings:
            node.set_attr(name, html.unescape(strings[key]))
        else:
            missing.add(key)

    def walk(node):
        if node.kind == "el":
            if node.tag == "html":
                node.set_attr("lang", code)
            if node.tag == "a" and node.attr("href"):
                node.set_attr("href", localize_href(node.attr("href"), folder))
            if node.tag == "link" and node.attr("rel") == "canonical" and slug not in ENGLISH_CANONICAL:
                node.set_attr("href", ORIGIN + localize_href(node.attr("href")[len(ORIGIN):], folder))
            if node.tag == "meta" and node.attr("property") == "og:url":
                node.set_attr("content", ORIGIN + localize_href(node.attr("content")[len(ORIGIN):], folder))
        for child in node.children:
            walk(child)

    walk(tree)
    out = serialize(tree)
    note = strings.get(NOTE, NOTE).replace('href="/contribute/', f'href="/{folder}/contribute/')
    out = out.replace("</main>", f'<p class="mt-note wrap">{note}</p>\n</main>', 1)
    if slug == "changelog":
        out = out.replace("<!-- releases -->", f'<p class="cl-lang-note">{strings.get(RELEASES_NOTE, RELEASES_NOTE)}</p>\n<!-- releases -->', 1)
    return out


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def source_keys():
    keys = []
    for slug in TRANSLATED:
        tree = parse(read(os.path.join(SITE, page_path(slug))))
        for element, first, last in units(tree):
            keys.append(key_of(element, first, last))
        for node, name in attr_nodes(tree):
            keys.append(normalize(node.attr(name)))
    keys.extend(EXTRA)
    return list(dict.fromkeys(k for k in keys if re.search(r"[A-Za-z]", k)))


def last_changed(*paths):
    """Date of the newest commit touching any of the paths, or None outside git."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", *paths], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None


def sitemap():
    entries = []
    for slug in TRANSLATED + ENGLISH_ONLY:
        if slug in UNLISTED:
            continue
        listed = slug in TRANSLATED and slug not in ENGLISH_CANONICAL
        variants = LANGUAGES if listed else LANGUAGES[:1]
        alternates = "".join(
            f'\n    <xhtml:link rel="alternate" hreflang="{code}" href="{ORIGIN}{url(folder, slug)}"/>'
            for code, folder, _ in variants) if len(variants) > 1 else ""
        source = os.path.join(SITE, page_path(slug))
        for code, folder, _ in variants:
            sources = [source] + ([os.path.join(I18N, f"{code}.json")] if folder else [])
            date = last_changed(*sources)
            lastmod = f"\n    <lastmod>{date}</lastmod>" if date else ""
            entries.append(f"  <url>\n    <loc>{ORIGIN}{url(folder, slug)}</loc>{lastmod}{alternates}\n  </url>")
    write(os.path.join(SITE, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
          + "\n".join(entries) + "\n</urlset>\n")
    print(f"sitemap: {len(entries)} pages")


def build():
    for slug in TRANSLATED + ENGLISH_ONLY:
        path = os.path.join(SITE, page_path(slug))
        write(path, decorate(read(path), "en", slug))
    for code, folder, _ in LANGUAGES[1:]:
        strings = load(code)
        missing = set()
        for slug in TRANSLATED:
            source = read(os.path.join(SITE, page_path(slug)))
            out = translate_page(source, code, folder, strings, missing, slug)
            write(os.path.join(SITE, folder, page_path(slug)), decorate(out, code, slug, strings))
        wanted = set(source_keys())
        print(f"{code}: {len(wanted & set(strings))}/{len(wanted)} translated")
    sitemap()


def check():
    wanted = source_keys()
    status = 0
    for code, _, _ in LANGUAGES[1:]:
        strings = load(code)
        gaps = [k for k in wanted if k not in strings]
        print(f"{code}: {len(wanted) - len(gaps)}/{len(wanted)} translated")
        for k in gaps:
            print(f"  missing: {k[:100]}")
        status |= bool(gaps)
    return status


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "build"
    if command == "build":
        build()
    elif command == "check":
        sys.exit(check())
    elif command == "keys":
        print(json.dumps(source_keys(), ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)
