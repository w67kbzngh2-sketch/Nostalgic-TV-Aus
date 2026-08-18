#!/usr/bin/env python3
"""Turns problems.json / candidates.json into a GitHub issue (or a comment
on the existing open one), via the gh CLI."""
import json
import subprocess

LABEL = "content-check"


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def format_problems(problems):
    lines = ["## Broken / mismatched links\n"]
    for p in problems:
        lines.append(f"- **{p.get('show') or p.get('title')}** — {p['title']}")
        for issue in p["problems"]:
            lines.append(f"  - `{issue['type']}`: {issue['detail']}")
        lines.append(f"  - {p['url']}")
    return "\n".join(lines)


def format_candidates(candidates):
    lines = ["## New content candidates (unvetted — check codec/bitrate/dub before adding)\n"]
    by_category = {}
    for c in candidates:
        by_category.setdefault(c["category"], []).append(c)
    for category, items in by_category.items():
        lines.append(f"\n### {category}")
        for c in items:
            lines.append(f"- [{c['title']} ({c['year']})]({c['url']}) — "
                          f"`{c['identifier']}`, {c['downloads']} downloads")
    return "\n".join(lines)


def main():
    problems = load("problems.json")
    candidates = load("candidates.json")

    if not problems and not candidates:
        print("Nothing to report.")
        return

    body_parts = []
    if problems:
        body_parts.append(format_problems(problems))
    if candidates:
        body_parts.append(format_candidates(candidates))
    body = "\n\n".join(body_parts)
    title = f"Content check: {len(problems)} link issue(s), {len(candidates)} new candidate(s)"

    existing = subprocess.run(
        ["gh", "issue", "list", "--label", LABEL, "--state", "open",
         "--json", "number", "--limit", "1"],
        capture_output=True, text=True, check=True,
    )
    open_issues = json.loads(existing.stdout)

    if open_issues:
        number = open_issues[0]["number"]
        subprocess.run(["gh", "issue", "comment", str(number), "--body", body], check=True)
        subprocess.run(["gh", "issue", "edit", str(number), "--title", title], check=True)
        print(f"Updated issue #{number}")
    else:
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body, "--label", LABEL],
            check=True,
        )
        print("Created new issue")


if __name__ == "__main__":
    main()
