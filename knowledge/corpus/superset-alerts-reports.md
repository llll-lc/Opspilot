# Alerts and reports

## Scheduling prerequisites

Alerts and reports require explicit configuration and an asynchronous scheduling path. This derived note preserves three evidence scopes: Superset application health, asynchronous runtime health, and the individual business-job history.

## Distinguish evidence

`reports.scheduler` configuration alone does not prove a report ran. A healthy web endpoint alone does not prove a worker, beat process, broker, or delivery path is healthy. Obtain a current observation for each relevant scope before escalating.

1. Read application health.
2. Read runtime component health.
3. Read schedule and recent run history.
