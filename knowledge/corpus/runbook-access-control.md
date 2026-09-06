# Synthetic internal Runbook: access control

> **Synthetic OpsPilot demonstration material.** It describes a safe diagnosis boundary, not a production role-management policy.

## Symptoms

Use for `PERMISSION_DENIED` or a report that a user can see a dashboard but cannot access an underlying dataset. Keep the resource and requester scope explicit.

## Read-only discrimination

1. Confirm application availability.
2. Retrieve scoped dataset or dashboard metadata.
3. Preserve the current denial observation and distinguish it from not-found filtering.

## Stop and escalate

Never grant roles, alter permissions, impersonate an administrator, or expose another user's metadata. Escalate proposed access changes to the authorization workflow.
