from __future__ import annotations

import os
from datetime import timedelta

from celery.schedules import crontab


SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_DATABASE_URI"]
WTF_CSRF_ENABLED = True
SCARF_ANALYTICS = False

CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}
DATA_CACHE_CONFIG = CACHE_CONFIG

if os.getenv("OP001_REPORTS_ENABLED", "false").lower() == "true":
    FEATURE_FLAGS = {"ALERT_REPORTS": True}

    class CeleryConfig:
        broker_url = "redis://redis:6379/0"
        result_backend = "redis://redis:6379/0"
        imports = ("superset.sql_lab", "superset.tasks.scheduler")
        worker_prefetch_multiplier = 1
        task_acks_late = True
        task_annotations = {
            "sql_lab.get_sql_results": {"rate_limit": "10/s"},
        }
        beat_schedule = {
            "reports.scheduler": {
                "task": "reports.scheduler",
                "schedule": crontab(minute="*", hour="*"),
            },
            "reports.prune_log": {
                "task": "reports.prune_log",
                "schedule": crontab(minute=0, hour=0),
            },
        }
        task_soft_time_limit = int(timedelta(minutes=5).total_seconds())
        task_time_limit = int(timedelta(minutes=6).total_seconds())

    CELERY_CONFIG = CeleryConfig
