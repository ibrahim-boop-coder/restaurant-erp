from contextlib import asynccontextmanager
from typing import Generator
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models import Base, engine, SessionLocal
from backend.inventory_service import (
    process_order_deduction,
    MenuItemNotFoundError,
    InsufficientInventoryError,
    InventoryError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Restaurant ERP API",
    version="1.0.0",
    lifespan=lifespan,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class OrderDeductionRequest(BaseModel):
    menu_item_id: int = Field(..., gt=0, description="ID of the menu item ordered")
    quantity: float = Field(..., gt=0, description="Quantity ordered")


class OrderDeductionResponse(BaseModel):
    message: str
    journal_entry_id: int
    entry_number: str
    reference: str | None


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Restaurant ERP"}


@app.post("/inventory/deduct-order", response_model=OrderDeductionResponse, status_code=status.HTTP_200_OK)
def deduct_order_inventory(
    payload: OrderDeductionRequest,
    db: Session = Depends(get_db),
):
    try:
        entry = process_order_deduction(
            session=db,
            menu_item_id=payload.menu_item_id,
            quantity=payload.quantity,
        )
        return OrderDeductionResponse(
            message="Inventory successfully deducted.",
            journal_entry_id=entry.id,
            entry_number=entry.entry_number,
            reference=entry.reference,
        )
    except MenuItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InsufficientInventoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InventoryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {exc}")
