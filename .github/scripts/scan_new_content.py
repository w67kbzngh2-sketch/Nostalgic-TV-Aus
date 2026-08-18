#!/usr/bin/env python3
"""
Runs a handful of curated archive.org searches, one per channel "vibe", and
reports items that (a) aren't already used anywhere in index.html and
(b) haven't been reported by a previous run (tracked in seen-content.json).

This is a DISCOVERY tool only -- it never adds anything to index.html and it
does not vet codec/bitrate/dub language (that still needs a human, per the
project's own notes on archive.org's dodgy metadata). It just surfaces
candidates worth a manual look.
"""
import json
import re
import time

import requests

INDEX_FILE = "index.html"
SEEN_FILE = ".github/scripts/seen-content.json"
OUTPUT_FILE = "candidates.json"
RESULTS_PER_QUERY = 15
NOISE_PREFIX = re.compile(r"^(youtube-|twitter-|tiktok-|turner_video_)")

# Each query loosely maps to one channel's vibe -- see memory notes on what
# actually returns usable results on archive.org (TV broadcast recordings
# and cult/older titles beat searching big-studio titles by name).
QUERIES = [
    ("CH7 SBS World Movies -- cult & arthouse",
     'collection:(feature_films) AND (subject:"cult film" OR subject:"surreal")'),
    ("CH7 SBS World Movies -- kung-fu / martial arts",
     'subject:"martial arts" AND collection:(feature_films)'),
    ("CH9 MTV -- music broadcast captures",
     'title:"MTV" AND mediatype:(movies)'),
    ("CH10 The Thinking Box -- documentary",
     'collection:(feature_films) AND subject:"documentary"'),
    ("CH11 The Late Movie -- horror & thriller",
     'subject:"horror" AND collection:(feature_films)'),
    ("CH13 Jumbo Video -- 80s/90s genre films",
     "collection:(feature_films) AND year:[1978 TO 1995]"),
    ("CH14 Trash TV -- talk shows",
     'collection:(television) AND (title:"Springer" OR title:"Oprah" OR subject:"talk show")'),
    ("CH15 Action Hour -- action & adventure",
     'subject:"action" AND collection:(feature_films)'),
]

session = requests.Session()
session.headers.update({"User-Agent": "nostalgic-tv-content-scan/1.0"})


def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f).get("seen_identifiers", []))
    except FileNotFoundError:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"seen_identifiers": sorted(seen)}, f, indent=2)


def used_identifiers():
    text = open(INDEX_FILE, encoding="utf-8").read()
    return set(re.findall(r"archive\.org/download/([^/\"]+)/", text))


def search(query):
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "downloads", "year"],
        "sort[]": "downloads desc",
        "rows": RESULTS_PER_QUERY,
        "output": "json",
    }
    for attempt in range(3):
        try:
            r = session.get("https://archive.org/advancedsearch.php", params=params, timeout=30)
            if r.status_code == 200:
                return r.json().get("response", {}).get("docs", [])
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    return []


def main():
    already_used = used_identifiers()
    seen = load_seen()
    print(f"{len(already_used)} identifiers already in index.html, "
          f"{len(seen)} previously reported")

    candidates = []
    for label, query in QUERIES:
        docs = search(query)
        for doc in docs:
            ident = doc.get("identifier", "")
            if not ident or NOISE_PREFIX.match(ident):
                continue
            if ident in already_used or ident in seen:
                continue
            candidates.append({
                "category": label,
                "identifier": ident,
                "title": doc.get("title", ""),
                "year": doc.get("year", ""),
                "downloads": doc.get("downloads", 0),
                "url": f"https://archive.org/details/{ident}",
            })
        time.sleep(2)  # be polite between queries

    print(f"Found {len(candidates)} new candidates")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2)

    seen.update(c["identifier"] for c in candidates)
    save_seen(seen)


if __name__ == "__main__":
    main()
