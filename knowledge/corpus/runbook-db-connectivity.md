# Synthetic internal Runbook: database connectivity

> **Synthetic OpsPilot demonstration material.** It is not an Apache Superset document or production enterprise procedure.

## Symptoms

Use when a scoped connection test reports `AUTHENTICATION_FAILED`, `NETWORK_TIMEOUT`, or a driver mismatch. Record the exact error class, affected database identifier, and observation time.

## Read-only discrimination

1. Confirm application health separately from the connection result.
2. Retrieve only the authorized database metadata.
3. Compare the current error class with the configured driver category.

## Stop and escalate

Do not reveal, edit, rotate, or test guessed credentials. Escalate if remediation needs a credential, network, driver, or connection configuration change.
