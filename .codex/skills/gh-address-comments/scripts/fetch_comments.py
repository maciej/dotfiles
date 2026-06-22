#!/usr/bin/env python3
"""
Fetch all PR conversation comments + reviews + review threads (inline threads)
for a GitHub pull request, by shelling out to:

  gh api graphql

Requires:
  - `gh auth login` already set up
  - a PR URL, a PR number plus --repo, or a current branch with an associated PR

Usage:
  python3 fetch_comments.py --repo owner/repo --pr 123 > pr_comments.json
  python3 fetch_comments.py --pr https://github.com/owner/repo/pull/123 > pr_comments.json
  python3 fetch_comments.py > pr_comments.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

QUERY = """\
query(
  $owner: String!,
  $repo: String!,
  $number: Int!,
  $commentsCursor: String,
  $reviewsCursor: String,
  $threadsCursor: String
) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      url
      title
      state

      # Top-level "Conversation" comments (issue comments on the PR)
      comments(first: 100, after: $commentsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          body
          createdAt
          updatedAt
          author { login }
        }
      }

      # Review submissions (Approve / Request changes / Comment), with body if present
      reviews(first: 100, after: $reviewsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          state
          body
          submittedAt
          author { login }
        }
      }

      # Inline review threads (grouped), includes resolved state
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          diffSide
          startLine
          startDiffSide
          originalLine
          originalStartLine
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              body
              createdAt
              updatedAt
              author { login }
            }
          }
        }
      }
    }
  }
}
"""

PR_URL_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:[/?#].*)?$")


def _run(cmd: list[str], stdin: str | None = None) -> str:
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout


def _run_json(cmd: list[str], stdin: str | None = None) -> dict[str, Any]:
    out = _run(cmd, stdin=stdin)
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from command output: {e}\nRaw:\n{out}") from e


def _ensure_gh_authenticated() -> None:
    try:
        _run(["gh", "auth", "status"])
    except RuntimeError:
        print("run `gh auth login` to authenticate the GitHub CLI", file=sys.stderr)
        raise RuntimeError("gh auth status failed; run `gh auth login` to authenticate the GitHub CLI") from None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub PR comments, reviews, and review threads as JSON."
    )
    parser.add_argument(
        "--repo",
        help="Target repository as owner/repo. Optional for PR URLs and current-branch PRs.",
    )
    parser.add_argument(
        "--pr",
        help="PR number or URL. Defaults to the PR associated with the current branch.",
    )
    return parser.parse_args()


def gh_pr_view_json(fields: str, pr: str | None = None, repo: str | None = None) -> dict[str, Any]:
    cmd = ["gh", "pr", "view"]
    if pr:
        cmd.append(pr)
    if repo:
        cmd += ["--repo", repo]
    cmd += ["--json", fields]
    return _run_json(cmd)


def gh_repo_view_json(fields: str) -> dict[str, Any]:
    return _run_json(["gh", "repo", "view", "--json", fields])


def parse_pr_url(value: str) -> tuple[str, str, int] | None:
    match = PR_URL_RE.match(value)
    if not match:
        return None
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def split_repo_slug(repo_slug: str) -> tuple[str, str]:
    parts = (
        repo_slug.strip()
        .removeprefix("https://github.com/")
        .removeprefix("git@github.com:")
        .removesuffix(".git")
        .split("/")
    )
    if len(parts) != 2 or not all(parts):
        raise RuntimeError(f"Repository must be owner/repo, got: {repo_slug}")
    return parts[0], parts[1]


def default_repo_slug() -> str:
    repo = gh_repo_view_json("nameWithOwner")
    name_with_owner = repo.get("nameWithOwner")
    if not name_with_owner:
        raise RuntimeError("Unable to resolve repository from the current directory.")
    return str(name_with_owner)


def get_pr_ref(repo_arg: str | None, pr_arg: str | None) -> tuple[str, str, int]:
    """
    Resolve the base repository and PR number for GraphQL review-thread queries.
    """
    if pr_arg:
        parsed_url = parse_pr_url(pr_arg)
        if parsed_url:
            return parsed_url

    repo_slug = repo_arg or default_repo_slug()

    if pr_arg:
        pr = gh_pr_view_json("number,url", pr=pr_arg, repo=repo_slug)
    else:
        pr = gh_pr_view_json("number,url", repo=repo_slug if repo_arg else None)

    url = pr.get("url")
    if isinstance(url, str):
        parsed_url = parse_pr_url(url)
        if parsed_url:
            return parsed_url

    owner, repo = split_repo_slug(repo_slug)
    number = int(pr["number"])
    return owner, repo, number


def gh_api_graphql(
    owner: str,
    repo: str,
    number: int,
    comments_cursor: str | None = None,
    reviews_cursor: str | None = None,
    threads_cursor: str | None = None,
) -> dict[str, Any]:
    """
    Call `gh api graphql` using -F variables, avoiding JSON blobs with nulls.
    Query is passed via stdin using query=@- to avoid shell newline/quoting issues.
    """
    cmd = [
        "gh",
        "api",
        "graphql",
        "-F",
        "query=@-",
        "-F",
        f"owner={owner}",
        "-F",
        f"repo={repo}",
        "-F",
        f"number={number}",
    ]
    if comments_cursor:
        cmd += ["-F", f"commentsCursor={comments_cursor}"]
    if reviews_cursor:
        cmd += ["-F", f"reviewsCursor={reviews_cursor}"]
    if threads_cursor:
        cmd += ["-F", f"threadsCursor={threads_cursor}"]

    return _run_json(cmd, stdin=QUERY)


def fetch_all(owner: str, repo: str, number: int) -> dict[str, Any]:
    conversation_comments: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    review_threads: list[dict[str, Any]] = []

    comments_cursor: str | None = None
    reviews_cursor: str | None = None
    threads_cursor: str | None = None

    pr_meta: dict[str, Any] | None = None

    while True:
        payload = gh_api_graphql(
            owner=owner,
            repo=repo,
            number=number,
            comments_cursor=comments_cursor,
            reviews_cursor=reviews_cursor,
            threads_cursor=threads_cursor,
        )

        if "errors" in payload and payload["errors"]:
            raise RuntimeError(f"GitHub GraphQL errors:\n{json.dumps(payload['errors'], indent=2)}")

        pr = payload["data"]["repository"]["pullRequest"]
        if pr_meta is None:
            pr_meta = {
                "number": pr["number"],
                "url": pr["url"],
                "title": pr["title"],
                "state": pr["state"],
                "owner": owner,
                "repo": repo,
            }

        c = pr["comments"]
        r = pr["reviews"]
        t = pr["reviewThreads"]

        conversation_comments.extend(c.get("nodes") or [])
        reviews.extend(r.get("nodes") or [])
        review_threads.extend(t.get("nodes") or [])

        comments_cursor = c["pageInfo"]["endCursor"] if c["pageInfo"]["hasNextPage"] else None
        reviews_cursor = r["pageInfo"]["endCursor"] if r["pageInfo"]["hasNextPage"] else None
        threads_cursor = t["pageInfo"]["endCursor"] if t["pageInfo"]["hasNextPage"] else None

        if not (comments_cursor or reviews_cursor or threads_cursor):
            break

    assert pr_meta is not None
    return {
        "pull_request": pr_meta,
        "conversation_comments": conversation_comments,
        "reviews": reviews,
        "review_threads": review_threads,
    }


def main() -> None:
    args = parse_args()
    _ensure_gh_authenticated()
    owner, repo, number = get_pr_ref(args.repo, args.pr)
    result = fetch_all(owner, repo, number)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
