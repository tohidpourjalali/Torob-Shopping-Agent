"""Create database tables & basic indexes (runs on startup / via CLI)."""
from __future__ import annotations

from app.db.database import engine, Base


def init_db() -> None:
    """Create all tables defined in app.db.models."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
