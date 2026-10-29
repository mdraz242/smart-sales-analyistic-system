from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ProductCostHistory(Base):
    __tablename__ = "product_cost_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=True, index=True)
    unit_cost = Column(Float, nullable=False, default=0.0)
    effective_date = Column(DateTime(timezone=True), default=utc_now, index=True)
    source = Column(String(50), default="manual")  # manual, csv_import, api
    notes = Column(String(255), nullable=True)

    product = relationship("Product", back_populates="costs")
