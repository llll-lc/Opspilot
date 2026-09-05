"""Create non-committed, random credentials for the isolated OP-003 lab."""

import secrets
from pathlib import Path

RUNTIME_FILE = Path(__file__).with_name(".runtime") / "op003.env"


def main() -> None:
    RUNTIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    if RUNTIME_FILE.exists():
        print(f"Reuse existing local lab environment: {RUNTIME_FILE}")
        return

    values = {
        "OP003_SUPERSET_SECRET_KEY": secrets.token_urlsafe(48),
        "OP003_DB_PASSWORD": secrets.token_urlsafe(24),
        "OP003_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "OP003_READER_PASSWORD": secrets.token_urlsafe(24),
        "OP003_MCP_JWT_SECRET": secrets.token_urlsafe(48),
    }
    RUNTIME_FILE.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n",
        encoding="utf-8",
    )
    print(f"Created local lab environment: {RUNTIME_FILE}")


if __name__ == "__main__":
    main()
