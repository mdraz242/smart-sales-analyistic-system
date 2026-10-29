from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)  # WooCommerce Customer ID (0 for guests)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    email_hash = Column(String(64), nullable=True, index=True)  # SHA-256 for pseudonymous analysis
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    username = Column(String(100), nullable=True)
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(100), nullable=True)
    billing_country = Column(String(10), nullable=True)
    billing_postcode = Column(String(30), nullable=True)
    orders_count = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    created_at_utc = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    store = relationship("Store", back_populates="customers")
    orders = relationship("Order", back_populates="customer")
