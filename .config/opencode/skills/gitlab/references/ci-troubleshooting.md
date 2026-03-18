# CI/CD Troubleshooting Reference

Load this reference when a pipeline has failed and needs remediation.

## Contents

- [Identify Failed Jobs](#identify-failed-jobs)
- [Pull and Analyze Job Logs](#pull-and-analyze-job-logs)
- [Common CI Failure Patterns](#common-ci-failure-patterns)
- [Address Failures Locally](#address-failures-locally)
- [Retry and Rerun Jobs](#retry-and-rerun-jobs)
- [Remediation Workflow](#remediation-workflow)
- [Debug with CI Variables](#debug-with-ci-variables)
- [Artifacts and Reports](#artifacts-and-reports)

## Identify Failed Jobs

When a pipeline fails, first identify which jobs failed:

```bash
# List jobs in the current pipeline
glab ci list

# List jobs for a specific branch
glab ci list --branch main
```

The output shows each job's status. Focus on jobs with `failed` status.

## Pull and Analyze Job Logs

```bash
# Stream logs from a running or completed job
glab ci trace <job-name>

# View logs for a specific job by ID
glab ci trace <job-id>

# Example: view logs for the "test" job
glab ci trace test

# For jobs in specific pipelines
glab ci trace <job-name> --pipeline-id <pipeline-id>
```

**Log analysis tips:**
- Scroll to the end first—the final error is usually the root cause
- Look for `error:`, `Error:`, `FAILED`, `fatal:`, or exit codes
- Check for timeout messages if the job hung
- Note the stage and job name for context

## Common CI Failure Patterns

| Pattern | Log Signature | Typical Fix |
|---------|---------------|-------------|
| Test failure | `FAIL`, `AssertionError`, `expected ... got` | Fix the failing test or the code it tests |
| Lint error | `error:`, style/format violations | Run linter locally, fix issues |
| Build failure | `compilation failed`, `cannot find module` | Check dependencies, imports, syntax |
| Timeout | `Job timed out`, `exceeded limit` | Optimize slow operations or increase timeout |
| Missing env/secret | `undefined`, `missing required`, `authentication failed` | Check CI variables configuration |
| Dependency issue | `404 Not Found`, `version not found` | Update dependency versions, check registry access |

## Address Failures Locally

1. **Reproduce the failure locally** (when possible):
   ```bash
   # Run the same commands from .gitlab-ci.yml (examples by language)
   make test          # Makefile-based projects
   go test ./...      # Go
   pytest             # Python
   npm test           # Node.js
   cargo test         # Rust
   ```

2. **Fix the issue and push**

3. **Monitor the new pipeline** to verify the fix

## Retry and Rerun Jobs

```bash
# Retry a specific job (job name or ID required)
glab ci retry <job-name>
glab ci retry <job-id>

# Retry a job in a specific pipeline
glab ci retry <job-name> --pipeline-id <pipeline-id>

# Trigger a completely new pipeline
glab ci run

# Trigger with CI variables (useful for conditional jobs)
glab ci run --variables "FORCE_FULL_TEST:true"
```

**When to retry vs. fix:**
- **Retry**: Flaky tests, transient network errors, runner issues
- **Fix**: Genuine code errors, missing dependencies, configuration problems

## Remediation Workflow

Follow this process when an MR pipeline fails:

1. **Check status**: `glab ci status` or `glab mr view`
2. **Identify failed jobs**: `glab ci list`
3. **Pull logs**: `glab ci trace <job-name>`
4. **Analyze the error**: Find root cause in logs
5. **Fix locally**: Reproduce and fix the issue
6. **Push fix**: `git commit` and `git push`
7. **Verify**: re-check with `glab ci status` and `glab ci list` until the new pipeline reaches a terminal state
8. **If still failing**: Repeat from step 2

## Debug with CI Variables

```bash
# List CI/CD variables (requires maintainer access)
glab variable list

# Set a variable for debugging
glab variable set DEBUG_CI "true"

# Run pipeline with debug variable
glab ci run --variables "CI_DEBUG_TRACE:true"
```

## Artifacts and Reports

```bash
# Download job artifacts (requires ref and job name)
glab job artifact main build
glab job artifact <branch> <job-name>

# Download to specific path
glab job artifact main build --path="./artifacts/"
```

Use artifacts to inspect test reports, coverage data, or build outputs that might explain failures.
