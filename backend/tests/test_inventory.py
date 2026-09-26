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
        name="Bun",
        description="Burger bun",
        unit_of_measure="unit",
        quantity_on_hand=Decimal("100.0000"),
        reorder_level=Decimal("10.0000"),
        unit_cost=Decimal("1.0000"),
    )
    mayo = RawInventory(
        sku="ING-MAYO-01",
        name="Mayo",
        description="Mayonnaise sauce",
        unit_of_measure="g",
        quantity_on_hand=Decimal("500.0000"),
        reorder_level=Decimal("50.0000"),
        unit_cost=Decimal("1.0000"),
    )
    db_session.add_all([bun, mayo])
    db_session.flush()

    # 3. Create Recipe Bridge Records
    bun_recipe = Recipe(
        menu_item_id=zinger_burger.id,
        ingredient_id=bun.id,
        quantity_required=Decimal("1.0000"),
        unit_of_measure="unit",
    )
    mayo_recipe = Recipe(
        menu_item_id=zinger_burger.id,
        ingredient_id=mayo.id,
        quantity_required=Decimal("20.0000"),
        unit_of_measure="g",
    )
    db_session.add_all([bun_recipe, mayo_recipe])
    db_session.commit()

    return {
        "menu_item": zinger_burger,
        "bun": bun,
        "mayo": mayo,
    }


def test_zinger_burger_deduction(db_session, seeded_data):
    zinger = seeded_data["menu_item"]
    bun = seeded_data["bun"]
    mayo = seeded_data["mayo"]

    journal_entry = process_order_deduction(
        session=db_session,
        menu_item_id=zinger.id,
        quantity=1,
    )

    assert journal_entry is not None
    assert journal_entry.id is not None

    lines = db_session.scalars(
        select(TransactionLine).where(
            TransactionLine.journal_entry_id == journal_entry.id
        )
    ).all()

    assert len(lines) == 2

    lines_by_inventory = {line.inventory_id: line for line in lines}

    assert bun.id in lines_by_inventory
    assert mayo.id in lines_by_inventory

    bun_line = lines_by_inventory[bun.id]
    mayo_line = lines_by_inventory[mayo.id]

    assert bun_line.amount == Decimal("-1.00")
    assert mayo_line.amount == Decimal("-20.00")
