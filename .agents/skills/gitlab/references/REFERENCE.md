# GitLab Extended Reference

Additional operations for less common workflows. Load this reference when needed.

## Contents

- [Multi-Repository Operations](#multi-repository-operations)
- [Working with Issues](#working-with-issues)
- [Releases](#releases)
- [API Access](#api-access)
- [CI/CD Advanced Operations](#cicd-advanced-operations)

## Multi-Repository Operations

For coordinated changes across multiple repositories (e.g., dependency updates, security fixes):

### Strategy

1. **List affected repositories**: Identify all repos that need changes
2. **Clone each repository**: Use `glab repo clone`
3. **Create branches with consistent naming**: Use a common prefix
4. **Make changes in each repo**: Apply the fix/update
5. **Create MRs with linked descriptions**: Reference the tracking issue

### Example: Coordinated Security Fix

```bash
# Define repos and fix details
REPOS="group/repo1 group/repo2 group/repo3"
BRANCH="fix/CVE-2024-12345"
ISSUE_URL="https://gitlab.example.com/group/tracker/-/issues/100"

for repo in $REPOS; do
  echo "Processing $repo..."
  
  # Clone if not exists
  if [ ! -d "$(basename $repo)" ]; then
    glab repo clone "$repo"
  fi
  
  cd "$(basename $repo)"
  
  # Create branch and make changes
  git checkout -b "$BRANCH"
  
  # Apply fix (example: update dependency version)
  # sed -i 's/vulnerable-pkg@1.0/vulnerable-pkg@1.1/g' package.json
  
  git add .
  git commit -m "<your commit message>"
  
  git push -u origin "$BRANCH"
  
  # Create MR
  glab mr create \
    --title "<MR title>" \
    --description "Updates vulnerable-pkg to patched version.

Related to: $ISSUE_URL" \
    --label "security"
  
  cd ..
done
```

## Working with Issues

### Create an Issue

```bash
glab issue create \
  --title "Bug: login fails on mobile" \
  --description "Steps to reproduce..." \
  --label "bug,mobile"
```

### List and View Issues

```bash
glab issue list
glab issue view 42
```

### Close an Issue

```bash
glab issue close 42
```

### Link MR to Issue

When creating an MR, reference the issue in the description:

```bash
glab mr create --description "Closes #42"
```

## Releases

### Create a Release

```bash
glab release create v1.0.0 \
  --name "Version 1.0.0" \
  --notes "$(cat CHANGELOG.md)"

# With assets
glab release create v1.0.0 --assets-links '[{"name":"binary","url":"https://..."}]'
```

### List Releases

```bash
glab release list
```

## API Access

For operations not covered by `glab` subcommands, use the API directly:

```bash
# GET request
glab api projects/:id/merge_requests

# POST request
glab api projects/:id/issues --method POST --field title="New issue"

# With pagination
glab api projects/:id/issues --paginate
```


