#!/usr/bin/env python3
"""Write the newest published Arcfin release for each platform into the site.

Runs in the deploy job before rsync. Elements marked data-version="iOS",
"macOS" or "tvOS" get "X.Y.Z (build N)"; data-version="latest" gets the
highest version across platforms. If the releases can't be read, the
values already in the HTML are left alone and the deploy carries on.
"""

import json
import os
import re
import sys
import urllib.request

API = os.environ.get("GITEA_API", "").rstrip("/")
REPO = os.environ.get("APP_REPO", "ArcFin/ArcFin")
SITE = sys.argv[1] if len(sys.argv) > 1 else "site/arcfin.psmattas.com"
TAG = re.compile(r"^(iOS|macOS|tvOS)-(\d+)\.(\d+)\.(\d+)-build-(\d+)$")


def warn(message):
    print(f"::warning::{message}")


def releases():
    found = []
    for page in range(1, 6):
        url = f"{API}/repos/{REPO}/releases?draft=false&limit=50&page={page}"
        with urllib.request.urlopen(url, timeout=20) as response:
            batch = json.load(response)
        found += batch
        if len(batch) < 50:
            break
    return found


def newest_per_platform(items):
    newest = {}
    for release in items:
        match = TAG.match(release.get("tag_name", ""))
        if not match or release.get("draft"):
            continue
        platform, *numbers = match.groups()
        key = tuple(int(n) for n in numbers)
        if platform not in newest or key > newest[platform]:
            newest[platform] = key
    return newest


def main():
    if not API:
        warn("GITEA_API isn't set, so the site keeps the versions already in its HTML.")
        return
    try:
        newest = newest_per_platform(releases())
    except Exception as error:
        warn(f"Couldn't read releases ({error}), so the site keeps the versions already in its HTML.")
        return
    if not newest:
        warn("No published platform releases found, so the site keeps the versions already in its HTML.")
        return

    labels = {p: f"{a}.{b}.{c} (build {n})" for p, (a, b, c, n) in newest.items()}
    latest = max(v[:3] for v in newest.values())
    labels["latest"] = ".".join(map(str, latest))
    for platform, label in sorted(labels.items()):
        print(f"{platform}: {label}")

    pattern = re.compile(r'(<span data-version="(\w+)">)[^<]*(</span>)')
    software = re.compile(r'("softwareVersion":")[^"]*(")')
    for root, _, files in os.walk(SITE):
        for name in files:
            if not name.endswith(".html"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            stamped = pattern.sub(
                lambda m: m.group(1) + labels[m.group(2)] + m.group(3) if m.group(2) in labels else m.group(0),
                html)
            stamped = software.sub(lambda m: m.group(1) + labels["latest"] + m.group(2), stamped)
            if stamped != html:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(stamped)
                print(f"stamped {os.path.relpath(path, SITE)}")


if __name__ == "__main__":
    main()
