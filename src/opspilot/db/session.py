"""Explicit engine/session factories; importing this module performs no I/O."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create a PostgreSQL engine without opening a connection eagerly."""
    return create_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the transaction-scoped session factory used by later services."""
    return sessionmaker(bind=engine, expire_on_commit=False)
