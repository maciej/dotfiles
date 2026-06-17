#!/usr/bin/env python3
"""List GitLab MRs pending your review (excluding drafts and already-approved).

Usage:
    ./review-queue.py [options] [gitlab-host]

Options:
    --json              Output as JSON array (default: TSV table)
    --user <username>   Check queue for specific user (default: current user)

Arguments:
    gitlab-host         GitLab hostname (falls back to $GITLAB_HOST)

Examples:
    ./review-queue.py gitlab.example.com
    ./review-queue.py --json gitlab.example.com
    ./review-queue.py --user jsmith gitlab.example.com
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def glab_api(endpoint: str, host: str) -> Any:
    """Call glab api and return parsed JSON."""
    env = os.environ.copy()
    env["GITLAB_HOST"] = host

    result = subprocess.run(
        ["glab", "api", endpoint],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"glab api {endpoint} failed: {result.stderr}")

    return json.loads(result.stdout)


def get_current_username(host: str) -> str:
    """Get the authenticated user's username."""
    user = glab_api("user", host)
    return user["username"]


def get_reviewer_mrs(user: str, host: str) -> list[dict]:
    """Fetch open MRs where user is a reviewer (excluding drafts)."""
    endpoint = f"merge_requests?reviewer_username={user}&state=opened&scope=all"
    mrs = glab_api(endpoint, host)

    # Filter out drafts
    return [mr for mr in mrs if not mr.get("draft", False)]


def get_approvers(project_id: int, mr_iid: int, host: str) -> list[str] | None:
    """Get list of usernames who approved the MR.

    Returns None if the API call fails (e.g., deleted project).
    """
    endpoint = f"projects/{project_id}/merge_requests/{mr_iid}/approvals"
    try:
        approvals = glab_api(endpoint, host)
        return [a["user"]["username"] for a in approvals.get("approved_by", [])]
    except RuntimeError:
        return None


def check_approval(
    mr: dict, current_user: str, host: str
) -> tuple[dict, bool, str | None]:
    """Check if MR is pending approval.

    Returns:
        (mr, is_pending, warning) - warning is None if no issues
    """
    approvers = get_approvers(mr["project_id"], mr["iid"], host)
    if approvers is None:
        return (
            mr,
            True,
            f"Warning: Could not check approvals for !{mr['iid']}, including in queue",
        )
    return (mr, current_user not in approvers, None)


def extract_project_path(web_url: str) -> str:
    """Extract project path from MR web URL.

    Example: https://gitlab.example.com/org/repo/-/merge_requests/123
             -> org/repo
    """
    # Remove protocol and host
    path = web_url.split("://", 1)[-1]
    # Remove host
    path = "/".join(path.split("/")[1:])
    # Remove /-/merge_requests/N
    if "/-/merge_requests" in path:
        path = path.split("/-/merge_requests")[0]
    return path


def format_table(mrs: list[dict]) -> str:
    """Format MRs as a TSV table."""
    lines = ["MR\tTITLE\tAUTHOR\tREPO\tURL"]
    for mr in mrs:
        title = mr["title"]
        if len(title) > 50:
            title = title[:47] + "..."
        project_path = extract_project_path(mr["web_url"])
        repo = project_path.split("/")[-1]
        lines.append(
            f"!{mr['iid']}\t{title}\t{mr['author']['username']}\t{repo}\t{mr['web_url']}"
        )
    return "\n".join(lines)


def format_json(mrs: list[dict]) -> str:
    """Format MRs as JSON array."""
    output = []
    for mr in mrs:
        output.append(
            {
                "iid": mr["iid"],
                "title": mr["title"],
                "author": mr["author"]["username"],
                "project_id": mr["project_id"],
                "project_path": extract_project_path(mr["web_url"]),
                "web_url": mr["web_url"],
            }
        )
    return json.dumps(output, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List GitLab MRs pending your review (excluding drafts and already-approved)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON array (default: TSV table)",
    )
    parser.add_argument(
        "--user",
        metavar="USERNAME",
        help="Check queue for specific user (default: current user)",
    )
    parser.add_argument(
        "host",
        nargs="?",
        help="GitLab hostname (falls back to $GITLAB_HOST)",
    )

    args = parser.parse_args()

    # Resolve GitLab host
    host = args.host or os.environ.get("GITLAB_HOST")
    if not host:
        print(
            "Error: GitLab host not specified. Provide as argument or set $GITLAB_HOST.",
            file=sys.stderr,
        )
        return 1

    # Check glab is available
    try:
        subprocess.run(
            ["glab", "--version"], capture_output=True, check=True
        )
    except FileNotFoundError:
        print(
            "Error: glab CLI not found. Install with: brew install glab",
            file=sys.stderr,
        )
        return 1

    # Get current username for approval check
    try:
        current_user = get_current_username(host)
    except RuntimeError as e:
        print(f"Error getting current user: {e}", file=sys.stderr)
        return 1

    # Determine whose queue to check
    reviewer = args.user or current_user

    # Fetch MRs where user is reviewer
    try:
        mrs = get_reviewer_mrs(reviewer, host)
    except RuntimeError as e:
        print(f"Error fetching MRs: {e}", file=sys.stderr)
        return 1

    if not mrs:
        if args.json:
            print("[]")
        else:
            print("No MRs pending review.")
        return 0

    # Filter out MRs already approved by current user (check in parallel)
    pending_mrs = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(check_approval, mr, current_user, host): mr
            for mr in mrs
        }
        for future in as_completed(futures):
            mr, is_pending, warning = future.result()
            if warning:
                print(warning, file=sys.stderr)
            if is_pending:
                pending_mrs.append(mr)

    # Output results
    if not pending_mrs:
        if args.json:
            print("[]")
        else:
            print("No MRs pending review (all approved or drafts).")
        return 0

    if args.json:
        print(format_json(pending_mrs))
    else:
        print(format_table(pending_mrs))

    return 0


if __name__ == "__main__":
    sys.exit(main())
