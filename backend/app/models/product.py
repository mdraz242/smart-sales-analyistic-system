from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True)  # WooCommerce Category ID
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=True)
    parent_id = Column(Integer, nullable=True, default=0)
    count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    products = relationship("ProductCategoryMapping", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)  # WooCommerce Product ID
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=True)
    sku = Column(String(100), nullable=True, index=True)
    type = Column(String(50), default="simple")  # simple, variable, grouped, external
    status = Column(String(50), default="publish")  # publish, draft, pending, private
    regular_price = Column(Float, default=0.0)
    sale_price = Column(Float, nullable=True)
    current_cost = Column(Float, nullable=True)  # Unit cost (COGS)
    stock_quantity = Column(Integer, nullable=True)
    stock_status = Column(String(50), default="instock")  # instock, outofstock, onbackorder
    manage_stock = Column(Boolean, default=False)
    total_sales = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    created_at_utc = Column(DateTime(timezone=True), default=utc_now)
    updated_at_utc = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    store = relationship("Store", back_populates="products")
    variations = relationship("ProductVariation", back_populates="product", cascade="all, delete-orphan")
    categories = relationship("ProductCategoryMapping", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")
    costs = relationship("ProductCostHistory", back_populates="product", cascade="all, delete-orphan")
    inventory_snapshots = relationship("InventorySnapshot", back_populates="product", cascade="all, delete-orphan")


class ProductVariation(Base):
    __tablename__ = "product_variations"

    id = Column(Integer, primary_key=True)  # WooCommerce Variation ID
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=True, index=True)
    price = Column(Float, default=0.0)
    regular_price = Column(Float, default=0.0)
    sale_price = Column(Float, nullable=True)
    stock_quantity = Column(Integer, nullable=True)
    stock_status = Column(String(50), default="instock")
    attributes_json = Column(Text, nullable=True)  # e.g. {"Size": "L", "Color": "Blue"}
    created_at_utc = Column(DateTime(timezone=True), default=utc_now)

    product = relationship("Product", back_populates="variations")


class ProductCategoryMapping(Base):
    __tablename__ = "product_category_mappings"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(Integer, ForeignKey("product_categories.id", ondelete="CASCADE"), primary_key=True)

    product = relationship("Product", back_populates="categories")
    category = relationship("ProductCategory", back_populates="products")


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=True)
    stock_quantity = Column(Integer, default=0)
    snapshot_date = Column(DateTime(timezone=True), default=utc_now, index=True)

    product = relationship("Product", back_populates="inventory_snapshots")
