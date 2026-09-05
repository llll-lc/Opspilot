# Database migrations

Alembic owns the OpsPilot business/knowledge/audit schema. Set `DATABASE_URL` to an
OpsPilot PostgreSQL database before running migration commands. The Superset metadata
database is a separate target-system resource and must never be used here.
