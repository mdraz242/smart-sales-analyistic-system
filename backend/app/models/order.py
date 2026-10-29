from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)  # WooCommerce Order ID
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    order_number = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, index=True)  # completed, processing, on-hold, pending, cancelled, refunded, failed
    currency = Column(String(10), nullable=False, default="USD")
    
    # Financial fields
    total_amount = Column(Float, nullable=False, default=0.0)  # total charge to customer
    discount_total = Column(Float, nullable=False, default=0.0)
    shipping_total = Column(Float, nullable=False, default=0.0)
    total_tax = Column(Float, nullable=False, default=0.0)
    shipping_tax = Column(Float, nullable=False, default=0.0)
    total_refunded = Column(Float, nullable=False, default=0.0)
    net_sales = Column(Float, nullable=False, default=0.0)  # gross - discounts - refunds (calculated & cached)

    # Fulfillment & Payment
    payment_method = Column(String(100), nullable=True)
    payment_method_title = Column(String(255), nullable=True)
    shipping_method = Column(String(255), nullable=True)
    
    # Geolocation / Customer Demographics
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(100), nullable=True)
    billing_country = Column(String(10), nullable=True, index=True)
    billing_postcode = Column(String(30), nullable=True)
    customer_ip = Column(String(50), nullable=True)

    # Timestamps (Stored in UTC)
    date_created_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    date_modified_utc = Column(DateTime(timezone=True), nullable=True)
    date_completed_utc = Column(DateTime(timezone=True), nullable=True)
    date_paid_utc = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    store = relationship("Store", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="order", cascade="all, delete-orphan")
    coupons = relationship("OrderCoupon", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)  # WooCommerce Line Item ID
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    variation_id = Column(Integer, nullable=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=True, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    subtotal = Column(Float, nullable=False, default=0.0)  # price * qty before discount
    total = Column(Float, nullable=False, default=0.0)     # after line discount
    subtotal_tax = Column(Float, default=0.0)
    total_tax = Column(Float, default=0.0)

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    refund_items = relationship("RefundItem", back_populates="order_item")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True)  # WooCommerce Refund ID
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False, default=0.0)
    reason = Column(Text, nullable=True)
    date_created_utc = Column(DateTime(timezone=True), nullable=False, index=True)

    order = relationship("Order", back_populates="refunds")
    items = relationship("RefundItem", back_populates="refund", cascade="all, delete-orphan")


class RefundItem(Base):
    __tablename__ = "refund_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    refund_id = Column(Integer, ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity = Column(Integer, default=0)
    refund_subtotal = Column(Float, default=0.0)
    refund_total = Column(Float, default=0.0)

    refund = relationship("Refund", back_populates="items")
    order_item = relationship("OrderItem", back_populates="refund_items")


class OrderCoupon(Base):
    __tablename__ = "order_coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(100), nullable=False, index=True)
    discount_amount = Column(Float, nullable=False, default=0.0)
    discount_tax = Column(Float, default=0.0)

    order = relationship("Order", back_populates="coupons")
