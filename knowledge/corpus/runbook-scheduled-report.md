# Synthetic internal Runbook: scheduled report

> **Synthetic OpsPilot demonstration material.** It does not change schedules, retry jobs, or restart services.

## Symptoms

Use when a scheduled report or alert was not sent. Capture the named schedule, expected time window, and any current run identifier.

## Evidence scopes

| Scope | Read-only question |
| --- | --- |
| APPLICATION | Is the Superset application endpoint reachable? |
| RUNTIME_COMPONENT | Are worker, beat, and broker observations available and healthy? |
| BUSINESS_JOB | Does the named report schedule show a recent completed run? |

## Stop and escalate

Do not treat connector health as worker health. Escalate before a retry, schedule edit, delivery configuration change, or worker/beat/Redis restart.
