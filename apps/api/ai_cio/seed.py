"""Seed instruments from instruments/v1.0.json into canonical Postgres."""
from __future__ import annotations

from ai_cio.db.session import get_session
from ai_cio.services.instruments import seed_instrument


def main() -> None:
    db = get_session()
    try:
        row = seed_instrument(db)
        db.commit()
        print(f"Seeded instrument version {row.version} (id={row.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
