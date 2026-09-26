import uuid
from datetime import date
from decimal import Decimal
from typing import Union
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    MenuItem,
    Recipe,
    RawInventory,
    JournalEntry,
    TransactionLine,
    EntryType,
    EntryStatus,
)


class InventoryError(Exception):
    """Base exception for inventory service errors."""
    pass


class MenuItemNotFoundError(InventoryError):
    """Raised when menu item cannot be found."""
    pass


class InsufficientInventoryError(InventoryError):
    """Raised when there is not enough raw inventory stock."""
    pass


def process_order_deduction(
    session: Session,
    menu_item_id: int,
    quantity: Union[int, Decimal, float],
) -> JournalEntry:
    """
    Deducts raw inventory based on a menu item recipe and order quantity,
    recording the negative deductions inside transaction lines for raw inventory ledger.
    Wraps the operation in a transaction and rolls back if an error occurs.
    """
    order_qty = Decimal(str(quantity))
    if order_qty <= 0:
        raise ValueError("Order quantity must be greater than zero.")

    try:
        # Retrieve the menu item
        menu_item = session.get(MenuItem, menu_item_id)
        if not menu_item:
            raise MenuItemNotFoundError(f"MenuItem with id {menu_item_id} not found.")

        # Query all recipe ingredients for this menu item
        recipes = session.scalars(
            select(Recipe).where(Recipe.menu_item_id == menu_item_id)
        ).all()

        if not recipes:
            raise InventoryError(f"No recipe found for MenuItem id {menu_item_id}.")

        # Generate a unique journal entry for this deduction
        entry_number = f"JE-INV-{uuid.uuid4().hex[:8].upper()}"
        journal_entry = JournalEntry(
            entry_number=entry_number,
            entry_date=date.today(),
            reference=f"ORDER-MENU-{menu_item_id}",
            description=f"Inventory deduction for {order_qty} x {menu_item.name}",
            status=EntryStatus.POSTED,
        )
        session.add(journal_entry)
        session.flush()  # Populates journal_entry.id

        for recipe in recipes:
            required_amount = recipe.quantity_required * order_qty
            ingredient = session.get(RawInventory, recipe.ingredient_id)

            if not ingredient:
                raise InventoryError(f"Ingredient id {recipe.ingredient_id} not found.")

            # Validate sufficient inventory
            if ingredient.quantity_on_hand < required_amount:
                raise InsufficientInventoryError(
                    f"Insufficient stock for '{ingredient.name}' (SKU: {ingredient.sku}). "
                    f"Required: {required_amount} {recipe.unit_of_measure}, "
                    f"Available: {ingredient.quantity_on_hand} {ingredient.unit_of_measure}."
                )

            # Deduct stock on hand
            ingredient.quantity_on_hand -= required_amount

            # Calculate cost impact
            cost_deduction = round(required_amount * ingredient.unit_cost, 2)

            # Record negative deduction into Transaction Lines for raw inventory ledger
            line = TransactionLine(
                journal_entry_id=journal_entry.id,
                account_code="1200-RAW-INVENTORY",
                account_name="Raw Inventory Ledger",
                entry_type=EntryType.CREDIT,
                amount=-abs(cost_deduction),  # Negative deduction recorded
                memo=(
                    f"Deducted {required_amount} {recipe.unit_of_measure} of {ingredient.name} "
                    f"for menu item {menu_item.name}"
                ),
                menu_item_id=menu_item.id,
                inventory_id=ingredient.id,
            )
            session.add(line)

        session.commit()
        session.refresh(journal_entry)
        return journal_entry

    except Exception:
        session.rollback()
        raise
