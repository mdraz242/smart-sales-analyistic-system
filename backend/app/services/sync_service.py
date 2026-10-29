import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.store import Store
from backend.app.models.product import Product, ProductCategory, ProductCategoryMapping, ProductVariation
from backend.app.models.customer import Customer
from backend.app.models.order import Order, OrderItem, Refund, RefundItem, OrderCoupon
from backend.app.models.sync import SyncLog
from backend.app.services.woocommerce_client import WooCommerceClient, WooCommerceAPIError

logger = logging.getLogger("sync_service")


def parse_wc_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parses WooCommerce ISO 8601 UTC date string into aware datetime."""
    if not date_str:
        return None
    try:
        # e.g. 2026-03-24T18:25:43 or 2026-03-24T18:25:43Z
        clean_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class SyncService:
    def __init__(self, db: Session, store: Store):
        self.db = db
        self.store = store
        self.client = WooCommerceClient(
            store_url=store.store_url,
            consumer_key=store.consumer_key,
            consumer_secret=store.consumer_secret
        )

    def run_sync(self, sync_type: str = "incremental") -> SyncLog:
        """Executes full or incremental synchronization of products, categories, customers, and orders."""
        log = SyncLog(
            store_id=self.store.id,
            sync_type=sync_type,
            status="running",
            started_at=datetime.now(timezone.utc),
            records_fetched=0,
            records_inserted=0,
            records_updated=0
        )
        self.db.add(log)
        self.db.commit()

        try:
            logger.info("Starting %s sync for store %s", sync_type, self.store.name)

            # 1. Categories
            cat_fetched = self._sync_categories()
            log.records_fetched += cat_fetched

            # 2. Products
            prod_fetched = self._sync_products(sync_type)
            log.records_fetched += prod_fetched

            # 3. Customers
            cust_fetched = self._sync_customers(sync_type)
            log.records_fetched += cust_fetched

            # 4. Orders & Line Items & Refunds
            ord_fetched, inserted, updated = self._sync_orders(sync_type)
            log.records_fetched += ord_fetched
            log.records_inserted += inserted
            log.records_updated += updated

            # Mark log success
            log.status = "success"
            log.completed_at = datetime.now(timezone.utc)
            self.store.last_sync_at = log.completed_at
            self.db.commit()
            logger.info("Sync completed successfully: %d fetched, %d inserted, %d updated",
                        log.records_fetched, log.records_inserted, log.records_updated)

        except Exception as exc:
            self.db.rollback()
            log.status = "failed"
            log.error_message = str(exc)
            log.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.error("Sync failed with error: %s", str(exc), exc_info=True)

        return log

    def _sync_categories(self) -> int:
        raw_cats = self.client.fetch_paginated("products/categories")
        for c in raw_cats:
            cat_id = int(c["id"])
            existing = self.db.query(ProductCategory).filter(
                ProductCategory.id == cat_id,
                ProductCategory.store_id == self.store.id
            ).first()

            if not existing:
                cat = ProductCategory(
                    id=cat_id,
                    store_id=self.store.id,
                    name=c.get("name", "Unnamed Category"),
                    slug=c.get("slug"),
                    parent_id=c.get("parent", 0),
                    count=c.get("count", 0)
                )
                self.db.add(cat)
            else:
                existing.name = c.get("name", existing.name)
                existing.slug = c.get("slug", existing.slug)
                existing.count = c.get("count", existing.count)
        self.db.commit()
        return len(raw_cats)

    def _sync_products(self, sync_type: str) -> int:
        params = {}
        if sync_type == "incremental" and self.store.last_sync_at:
            params["modified_after"] = self.store.last_sync_at.isoformat()

        raw_prods = self.client.fetch_paginated("products", params=params)
        for p in raw_prods:
            prod_id = int(p["id"])
            existing = self.db.query(Product).filter(
                Product.id == prod_id,
                Product.store_id == self.store.id
            ).first()

            reg_price = float(p.get("regular_price") or 0.0) if p.get("regular_price") != "" else 0.0
            sale_price = float(p.get("sale_price") or 0.0) if p.get("sale_price") != "" else None
            stock_qty = p.get("stock_quantity")

            if not existing:
                prod = Product(
                    id=prod_id,
                    store_id=self.store.id,
                    name=p.get("name", "Product"),
                    slug=p.get("slug"),
                    sku=p.get("sku") or None,
                    type=p.get("type", "simple"),
                    status=p.get("status", "publish"),
                    regular_price=reg_price,
                    sale_price=sale_price,
                    stock_quantity=stock_qty,
                    stock_status=p.get("stock_status", "instock"),
                    manage_stock=bool(p.get("manage_stock", False)),
                    total_sales=int(p.get("total_sales") or 0),
                    average_rating=float(p.get("average_rating") or 0.0),
                    rating_count=int(p.get("rating_count") or 0),
                    created_at_utc=parse_wc_datetime(p.get("date_created_gmt")) or datetime.now(timezone.utc),
                    updated_at_utc=parse_wc_datetime(p.get("date_modified_gmt")) or datetime.now(timezone.utc)
                )
                self.db.add(prod)
                self.db.flush()

                # Add Category Mappings
                for c in p.get("categories", []):
                    cat_id = int(c["id"])
                    mapping = ProductCategoryMapping(product_id=prod.id, category_id=cat_id)
                    self.db.merge(mapping)
            else:
                existing.name = p.get("name", existing.name)
                existing.sku = p.get("sku") or existing.sku
                existing.regular_price = reg_price
                existing.sale_price = sale_price
                existing.stock_quantity = stock_qty
                existing.stock_status = p.get("stock_status", existing.stock_status)
                existing.total_sales = int(p.get("total_sales") or existing.total_sales)
                existing.updated_at_utc = parse_wc_datetime(p.get("date_modified_gmt")) or datetime.now(timezone.utc)

        self.db.commit()
        return len(raw_prods)

    def _sync_customers(self, sync_type: str) -> int:
        params = {}
        if sync_type == "incremental" and self.store.last_sync_at:
            params["modified_after"] = self.store.last_sync_at.isoformat()

        raw_customers = self.client.fetch_paginated("customers", params=params)
        for c in raw_customers:
            cust_id = int(c["id"])
            if cust_id == 0:
                continue

            existing = self.db.query(Customer).filter(
                Customer.id == cust_id,
                Customer.store_id == self.store.id
            ).first()

            email = c.get("email")
            email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest() if email else None
            billing = c.get("billing", {})

            if not existing:
                cust = Customer(
                    id=cust_id,
                    store_id=self.store.id,
                    email=email,
                    email_hash=email_hash,
                    first_name=c.get("first_name"),
                    last_name=c.get("last_name"),
                    username=c.get("username"),
                    billing_city=billing.get("city"),
                    billing_state=billing.get("state"),
                    billing_country=billing.get("country"),
                    billing_postcode=billing.get("postcode"),
                    orders_count=int(c.get("orders_count") or 0),
                    total_spent=float(c.get("total_spent") or 0.0),
                    created_at_utc=parse_wc_datetime(c.get("date_created_gmt")) or datetime.now(timezone.utc)
                )
                self.db.add(cust)
            else:
                existing.first_name = c.get("first_name", existing.first_name)
                existing.last_name = c.get("last_name", existing.last_name)
                existing.billing_city = billing.get("city", existing.billing_city)
                existing.billing_country = billing.get("country", existing.billing_country)
                existing.orders_count = int(c.get("orders_count") or existing.orders_count)
                existing.total_spent = float(c.get("total_spent") or existing.total_spent)

        self.db.commit()
        return len(raw_customers)

    def _sync_orders(self, sync_type: str) -> Tuple[int, int, int]:
        params = {}
        if sync_type == "incremental" and self.store.last_sync_at:
            params["modified_after"] = self.store.last_sync_at.isoformat()

        raw_orders = self.client.fetch_paginated("orders", params=params)
        inserted = 0
        updated = 0

        for o in raw_orders:
            order_id = int(o["id"])
            existing = self.db.query(Order).filter(
                Order.id == order_id,
                Order.store_id == self.store.id
            ).first()

            total_amount = float(o.get("total") or 0.0)
            discount_total = float(o.get("discount_total") or 0.0)
            shipping_total = float(o.get("shipping_total") or 0.0)
            total_tax = float(o.get("total_tax") or 0.0)
            shipping_tax = float(o.get("shipping_tax") or 0.0)
            refund_amount = sum(abs(float(r.get("total") or 0.0)) for r in o.get("refunds", []))

            # Calculated Net Sales
            items_subtotal = sum(float(it.get("subtotal") or 0.0) for it in o.get("line_items", []))
            net_sales = max(0.0, items_subtotal - discount_total - refund_amount)

            billing = o.get("billing", {})
            shipping = o.get("shipping_lines", [{}])
            shipping_method = shipping[0].get("method_title") if shipping else None

            created_utc = parse_wc_datetime(o.get("date_created_gmt")) or datetime.now(timezone.utc)
            modified_utc = parse_wc_datetime(o.get("date_modified_gmt"))
            completed_utc = parse_wc_datetime(o.get("date_completed_gmt"))
            paid_utc = parse_wc_datetime(o.get("date_paid_gmt"))

            cust_id = int(o.get("customer_id") or 0)
            cust_ref = cust_id if cust_id > 0 else None

            if not existing:
                order = Order(
                    id=order_id,
                    store_id=self.store.id,
                    customer_id=cust_ref,
                    order_number=str(o.get("number", order_id)),
                    status=o.get("status", "pending"),
                    currency=o.get("currency", "USD"),
                    total_amount=total_amount,
                    discount_total=discount_total,
                    shipping_total=shipping_total,
                    total_tax=total_tax,
                    shipping_tax=shipping_tax,
                    total_refunded=refund_amount,
                    net_sales=net_sales,
                    payment_method=o.get("payment_method"),
                    payment_method_title=o.get("payment_method_title"),
                    shipping_method=shipping_method,
                    billing_city=billing.get("city"),
                    billing_state=billing.get("state"),
                    billing_country=billing.get("country"),
                    billing_postcode=billing.get("postcode"),
                    customer_ip=o.get("customer_ip_address"),
                    date_created_utc=created_utc,
                    date_modified_utc=modified_utc,
                    date_completed_utc=completed_utc,
                    date_paid_utc=paid_utc
                )
                self.db.add(order)
                self.db.flush()
                inserted += 1

                # Line Items
                for it in o.get("line_items", []):
                    item_id = int(it["id"])
                    line_item = OrderItem(
                        id=item_id,
                        order_id=order.id,
                        product_id=int(it["product_id"]) if it.get("product_id") else None,
                        variation_id=int(it["variation_id"]) if it.get("variation_id") else None,
                        name=it.get("name", "Product Item"),
                        sku=it.get("sku") or None,
                        quantity=int(it.get("quantity") or 1),
                        unit_price=float(it.get("price") or 0.0),
                        subtotal=float(it.get("subtotal") or 0.0),
                        total=float(it.get("total") or 0.0),
                        subtotal_tax=float(it.get("subtotal_tax") or 0.0),
                        total_tax=float(it.get("total_tax") or 0.0)
                    )
                    self.db.merge(line_item)

                # Coupons
                for cp in o.get("coupon_lines", []):
                    coupon = OrderCoupon(
                        order_id=order.id,
                        code=cp.get("code", "COUPON"),
                        discount_amount=float(cp.get("discount") or 0.0),
                        discount_tax=float(cp.get("discount_tax") or 0.0)
                    )
                    self.db.add(coupon)

                # Refunds
                for rf in o.get("refunds", []):
                    ref_id = int(rf["id"])
                    refund = Refund(
                        id=ref_id,
                        order_id=order.id,
                        amount=abs(float(rf.get("total") or 0.0)),
                        reason=rf.get("reason"),
                        date_created_utc=created_utc
                    )
                    self.db.merge(refund)

            else:
                existing.status = o.get("status", existing.status)
                existing.total_amount = total_amount
                existing.discount_total = discount_total
                existing.total_refunded = refund_amount
                existing.net_sales = net_sales
                existing.date_modified_utc = modified_utc
                existing.date_completed_utc = completed_utc
                updated += 1

        self.db.commit()
        return len(raw_orders), inserted, updated
