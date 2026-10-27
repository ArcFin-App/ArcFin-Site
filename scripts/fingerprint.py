#!/usr/bin/env python3
"""Add a content hash to every /assets/ link in the site's HTML.

Cloudflare keeps CSS, scripts and images for hours. With ?v=<hash> on each
link, a changed file gets a new URL and is fetched straight away, while
unchanged files stay cached. Runs in the deploy job, after releases.py.
"""

import hashlib
import os
import re
import sys

SITE = sys.argv[1] if len(sys.argv) > 1 else "site/arcfin.psmattas.com"
LINK = re.compile(r'((?:src|href)=")(/assets/[^"?#]+)(")')
hashes = {}


def version(path):
    if path not in hashes:
        with open(os.path.join(SITE, path.lstrip("/")), "rb") as f:
            hashes[path] = hashlib.sha256(f.read()).hexdigest()[:10]
    return hashes[path]


def stamp(match):
    path = match.group(2)
    if not os.path.isfile(os.path.join(SITE, path.lstrip("/"))):
        print(f"::warning::{path} is linked but missing")
        return match.group(0)
    return f"{match.group(1)}{path}?v={version(path)}{match.group(3)}"


for root, _, files in os.walk(SITE):
    for name in files:
        if name.endswith(".html"):
            page = os.path.join(root, name)
            with open(page, encoding="utf-8") as f:
                text = f.read()
            with open(page, "w", encoding="utf-8") as f:
                f.write(LINK.sub(stamp, text))
print(f"fingerprinted {len(hashes)} assets")
