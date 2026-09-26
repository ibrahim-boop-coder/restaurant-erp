from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    Numeric,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
import enum


class Base(DeclarativeBase):
    pass


class EntryType(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class EntryStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    VOIDED = "VOIDED"


class RawInventory(Base):
    __tablename__ = "raw_inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g., kg, g, liter, unit
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0000"), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0000"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    recipes: Mapped[List["Recipe"]] = relationship("Recipe", back_populates="ingredient", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RawInventory id={self.id} sku='{self.sku}' name='{self.name}'>"


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    recipes: Mapped[List["Recipe"]] = relationship("Recipe", back_populates="menu_item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} item_code='{self.item_code}' name='{self.name}'>"


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("raw_inventory.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="recipes")
    ingredient: Mapped["RawInventory"] = relationship("RawInventory", back_populates="recipes")

    def __repr__(self) -> str:
        return (
            f"<Recipe menu_item_id={self.menu_item_id} "
            f"ingredient_id={self.ingredient_id} qty={self.quantity_required}>"
        )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_number: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[EntryStatus] = mapped_column(
        SQLEnum(EntryStatus), default=EntryStatus.POSTED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    lines: Mapped[List["TransactionLine"]] = relationship(
        "TransactionLine", back_populates="journal_entry", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<JournalEntry id={self.id} entry_number='{self.entry_number}'>"


class TransactionLine(Base):
    __tablename__ = "transaction_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_type: Mapped[EntryType] = mapped_column(SQLEnum(EntryType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    memo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Optional references for cost/sales allocation
    menu_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("menu_items.id", ondelete="SET NULL"), nullable=True
    )
    inventory_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("raw_inventory.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    journal_entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    menu_item: Mapped[Optional["MenuItem"]] = relationship("MenuItem")
    inventory: Mapped[Optional["RawInventory"]] = relationship("RawInventory")

    def __repr__(self) -> str:
        return (
            f"<TransactionLine id={self.id} entry_id={self.journal_entry_id} "
            f"account='{self.account_code}' type='{self.entry_type}' amount={self.amount}>"
        )
