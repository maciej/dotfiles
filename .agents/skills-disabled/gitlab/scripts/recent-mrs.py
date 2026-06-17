#!/usr/bin/env python3
"""List recently updated GitLab merge requests using the glab mr command family.

This helper intentionally stays within:
  - glab mr list
  - glab mr view
  - glab mr diff

Usage:
    ./recent-mrs.py
    ./recent-mrs.py --hours 24 --json
    ./recent-mrs.py --repo group/project --hours 48
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any


def default_lookback_hours(now: datetime | None = None) -> int:
    """Use a wider default window on Mondays to cover Friday + weekend."""
    current = now or datetime.now().astimezone()
    return 72 if current.weekday() == 0 else 24


def parse_ts(value: str) -> datetime:
    """Parse GitLab ISO-8601 timestamps with trailing Z."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_command(argv: list[str]) -> str:
    """Run a command and return stdout, raising on failure."""
    result = subprocess.run(argv, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(argv)}\n{result.stderr.strip()}"
        )
    return result.stdout


def glab_mr_list(repo: str | None, per_page: int) -> list[dict[str, Any]]:
    """Fetch candidate MRs ordered by updated_at descending."""
    argv = [
        "glab",
        "mr",
        "list",
        "--all",
        "--output",
        "json",
        "--order",
        "updated_at",
        "--sort",
        "desc",
        "--per-page",
        str(per_page),
    ]
    if repo:
        argv.extend(["-R", repo])
    return json.loads(run_command(argv))


def glab_mr_view(iid: int, repo: str | None) -> dict[str, Any]:
    """Fetch detailed MR metadata."""
    argv = ["glab", "mr", "view", str(iid), "--output", "json"]
    if repo:
        argv.extend(["-R", repo])
    return json.loads(run_command(argv))


def glab_mr_files(iid: int, repo: str | None) -> list[str]:
    """Parse changed file paths from raw diff headers."""
    argv = ["glab", "mr", "diff", str(iid), "--raw"]
    if repo:
        argv.extend(["-R", repo])
    raw = run_command(argv)

    files: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        if not line.startswith("diff --git a/"):
            continue
        try:
            path = line[len("diff --git a/") :].split(" b/", 1)[0]
        except IndexError:
            continue
        if path not in seen:
            seen.add(path)
            files.append(path)
    return files


def summarize_description(description: str) -> str | None:
    """Extract the first non-empty paragraph line for compact text output."""
    for paragraph in description.split("\n\n"):
        line = paragraph.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("* "):
            continue
        return " ".join(line.split())
    return None


def build_records(
    repo: str | None, hours: int, per_page: int
) -> list[dict[str, Any]]:
    """Build detailed MR records updated within the requested window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    listed = glab_mr_list(repo=repo, per_page=per_page)
    listed = [mr for mr in listed if parse_ts(mr["updated_at"]) >= cutoff]

    records: list[dict[str, Any]] = []
    for mr in listed:
        iid = mr["iid"]
        details = glab_mr_view(iid=iid, repo=repo)
        files = glab_mr_files(iid=iid, repo=repo)
        records.append(
            {
                "iid": details["iid"],
                "title": details["title"],
                "state": details["state"],
                "draft": details.get("draft", details.get("work_in_progress", False)),
                "author": details["author"]["name"],
                "author_username": details["author"]["username"],
                "created_at": details["created_at"],
                "updated_at": details["updated_at"],
                "merged_at": details.get("merged_at"),
                "web_url": details["web_url"],
                "source_branch": details["source_branch"],
                "target_branch": details["target_branch"],
                "changes_count": details.get("changes_count"),
                "description": details.get("description", ""),
                "summary": summarize_description(details.get("description", "")),
                "files": files,
            }
        )

    return records


def format_text(records: list[dict[str, Any]], hours: int) -> str:
    """Render a compact grouped text summary."""
    if not records:
        return f"No merge requests updated in the last {hours} hours."

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["author"]].append(record)

    lines: list[str] = []
    for author in sorted(grouped):
        lines.append(f"{author}:")
        for record in sorted(
            grouped[author], key=lambda item: item["updated_at"], reverse=True
        ):
            lines.append(
                f"  !{record['iid']} [{record['state']}] {record['title']}"
            )
            lines.append(f"    updated: {record['updated_at']}")
            if record["summary"]:
                lines.append(f"    summary: {record['summary']}")
            if record["files"]:
                preview = ", ".join(record["files"][:5])
                if len(record["files"]) > 5:
                    preview += f", ... ({len(record['files'])} files)"
                lines.append(f"    files: {preview}")
    return "\n".join(lines)


def main() -> int:
    default_hours = default_lookback_hours()
    parser = argparse.ArgumentParser(
        description="List recently updated GitLab MRs using glab mr commands."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=default_hours,
        help=(
            "Look back this many hours "
            f"(default: {default_hours}; 72 on Monday, otherwise 24)."
        ),
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=30,
        help="How many recent MRs to fetch before local filtering (default: 30).",
    )
    parser.add_argument(
        "--repo",
        help="Optional repository override for glab -R (owner/repo or group/repo).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    args = parser.parse_args()

    try:
        records = build_records(
            repo=args.repo,
            hours=args.hours,
            per_page=args.per_page,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(records, indent=2))
    else:
        print(format_text(records, hours=args.hours))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
