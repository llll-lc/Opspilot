# Connecting databases

## Driver boundary

Superset requires a driver compatible with the target database. This local note records a derived check only: compare the configured engine and driver with the supported connection documentation before changing configuration.

## Read-only evidence

Collect the current database metadata and the reported connection-test error class. A timeout, authentication failure, and missing driver are different evidence categories. Do not place a connection URI, password, or token in a ticket or retrieval query.

```ini
SQLALCHEMY_DATABASE_URI=<redacted and never stored in knowledge>
```
