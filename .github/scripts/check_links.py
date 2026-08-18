#!/usr/bin/env python3
"""
Checks every archive.org video link in index.html:
  1. the file still exists in the archive.org item's metadata
  2. its real length (seconds) matches the programme's durationMins
  3. a ranged GET against the canonical download URL actually streams (206/200)

Writes a JSON report to problems.json. Never modifies index.html.
"""
import json
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

INDEX_FILE = "index.html"
OUTPUT_FILE = "problems.json"
THREADS = 4  # archive.org throttles hard above ~4 concurrent requests
DURATION_TOLERANCE_SEC = 90  # allow some slack between durationMins and real length
RETRIES = 3
RETRY_BACKOFF = 5

OBJ_RE = re.compile(r'\{[^{}]*directUrl:\s*"[^"]+"[^{}]*\}', re.DOTALL)
TITLE_RE = re.compile(r'title:\s*"((?:[^"\\]|\\.)*)"')
SHOW_RE = re.compile(r'show:\s*"((?:[^"\\]|\\.)*)"')
DUR_RE = re.compile(r'durationMins:\s*([\d.]+)')
URL_RE = re.compile(r'directUrl:\s*"([^"]+)"')

session = requests.Session()
session.headers.update({"User-Agent": "nostalgic-tv-link-checker/1.0"})


def extract_entries(text):
    entries = []
    for obj in OBJ_RE.findall(text):
        title_m = TITLE_RE.search(obj)
        show_m = SHOW_RE.search(obj)
        dur_m = DUR_RE.search(obj)
        url_m = URL_RE.search(obj)
        if not (dur_m and url_m):
            continue
        entries.append({
            "title": title_m.group(1) if title_m else "",
            "show": show_m.group(1) if show_m else "",
            "durationMins": float(dur_m.group(1)),
            "url": url_m.group(1),
        })
    return entries


def parse_identifier(url):
    m = re.match(r"https://archive\.org/download/([^/]+)/(.+)", url)
    if not m:
        return None, None
    identifier, filename = m.groups()
    return identifier, urllib.parse.unquote(filename)


def fetch_metadata(identifier):
    for attempt in range(RETRIES):
        try:
            r = session.get(f"https://archive.org/metadata/{identifier}", timeout=30)
            if r.status_code == 200:
                data = r.json()
                if "error" in data:
                    # archive.org's metadata API returns this both for real takedowns
                    # and for throttling -- retry before trusting it.
                    time.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue
                return data
            time.sleep(RETRY_BACKOFF * (attempt + 1))
        except requests.RequestException:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    return None


def ranged_get_ok(url):
    for attempt in range(RETRIES):
        try:
            r = session.get(url, headers={"Range": "bytes=0-1000"}, timeout=30, stream=True)
            r.close()
            if r.status_code in (200, 206):
                return True
            if r.status_code in (500, 502, 503, 504):
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                continue
            return False
        except requests.RequestException:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    return False


def check_entry(entry, metadata_cache):
    identifier, filename = parse_identifier(entry["url"])
    problems = []
    if not identifier:
        problems.append({"type": "malformed_url", "detail": entry["url"]})
        return entry, problems

    meta = metadata_cache.get(identifier)
    if meta is None:
        problems.append({"type": "metadata_unavailable", "detail": identifier})
    else:
        files = meta.get("files", [])
        file_entry = next((f for f in files if f.get("name") == filename), None)
        if file_entry is None:
            problems.append({"type": "file_missing_from_item", "detail": filename})
        else:
            length = file_entry.get("length")
            try:
                real_seconds = float(length)
                expected_seconds = entry["durationMins"] * 60
                if abs(real_seconds - expected_seconds) > DURATION_TOLERANCE_SEC:
                    problems.append({
                        "type": "duration_mismatch",
                        "detail": f"durationMins={entry['durationMins']} "
                                  f"({expected_seconds:.0f}s) vs real {real_seconds:.0f}s",
                    })
            except (TypeError, ValueError):
                pass  # some file types don't report length; skip the duration check

    if not ranged_get_ok(entry["url"]):
        problems.append({"type": "stream_check_failed", "detail": entry["url"]})

    return entry, problems


def main():
    text = open(INDEX_FILE, encoding="utf-8").read()
    entries = extract_entries(text)
    print(f"Parsed {len(entries)} programme entries from {INDEX_FILE}")

    identifiers = {parse_identifier(e["url"])[0] for e in entries} - {None}
    print(f"Fetching metadata for {len(identifiers)} unique archive.org items "
          f"({THREADS} threads)...")

    metadata_cache = {}
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = {pool.submit(fetch_metadata, ident): ident for ident in identifiers}
        for fut in as_completed(futures):
            metadata_cache[futures[fut]] = fut.result()

    results = []
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [pool.submit(check_entry, e, metadata_cache) for e in entries]
        for fut in as_completed(futures):
            entry, problems = fut.result()
            if problems:
                results.append({**entry, "problems": problems})

    print(f"Found {len(results)} entries with problems")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
