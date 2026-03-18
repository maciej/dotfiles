# Rate Limits

> Portable reference for the GitLab skill. Keep instance-specific thresholds in an optional `config.json` in the skill root, not in this file.

## Optional Local Config

If this skill includes a local `config.json`, it may provide instance-specific rate-limit hints:

```json
{
  "rate_limits": {
    "authenticated_api": { "max_requests": 36000, "period": "1 hour" },
    "authenticated_web": { "max_requests": 36000, "period": "1 hour" },
    "sustained_requests_per_second_hint": 10,
    "low_remaining_threshold": 1000
  }
}
```

All keys are optional. Missing `config.json` or missing values are not setup failures; fall back to the generic `429` and backoff guidance in `SKILL.md`.

## Public GitLab Guidance

- GitLab can enforce both configurable and fixed/default rate limits depending on endpoint and hosting model.
- `HTTP 429 Too Many Requests` is the main signal that a limit was exceeded.
- `glab api -i` can expose response headers such as `RateLimit-Remaining` and `Retry-After` when you need to debug a limit.
- For bulk or comment-heavy workflows, pace requests, reuse data from single responses, and back off on repeated failures.

## Documented Limits You May Encounter

These values come from public GitLab documentation and are useful as general expectations:

| Endpoint/Action | Limit | Scope |
|-----------------|-------|-------|
| Repository archives download | 5 req/min | Per user |
| Webhook testing | 5 req/min | Per user |
| AI action (GraphQL) | 160 calls/8 hours | Per user |
| List project members API | 200 req/min default | Per endpoint |
| Delete member API | 60 deletions/min | System-wide |

## Reference

- [GitLab rate limits documentation](https://docs.gitlab.com/security/rate_limits/)
