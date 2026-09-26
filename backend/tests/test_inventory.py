from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.models import (
    Base,
    MenuItem,
    RawInventory,
    Recipe,
    TransactionLine,
)
from backend.inventory_service import process_order_deduction


@pytest.fixture
def db_session():
    """Configures an in-memory SQLite database and yields a session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seeded_data(db_session):
    """
    Seeds 1 Menu Item (Zinger Burger), 2 Raw Inventory items (Bun, Mayo),
    and 2 Recipe bridge records linking them.
    """
    # 1. Create Menu Item
    zinger_burger = MenuItem(
        item_code="ZING-01",
        name="Zinger Burger",
        description="Crispy chicken fillet in a toasted bun with mayo",
        category="Burgers",
        selling_price=Decimal("5.99"),
        is_active=True,
    )
    db_session.add(zinger_burger)
    db_session.flush()

    # 2. Create Raw Inventory Items
    bun = RawInventory(
        sku="ING-BUN-01",
        name="Bun