# GitLab Extended Reference

Load this file only for less common GitLab operations or when ordinary `glab`
command examples are useful.

## Contents

- [Repository Setup](#repository-setup)
- [Merge Requests](#merge-requests)
- [Searching GitLab](#searching-gitlab)
- [Multi-Repository Operations](#multi-repository-operations)
- [Working with Issues](#working-with-issues)
- [Releases](#releases)
- [API Access](#api-access)

## Repository Setup

```bash
glab repo clone <owner>/<repo>
glab repo clone <owner>/<repo> -- --branch <branch>
glab repo clone <owner>/<repo> <directory>
glab repo fork <owner>/<repo>
glab repo fork <owner>/<repo> --clone
glab repo view
glab repo view <owner>/<repo>
```

## Merge Requests

Create:

```bash
glab mr create \
  --title "feat: add new feature" \
  --description "$(cat <<'EOF'
Your description here (supports markdown)
EOF
)" \
  --target-branch main \
  --assignee @me \
  --label "enhancement" \
  --yes

glab mr create --draft --title "WIP: feature in progress" --yes
glab mr create --fill --yes
```

List and view:

```bash
glab mr list
glab mr list --merged
glab mr list --closed
glab mr list --all
glab mr list --author @me
glab mr list --assignee @me
glab mr list --label bug,urgent
glab mr list --per-page 10
glab mr view
glab mr view <id>
```

Update:

```bash
glab mr update <id> --title "new title" --yes
glab mr update <id> --label "reviewed,approved" --yes
glab mr update <id> --assignee user1,user2 --yes
glab mr update <id> --reviewer user1,user2 --yes
glab mr update <id> --ready --yes
```

Merge:

```bash
glab mr merge <id> --yes
glab mr merge <id> --auto-merge=false --yes
glab mr merge <id> --squash --yes
glab mr merge <id> --remove-source-branch --yes
```

Checkout:

```bash
glab mr checkout <id>
```

## Searching GitLab

```bash
glab issue list --search "bug in login"
glab issue list --label "bug"
glab mr list --search "refactor auth"
```

Search across accessible GitLab projects with the API:

```bash
glab api "search?scope=issues&search=login+error" \
  | jq '.[] | {id, title, web_url}'

glab api "search?scope=merge_requests&search=auth+refactor" \
  | jq '.[] | {id, title, web_url}'

glab api "search?scope=projects&search=my-library" \
  | jq '.[] | {id, name, web_url}'

glab api "search?scope=blobs&search=deprecated+function" \
  | jq '.[] | {path, project_id, ref}'
```

## Multi-Repository Operations

For coordinated changes across multiple repositories:

1. List affected repositories.
2. Clone each repository.
3. Create branches with consistent naming.
4. Make the required changes.
5. Create MRs with linked descriptions.

Example:

```bash
REPOS="group/repo1 group/repo2 group/repo3"
BRANCH="fix/tracking-issue-123"
ISSUE_URL="https://gitlab.example.com/group/tracker/-/issues/100"

for repo in $REPOS; do
  echo "Processing $repo..."

  if [ ! -d "$(basename "$repo")" ]; then
    glab repo clone "$repo"
  fi

  cd "$(basename "$repo")" || exit 1
  git checkout -b "$BRANCH"

  # Apply the required change.

  git add .
  git commit -m "Fix tracked issue"
  git push -u origin "$BRANCH"

  glab mr create \
    --title "Fix tracked issue" \
    --description "Related to: $ISSUE_URL" \
    --label "maintenance" \
    --yes

  cd ..
done
```

## Working with Issues

```bash
glab issue create \
  --title "Bug: login fails on mobile" \
  --description "Steps to reproduce..." \
  --label "bug,mobile"

glab issue list
glab issue view <id>
glab issue close <id>
```

Reference issues in MR descriptions:

```bash
glab mr create --fill --description "Closes #42" --yes
glab mr create --fill --description "Relates to #42" --yes
```

## Releases

```bash
glab release create v1.0.0 \
  --name "Version 1.0.0" \
  --notes "$(cat CHANGELOG.md)"

glab release create v1.0.0 \
  --assets-links '[{"name":"binary","url":"https://example.com/download"}]'

glab release list
```

## API Access

Use `glab api` for operations not covered by `glab` subcommands:

```bash
glab api projects/:id/merge_requests | jq '.[] | {iid, title, state}'
glab api projects/:id/issues --method POST --field title="New issue"
glab api projects/:id/issues --paginate | jq '.[] | {iid, title, state}'
```
