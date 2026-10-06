"""Development seed.

Inserts:

* user `test.user@example.com` (password is hashed, never stored in plaintext)
* the NSE and BSE equity master
* a fictional `TEST_STOCK` that is outside the Indian market and is not searchable

No prices, fundamentals, news, or other market figures are inserted.
"""

import hashlib
from collections.abc import Sequence

from sqlalchemy import insert, select

from app.core.database import SessionLocal
from app.data_providers.india.metadata import bundled_listings
from app.models import Stock, User

TEST_USER_EMAIL = "test.user@example.com"
TEST_USER_NAME = "Test User"
TEST_STOCK_SYMBOL = "TEST_STOCK"
TEST_STOCK_EXCHANGE = "TEST"
# Development-only secret used to build the stored hash. It is not written to the database.
_DEV_SEED_PASSWORD = "dev-only-not-for-production"


def hash_dev_password(password: str) -> str:
    """Hash the development seed password. This is not the production password hasher."""
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"stocksense-dev-seed",
        100_000,
    )
    return f"pbkdf2_sha256$stocksense-dev-seed${digest.hex()}"


def seed() -> Sequence[str]:
    """Insert missing fictional records. Existing seed rows are left unchanged."""
    created: list[str] = []
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == TEST_USER_EMAIL))
        if user is None:
            session.add(
                User(
                    email=TEST_USER_EMAIL,
                    password_hash=hash_dev_password(_DEV_SEED_PASSWORD),
                    full_name=TEST_USER_NAME,
                    is_active=True,
                )
            )
            created.append("users:test.user@example.com")

        stock = session.scalar(
            select(Stock).where(
                Stock.symbol == TEST_STOCK_SYMBOL,
                Stock.exchange == TEST_STOCK_EXCHANGE,
            )
        )
        if stock is None:
            session.add(
                Stock(
                    symbol=TEST_STOCK_SYMBOL,
                    company_name="Fictional Test Company",
                    exchange=TEST_STOCK_EXCHANGE,
                    country="XX",
                    currency="XXX",
                    sector="Test Sector",
                    industry="Test Industry",
                    is_active=True,
                )
            )
            created.append("stocks:TEST_STOCK")

        known = {
            (symbol, exchange)
            for symbol, exchange in session.execute(
                select(Stock.symbol, Stock.exchange).where(Stock.exchange.in_(("NSE", "BSE")))
            )
        }
        pending: list[dict[str, object]] = []
        for listing in bundled_listings():
            key = (listing.symbol, listing.exchange)
            if key in known:
                continue
            pending.append(
                {
                    "symbol": listing.symbol,
                    "company_name": listing.company_name,
                    "exchange": listing.exchange,
                    "country": listing.country,
                    "currency": listing.currency,
                    "sector": listing.sector,
                    "industry": listing.industry,
                    "isin": listing.isin,
                    "is_active": True,
                }
            )
            known.add(key)
        for start in range(0, len(pending), 500):
            session.execute(insert(Stock), pending[start : start + 500])
        if pending:
            created.append(f"stocks:added:{len(pending)}")

        session.commit()
    return created


def main() -> None:
    from app.core.config import settings

    if settings.app_env == "production":
        raise SystemExit("Refusing to seed a production database.")
    created = seed()
    if created:
        print("Seeded records:")
        for name in created:
            print(f"  {name}")
    else:
        print("Seed records already exist.")


if __name__ == "__main__":
    main()
