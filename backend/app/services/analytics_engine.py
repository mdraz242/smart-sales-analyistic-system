from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, distinct

from backend.app.models.order import Order, OrderItem, Refund, RefundItem, OrderCoupon
from backend.app.models.product import Product, ProductCategory, ProductCategoryMapping, ProductVariation
from backend.app.models.customer import Customer
from backend.app.models.cost import ProductCostHistory
from backend.app.utils.currency import format_currency, format_percentage
from backend.app.schemas.analytics import MetricSummary, ExecutiveKPIDashboard, ProductRankItem


# Valid completed revenue statuses in WooCommerce
VALID_ORDER_STATUSES = ["completed", "processing"]


class AnalyticsEngine:
    def __init__(self, db: Session, store_id: Optional[int] = None):
        self.db = db
        self.store_id = store_id

    def _apply_store_filter(self, query, model_class):
        if self.store_id is not None and hasattr(model_class, "store_id"):
            return query.filter(model_class.store_id == self.store_id)
        return query

    # =========================================================================
    # 1. EXECUTIVE KPI DASHBOARD
    # =========================================================================
    def calculate_period_metrics(
        self,
        start_utc: datetime,
        end_utc: datetime,
        category_id: Optional[int] = None,
        product_id: Optional[int] = None,
        order_status: Optional[str] = None,
        coupon_code: Optional[str] = None,
        customer_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates accurate aggregate financial & transactional metrics for a given time window."""
        
        # Build base order query
        order_query = self.db.query(Order).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc
        )
        if self.store_id is not None:
            order_query = order_query.filter(Order.store_id == self.store_id)

        all_orders = order_query.all()
        total_placed_orders_count = len(all_orders)

        # Filter by status
        if order_status and order_status.lower() != "all":
            valid_orders = [o for o in all_orders if o.status.lower() == order_status.lower()]
        else:
            valid_orders = [o for o in all_orders if o.status.lower() in VALID_ORDER_STATUSES]

        cancelled_failed_count = sum(1 for o in all_orders if o.status.lower() in ["cancelled", "failed"])

        valid_order_ids = [o.id for o in valid_orders]

        # Filter items for these orders
        if not valid_order_ids:
            return {
                "gross_sales": 0.0,
                "discounts": 0.0,
                "refunds": 0.0,
                "net_sales": 0.0,
                "shipping_revenue": 0.0,
                "tax_collected": 0.0,
                "total_revenue_collected": 0.0,
                "total_orders": 0,
                "units_sold": 0,
                "aov": 0.0,
                "cancellation_rate": (cancelled_failed_count / total_placed_orders_count * 100) if total_placed_orders_count > 0 else 0.0,
                "refund_rate": 0.0,
                "unique_customers": 0,
                "new_customers": 0,
                "returning_customers": 0,
                "total_placed_orders_count": total_placed_orders_count
            }

        # Query OrderItems with product filters if specified
        item_query = self.db.query(OrderItem).filter(OrderItem.order_id.in_(valid_order_ids))
        if product_id:
            item_query = item_query.filter(OrderItem.product_id == product_id)
        if category_id:
            cat_product_ids = [
                m.product_id for m in self.db.query(ProductCategoryMapping.product_id)
                .filter(ProductCategoryMapping.category_id == category_id).all()
            ]
            item_query = item_query.filter(OrderItem.product_id.in_(cat_product_ids))

        order_items = item_query.all()

        # Gross sales: sum of line item subtotal (before coupon discount)
        gross_sales = sum(item.subtotal for item in order_items)
        # Line item discount total
        item_discounts = sum(item.subtotal - item.total for item in order_items)

        # Order level shipping and tax
        shipping_revenue = sum(o.shipping_total for o in valid_orders)
        tax_collected = sum(o.total_tax + o.shipping_tax for o in valid_orders)
        order_discounts = sum(o.discount_total for o in valid_orders)
        total_discounts = max(item_discounts, order_discounts)

        # Refunds for these orders
        refund_query = self.db.query(Refund).filter(Refund.order_id.in_(valid_order_ids))
        refunds = refund_query.all()
        total_refunds = sum(r.amount for r in refunds)

        # Line item refunded units
        refund_items = self.db.query(RefundItem).filter(
            RefundItem.refund_id.in_([r.id for r in refunds])
        ).all()
        refunded_units = sum(ri.quantity for ri in refund_items)

        gross_units = sum(item.quantity for item in order_items)
        net_units_sold = max(0, gross_units - refunded_units)

        # Net sales = Gross Sales - Discounts - Refunds
        net_sales = max(0.0, gross_sales - total_discounts - total_refunds)
        total_orders_count = len(valid_orders)
        aov = (net_sales / total_orders_count) if total_orders_count > 0 else 0.0

        # Total revenue collected = Net Sales + Shipping + Tax
        total_revenue_collected = net_sales + shipping_revenue + tax_collected

        cancellation_rate = (cancelled_failed_count / total_placed_orders_count * 100) if total_placed_orders_count > 0 else 0.0
        refund_rate = (total_refunds / gross_sales * 100) if gross_sales > 0 else 0.0

        # Customer breakdown: new vs returning
        customer_ids = [o.customer_id for o in valid_orders if o.customer_id is not None]
        unique_customers = len(set(customer_ids))

        # Check how many of these customers placed their first order before start_utc
        new_customers = 0
        returning_customers = 0
        if customer_ids:
            first_orders = self.db.query(
                Order.customer_id,
                func.min(Order.date_created_utc).label("first_order_date")
            ).filter(
                Order.customer_id.in_(list(set(customer_ids))),
                Order.status.in_(VALID_ORDER_STATUSES)
            ).group_by(Order.customer_id).all()

            for cust_id, first_date in first_orders:
                # Ensure timezone aware comparison
                if first_date.tzinfo is None:
                    first_date = first_date.replace(tzinfo=timezone.utc)
                if first_date >= start_utc:
                    new_customers += 1
                else:
                    returning_customers += 1

        return {
            "gross_sales": round(gross_sales, 2),
            "discounts": round(total_discounts, 2),
            "refunds": round(total_refunds, 2),
            "net_sales": round(net_sales, 2),
            "shipping_revenue": round(shipping_revenue, 2),
            "tax_collected": round(tax_collected, 2),
            "total_revenue_collected": round(total_revenue_collected, 2),
            "total_orders": total_orders_count,
            "units_sold": net_units_sold,
            "aov": round(aov, 2),
            "cancellation_rate": round(cancellation_rate, 2),
            "refund_rate": round(refund_rate, 2),
            "unique_customers": unique_customers,
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "total_placed_orders_count": total_placed_orders_count
        }

    def get_executive_kpis(
        self,
        start_utc: datetime,
        end_utc: datetime,
        prev_start_utc: datetime,
        prev_end_utc: datetime,
        category_id: Optional[int] = None,
        product_id: Optional[int] = None,
        order_status: Optional[str] = None,
        coupon_code: Optional[str] = None,
        customer_type: Optional[str] = None,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Calculates executive dashboard KPIs with period-over-period comparisons."""

        cur = self.calculate_period_metrics(
            start_utc, end_utc, category_id, product_id, order_status, coupon_code, customer_type
        )
        prev = self.calculate_period_metrics(
            prev_start_utc, prev_end_utc, category_id, product_id, order_status, coupon_code, customer_type
        )

        def make_summary(key: str, is_currency: bool, is_percentage: bool, definition: str, invert_trend: bool = False):
            c_val = cur.get(key, 0.0)
            p_val = prev.get(key, 0.0)
            delta_abs = c_val - p_val
            if p_val != 0:
                delta_pct = (delta_abs / abs(p_val)) * 100
            else:
                delta_pct = 100.0 if c_val > 0 else 0.0

            if is_currency:
                f_cur = format_currency(c_val, currency)
                f_prev = format_currency(p_val, currency)
            elif is_percentage:
                f_cur = f"{c_val:.1f}%"
                f_prev = f"{p_val:.1f}%"
            else:
                f_cur = f"{int(c_val):,}" if isinstance(c_val, (int, np.integer)) or c_val.is_integer() else f"{c_val:,.1f}"
                f_prev = f"{int(p_val):,}" if isinstance(p_val, (int, np.integer)) or p_val.is_integer() else f"{p_val:,.1f}"

            # Trend direction
            if delta_pct > 0:
                trend = "negative" if invert_trend else "positive"
            elif delta_pct < 0:
                trend = "positive" if invert_trend else "negative"
            else:
                trend = "neutral"

            return {
                "current": c_val,
                "previous": p_val,
                "delta_abs": round(delta_abs, 2),
                "delta_pct": round(delta_pct, 1),
                "formatted_current": f_cur,
                "formatted_previous": f_prev,
                "trend": trend,
                "definition": definition
            }

        sales_growth_val = ((cur["net_sales"] - prev["net_sales"]) / prev["net_sales"] * 100) if prev["net_sales"] > 0 else 0.0

        return {
            "gross_sales": make_summary(
                "gross_sales", True, False,
                "Total item subtotal value before discounts, taxes, or shipping for completed/processing orders."
            ),
            "net_sales": make_summary(
                "net_sales", True, False,
                "Gross sales minus all discounts, coupons, and customer refunds."
            ),
            "revenue_collected": make_summary(
                "total_revenue_collected", True, False,
                "Total settled revenue: Net Sales plus shipping fees and sales tax collected."
            ),
            "total_orders": make_summary(
                "total_orders", False, False,
                "Total count of successful B2C orders (completed or processing status)."
            ),
            "units_sold": make_summary(
                "units_sold", False, False,
                "Net quantity of merchandise units sold (gross units minus returned/refunded units)."
            ),
            "average_order_value": make_summary(
                "aov", True, False,
                "Average net revenue per successful order (Net Sales divided by Total Orders)."
            ),
            "total_discounts": make_summary(
                "discounts", True, False,
                "Cumulative value of promotional coupons and item discounts granted.",
                invert_trend=True
            ),
            "total_refunds": make_summary(
                "refunds", True, False,
                "Total value of customer refunds issued against completed/processing orders.",
                invert_trend=True
            ),
            "tax_collected": make_summary(
                "tax_collected", True, False,
                "Sales and value-added tax collected on products and shipping."
            ),
            "shipping_revenue": make_summary(
                "shipping_revenue", True, False,
                "Total shipping and freight charges billed to customers."
            ),
            "unique_customers": make_summary(
                "unique_customers", False, False,
                "Count of distinct customer accounts or pseudonymous guests who ordered."
            ),
            "new_customers": make_summary(
                "new_customers", False, False,
                "Customers whose very first store order occurred during this period."
            ),
            "returning_customers": make_summary(
                "returning_customers", False, False,
                "Customers who had already purchased at least once prior to this period."
            ),
            "cancellation_rate": make_summary(
                "cancellation_rate", False, True,
                "Percentage of total placed orders that were cancelled or failed.",
                invert_trend=True
            ),
            "refund_rate": make_summary(
                "refund_rate", False, True,
                "Total refund value divided by Gross Sales as a percentage.",
                invert_trend=True
            ),
            "sales_growth_pct": {
                "current": round(sales_growth_val, 1),
                "previous": 0.0,
                "delta_abs": round(sales_growth_val, 1),
                "delta_pct": round(sales_growth_val, 1),
                "formatted_current": f"{'+' if sales_growth_val > 0 else ''}{sales_growth_val:.1f}%",
                "formatted_previous": "Baseline",
                "trend": "positive" if sales_growth_val >= 0 else "negative",
                "definition": "Period-over-period Net Sales growth percentage compared to the previous equivalent period."
            },
            "currency": currency,
            "period_start": start_utc,
            "period_end": end_utc,
            "previous_period_start": prev_start_utc,
            "previous_period_end": prev_end_utc
        }

    # =========================================================================
    # 2. PRODUCT PERFORMANCE INTELLIGENCE
    # =========================================================================
    def get_product_performance(
        self,
        start_utc: datetime,
        end_utc: datetime,
        prev_start_utc: datetime,
        prev_end_utc: datetime,
        rank_by: str = "units_sold",  # units_sold, net_sales, gross_sales, orders_count, growth_pct
        limit: int = 20,
        category_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Calculates product rankings, profitability, and classification."""
        
        # 1. Fetch current period items
        cur_order_ids = [
            o.id for o in self.db.query(Order.id).filter(
                Order.date_created_utc >= start_utc,
                Order.date_created_utc <= end_utc,
                Order.status.in_(VALID_ORDER_STATUSES)
            ).all()
        ]
        
        # 2. Fetch previous period items for comparison
        prev_order_ids = [
            o.id for o in self.db.query(Order.id).filter(
                Order.date_created_utc >= prev_start_utc,
                Order.date_created_utc <= prev_end_utc,
                Order.status.in_(VALID_ORDER_STATUSES)
            ).all()
        ]

        if not cur_order_ids:
            return []

        # Current period order items
        cur_items_query = self.db.query(OrderItem).filter(OrderItem.order_id.in_(cur_order_ids))
        cur_items = cur_items_query.all()

        # Previous period order items
        prev_items = self.db.query(OrderItem).filter(OrderItem.order_id.in_(prev_order_ids)).all() if prev_order_ids else []

        # Current refunds mapping
        refund_query = self.db.query(
            RefundItem.product_id,
            func.sum(RefundItem.quantity).label("ref_qty"),
            func.sum(RefundItem.refund_total).label("ref_total")
        ).join(Refund, RefundItem.refund_id == Refund.id).filter(
            Refund.order_id.in_(cur_order_ids)
        ).group_by(RefundItem.product_id).all()

        refund_map = {r.product_id: (r.ref_qty or 0, r.ref_total or 0.0) for r in refund_query}

        # Products metadata & current costs
        products_query = self.db.query(Product)
        if self.store_id:
            products_query = products_query.filter(Product.store_id == self.store_id)
        products_dict = {p.id: p for p in products_query.all()}

        # Category mapping
        cat_mappings = self.db.query(
            ProductCategoryMapping.product_id,
            ProductCategory.name
        ).join(ProductCategory, ProductCategoryMapping.category_id == ProductCategory.id).all()
        cat_map = {}
        for pid, cname in cat_mappings:
            if pid not in cat_map:
                cat_map[pid] = []
            cat_map[pid].append(cname)

        # Aggregate current period by product
        cur_agg = {}
        for item in cur_items:
            pid = item.product_id or 0
            if pid not in cur_agg:
                cur_agg[pid] = {
                    "product_id": pid,
                    "name": item.name,
                    "sku": item.sku or "N/A",
                    "gross_sales": 0.0,
                    "discounts": 0.0,
                    "gross_units": 0,
                    "orders": set()
                }
            cur_agg[pid]["gross_sales"] += item.subtotal
            cur_agg[pid]["discounts"] += max(0.0, item.subtotal - item.total)
            cur_agg[pid]["gross_units"] += item.quantity
            cur_agg[pid]["orders"].add(item.order_id)

        # Aggregate previous period by product
        prev_agg = {}
        for item in prev_items:
            pid = item.product_id or 0
            if pid not in prev_agg:
                prev_agg[pid] = {"units": 0, "net_sales": 0.0}
            prev_agg[pid]["units"] += item.quantity
            prev_agg[pid]["net_sales"] += item.total

        total_store_net_sales = 0.0
        results = []

        for pid, data in cur_agg.items():
            ref_qty, ref_val = refund_map.get(pid, (0, 0.0))
            net_units = max(0, data["gross_units"] - ref_qty)
            net_sales = max(0.0, data["gross_sales"] - data["discounts"] - ref_val)
            total_store_net_sales += net_sales

            # Product details
            prod = products_dict.get(pid)
            sku = prod.sku if prod and prod.sku else data["sku"]
            cat_str = ", ".join(cat_map.get(pid, ["Uncategorized"]))
            unit_cost = prod.current_cost if prod else None
            stock_qty = prod.stock_quantity if prod else None

            # Previous comparison
            prev_data = prev_agg.get(pid, {"units": 0, "net_sales": 0.0})
            p_units = prev_data["units"]
            p_net = prev_data["net_sales"]
            growth_pct = ((net_units - p_units) / p_units * 100) if p_units > 0 else (100.0 if net_units > 0 else 0.0)

            # Profitability
            cogs = (unit_cost * net_units) if unit_cost is not None else None
            gross_profit = (net_sales - cogs) if cogs is not None else None
            gross_margin_pct = (gross_profit / net_sales * 100) if (gross_profit is not None and net_sales > 0) else None

            asp = (net_sales / net_units) if net_units > 0 else 0.0

            results.append({
                "product_id": pid,
                "name": prod.name if prod else data["name"],
                "sku": sku or "N/A",
                "category": cat_str,
                "units_sold": net_units,
                "orders_count": len(data["orders"]),
                "gross_sales": round(data["gross_sales"], 2),
                "discounts": round(data["discounts"], 2),
                "refunds": round(ref_val, 2),
                "net_sales": round(net_sales, 2),
                "average_selling_price": round(asp, 2),
                "cogs": round(cogs, 2) if cogs is not None else None,
                "gross_profit": round(gross_profit, 2) if gross_profit is not None else None,
                "gross_margin_pct": round(gross_margin_pct, 1) if gross_margin_pct is not None else None,
                "previous_units_sold": p_units,
                "previous_net_sales": round(p_net, 2),
                "growth_pct": round(growth_pct, 1),
                "stock_quantity": stock_qty,
                "refund_rate": round((ref_val / data["gross_sales"] * 100) if data["gross_sales"] > 0 else 0.0, 1),
                "discount_rate": round((data["discounts"] / data["gross_sales"] * 100) if data["gross_sales"] > 0 else 0.0, 1),
            })

        # Calculate % of total net sales
        for r in results:
            r["net_sales_percentage"] = round((r["net_sales"] / total_store_net_sales * 100) if total_store_net_sales > 0 else 0.0, 2)

        # Filter by category if requested
        if category_id:
            cat_obj = self.db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
            if cat_obj:
                results = [r for r in results if cat_obj.name.lower() in r["category"].lower()]

        # Apply classifications
        self._classify_product_list(results, total_store_net_sales)

        # Sort based on rank_by
        sort_keys = {
            "units_sold": ("units_sold", True),
            "net_sales": ("net_sales", True),
            "gross_sales": ("gross_sales", True),
            "orders_count": ("orders_count", True),
            "growth_pct": ("growth_pct", True),
            "gross_profit": ("gross_profit", True),
        }
        key_col, desc = sort_keys.get(rank_by, ("units_sold", True))
        results.sort(key=lambda x: (x.get(key_col) is not None, x.get(key_col) or 0), reverse=desc)

        return results[:limit]

    def _classify_product_list(self, products: List[Dict[str, Any]], total_net_sales: float):
        """Applies 9-class automated performance taxonomy."""
        if not products:
            return

        units_list = [p["units_sold"] for p in products]
        net_list = [p["net_sales"] for p in products]
        
        top_units_thresh = np.percentile(units_list, 80) if units_list else 10
        bottom_units_thresh = np.percentile(units_list, 25) if units_list else 1
        top_rev_thresh = np.percentile(net_list, 80) if net_list else 500

        # Store-wide refund rate average
        total_gross = sum(p["gross_sales"] for p in products)
        total_ref = sum(p["refunds"] for p in products)
        avg_refund_rate = (total_ref / total_gross * 100) if total_gross > 0 else 0.0

        for p in products:
            classes = []
            
            # 1. Best Sellers: high sales volume and high revenue
            if p["units_sold"] >= top_units_thresh and p["net_sales"] >= top_rev_thresh:
                classes.append("Best Seller")
            
            # 2. Rising Stars: strong growth (>=25%) with minimum 5 units
            if p["growth_pct"] >= 25.0 and p["units_sold"] >= 5:
                classes.append("Rising Star")

            # 3. Declining Products: <= -20% unit drop
            if p["growth_pct"] <= -20.0 and p["previous_units_sold"] >= 5:
                classes.append("Declining")

            # 4. Low Performers: bottom volume and revenue
            if p["units_sold"] <= bottom_units_thresh and p["growth_pct"] <= 0:
                classes.append("Low Performer")

            # 5. High Revenue Products: strong sales contribution
            if p["net_sales_percentage"] >= 10.0 or p["net_sales"] >= top_rev_thresh:
                classes.append("High Revenue")

            # 6. High Margin Products: gross margin >= 50%
            if p.get("gross_margin_pct") is not None and p["gross_margin_pct"] >= 50.0:
                classes.append("High Margin")

            # 7. Frequently Refunded: refund rate > 1.5x store average
            if p["refund_rate"] > max(5.0, avg_refund_rate * 1.5) and p["units_sold"] >= 3:
                classes.append("High Refund Risk")

            # 8. Discount Dependent: discount rate >= 25%
            if p["discount_rate"] >= 25.0:
                classes.append("Discount Dependent")

            # 9. Stockout Risk: stock <= 10 and units sold >= 15
            if p.get("stock_quantity") is not None and p["stock_quantity"] <= 10 and p["units_sold"] >= 10:
                classes.append("Stockout Risk")

            if not classes:
                classes.append("Steady")

            p["classification"] = classes[0]
            p["all_classifications"] = classes

    # =========================================================================
    # 3. REVENUE & SALES ANALYTICS
    # =========================================================================
    def get_revenue_time_series(
        self,
        start_utc: datetime,
        end_utc: datetime,
        interval: str = "daily"  # daily, weekly, monthly
    ) -> List[Dict[str, Any]]:
        """Calculates revenue time-series aggregation for line/bar charts."""
        orders = self.db.query(
            Order.date_created_utc,
            Order.net_sales,
            Order.total_amount,
            Order.shipping_total,
            Order.total_tax,
            Order.discount_total,
            Order.status
        ).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc,
            Order.status.in_(VALID_ORDER_STATUSES)
        )
        if self.store_id:
            orders = orders.filter(Order.store_id == self.store_id)
        
        data = orders.all()
        if not data:
            return []

        df = pd.DataFrame([{
            "date": o.date_created_utc,
            "net_sales": o.net_sales,
            "total_revenue": o.total_amount,
            "orders": 1
        } for o in data])

        df["date"] = pd.to_datetime(df["date"], utc=True)

        if interval == "hourly":
            freq = "h"
        elif interval == "weekly":
            freq = "W-MON"
        elif interval == "monthly":
            freq = "ME"
        else:
            freq = "D"

        grouped = df.groupby(pd.Grouper(key="date", freq=freq)).agg({
            "net_sales": "sum",
            "total_revenue": "sum",
            "orders": "sum"
        }).reset_index()

        grouped["date_str"] = grouped["date"].dt.strftime("%Y-%m-%d" if freq == "D" else ("%Y-%m" if freq == "ME" else "%Y-%m-%d"))
        grouped["aov"] = (grouped["net_sales"] / grouped["orders"]).fillna(0).round(2)
        grouped["net_sales"] = grouped["net_sales"].round(2)
        grouped["total_revenue"] = grouped["total_revenue"].round(2)

        return grouped.to_dict(orient="records")

    def get_sales_heatmaps(
        self,
        start_utc: datetime,
        end_utc: datetime
    ) -> Dict[str, Any]:
        """Calculates peak sales hours and days of the week."""
        orders = self.db.query(
            Order.date_created_utc,
            Order.net_sales
        ).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc,
            Order.status.in_(VALID_ORDER_STATUSES)
        )
        if self.store_id:
            orders = orders.filter(Order.store_id == self.store_id)
        
        data = orders.all()
        if not data:
            return {"by_hour": [], "by_weekday": [], "heatmap_matrix": []}

        df = pd.DataFrame([{
            "date": o.date_created_utc,
            "net_sales": o.net_sales
        } for o in data])

        df["date"] = pd.to_datetime(df["date"], utc=True)
        df["hour"] = df["date"].dt.hour
        df["weekday"] = df["date"].dt.day_name()
        df["weekday_num"] = df["date"].dt.weekday

        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        by_hour = df.groupby("hour")["net_sales"].agg(["sum", "count"]).reset_index()
        by_hour.columns = ["hour", "total_sales", "order_count"]

        by_weekday = df.groupby("weekday")["net_sales"].agg(["sum", "count"]).reindex(day_order).fillna(0).reset_index()
        by_weekday.columns = ["weekday", "total_sales", "order_count"]

        # 7x24 Matrix
        matrix = df.pivot_table(
            index="weekday",
            columns="hour",
            values="net_sales",
            aggfunc="sum",
            fill_value=0
        ).reindex(day_order).fillna(0)

        # Fill missing hours 0..23
        for h in range(24):
            if h not in matrix.columns:
                matrix[h] = 0.0
        matrix = matrix[sorted(matrix.columns)]

        return {
            "by_hour": by_hour.to_dict(orient="records"),
            "by_weekday": by_weekday.to_dict(orient="records"),
            "heatmap_matrix": matrix.values.tolist(),
            "heatmap_days": day_order,
            "heatmap_hours": [f"{h:02d}:00" for h in range(24)]
        }

    def get_breakdowns(
        self,
        start_utc: datetime,
        end_utc: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Calculates sales breakdown by payment method, shipping method, coupon, and country."""
        orders = self.db.query(Order).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc,
            Order.status.in_(VALID_ORDER_STATUSES)
        )
        if self.store_id:
            orders = orders.filter(Order.store_id == self.store_id)
        
        all_orders = orders.all()
        if not all_orders:
            return {"payment_methods": [], "shipping_methods": [], "countries": [], "coupons": []}

        # Payment Methods
        pm_map = {}
        sm_map = {}
        geo_map = {}
        for o in all_orders:
            pm = o.payment_method_title or o.payment_method or "Other / Manual"
            pm_map[pm] = pm_map.get(pm, 0.0) + o.net_sales

            sm = o.shipping_method or "Standard Shipping"
            sm_map[sm] = sm_map.get(sm, 0.0) + o.net_sales

            country = o.billing_country or "Unknown"
            geo_map[country] = geo_map.get(country, 0.0) + o.net_sales

        # Coupons
        coupons = self.db.query(
            OrderCoupon.code,
            func.sum(OrderCoupon.discount_amount).label("total_discount"),
            func.count(OrderCoupon.id).label("uses")
        ).join(Order, OrderCoupon.order_id == Order.id).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc,
            Order.status.in_(VALID_ORDER_STATUSES)
        ).group_by(OrderCoupon.code).all()

        return {
            "payment_methods": sorted([{"name": k, "net_sales": round(v, 2)} for k, v in pm_map.items()], key=lambda x: x["net_sales"], reverse=True),
            "shipping_methods": sorted([{"name": k, "net_sales": round(v, 2)} for k, v in sm_map.items()], key=lambda x: x["net_sales"], reverse=True),
            "countries": sorted([{"country": k, "net_sales": round(v, 2)} for k, v in geo_map.items()], key=lambda x: x["net_sales"], reverse=True),
            "coupons": [{"code": c.code, "total_discount": round(c.total_discount, 2), "uses": c.uses} for c in coupons]
        }

    # =========================================================================
    # 4. CATEGORY INTELLIGENCE
    # =========================================================================
    def get_category_analytics(
        self,
        start_utc: datetime,
        end_utc: datetime,
        prev_start_utc: datetime,
        prev_end_utc: datetime
    ) -> List[Dict[str, Any]]:
        """Calculates category revenue, units, AOV, growth, and refund rates without double counting."""
        
        # Valid order items in current period
        cur_items = self.db.query(
            OrderItem.product_id,
            OrderItem.quantity,
            OrderItem.subtotal,
            OrderItem.total,
            OrderItem.order_id
        ).join(Order, OrderItem.order_id == Order.id).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc,
            Order.status.in_(VALID_ORDER_STATUSES)
        ).all()

        # Valid order items in previous period
        prev_items = self.db.query(
            OrderItem.product_id,
            OrderItem.quantity,
            OrderItem.total
        ).join(Order, OrderItem.order_id == Order.id).filter(
            Order.date_created_utc >= prev_start_utc,
            Order.date_created_utc <= prev_end_utc,
            Order.status.in_(VALID_ORDER_STATUSES)
        ).all()

        # Category mappings
        mappings = self.db.query(
            ProductCategoryMapping.product_id,
            ProductCategory.id.label("cat_id"),
            ProductCategory.name.label("cat_name")
        ).join(ProductCategory, ProductCategoryMapping.category_id == ProductCategory.id).all()

        cat_lookup = {}
        for pid, cid, cname in mappings:
            if pid not in cat_lookup:
                cat_lookup[pid] = []
            cat_lookup[pid].append((cid, cname))

        # Current aggregation by category
        cur_cats = {}
        store_net_sales = sum(i.total for i in cur_items)

        for item in cur_items:
            assigned = cat_lookup.get(item.product_id, [(0, "Uncategorized")])
            # Even if product has multiple categories, distribute equally or associate
            weight = 1.0 / len(assigned)
            for cid, cname in assigned:
                if cid not in cur_cats:
                    cur_cats[cid] = {
                        "category_id": cid,
                        "category_name": cname,
                        "gross_sales": 0.0,
                        "net_sales": 0.0,
                        "units_sold": 0,
                        "orders": set(),
                        "products": set()
                    }
                cur_cats[cid]["gross_sales"] += item.subtotal * weight
                cur_cats[cid]["net_sales"] += item.total * weight
                cur_cats[cid]["units_sold"] += int(round(item.quantity * weight))
                cur_cats[cid]["orders"].add(item.order_id)
                if item.product_id:
                    cur_cats[cid]["products"].add(item.product_id)

        # Previous aggregation by category
        prev_cats = {}
        for item in prev_items:
            assigned = cat_lookup.get(item.product_id, [(0, "Uncategorized")])
            weight = 1.0 / len(assigned)
            for cid, cname in assigned:
                if cid not in prev_cats:
                    prev_cats[cid] = 0.0
                prev_cats[cid] += item.total * weight

        results = []
        for cid, data in cur_cats.items():
            net = data["net_sales"]
            prev_net = prev_cats.get(cid, 0.0)
            growth = ((net - prev_net) / prev_net * 100) if prev_net > 0 else (100.0 if net > 0 else 0.0)
            orders_cnt = len(data["orders"])
            aov = (net / orders_cnt) if orders_cnt > 0 else 0.0
            contrib = (net / store_net_sales * 100) if store_net_sales > 0 else 0.0

            results.append({
                "category_id": cid,
                "name": data["category_name"],
                "gross_sales": round(data["gross_sales"], 2),
                "net_sales": round(net, 2),
                "units_sold": data["units_sold"],
                "orders_count": orders_cnt,
                "aov": round(aov, 2),
                "sales_contribution_pct": round(contrib, 1),
                "growth_pct": round(growth, 1),
                "product_count": len(data["products"])
            })

        results.sort(key=lambda x: x["net_sales"], reverse=True)
        return results

    # =========================================================================
    # 5. CUSTOMER INTELLIGENCE & COHORTS
    # =========================================================================
    def get_customer_segments(self) -> Dict[str, Any]:
        """Calculates RFM-based behavioral customer segments and cohort matrices."""
        customers = self.db.query(Customer).all()
        orders = self.db.query(
            Order.customer_id,
            Order.date_created_utc,
            Order.net_sales
        ).filter(
            Order.status.in_(VALID_ORDER_STATUSES),
            Order.customer_id.isnot(None)
        ).all()

        if not orders:
            return {
                "segments": {
                    "high_value": 0, "frequent_buyers": 0, "one_time": 0,
                    "inactive": 0, "declining": 0
                },
                "cohort_data": []
            }

        df = pd.DataFrame([{
            "customer_id": o.customer_id,
            "date": o.date_created_utc,
            "net_sales": o.net_sales
        } for o in orders])

        df["date"] = pd.to_datetime(df["date"], utc=True)
        now = pd.to_datetime(datetime.now(timezone.utc))

        # Customer level aggregation
        cust_agg = df.groupby("customer_id").agg(
            order_count=("net_sales", "count"),
            total_spent=("net_sales", "sum"),
            last_order=("date", "max"),
            first_order=("date", "min")
        ).reset_index()

        cust_agg["days_since_last"] = (now - cust_agg["last_order"]).dt.days

        # Segmentation Rules:
        # High-value: spent > top 15% threshold
        spend_thresh = cust_agg["total_spent"].quantile(0.85) if len(cust_agg) > 5 else 300.0

        high_value = cust_agg[cust_agg["total_spent"] >= spend_thresh]
        frequent = cust_agg[(cust_agg["order_count"] >= 3) & (~cust_agg.index.isin(high_value.index))]
        one_time = cust_agg[cust_agg["order_count"] == 1]
        inactive = cust_agg[cust_agg["days_since_last"] > 90]
        declining = cust_agg[(cust_agg["order_count"] >= 2) & (cust_agg["days_since_last"] > 60)]

        # Monthly Cohort Analysis
        df["cohort_month"] = df.groupby("customer_id")["date"].transform("min").dt.to_period("M")
        df["order_month"] = df["date"].dt.to_period("M")

        df["cohort_index"] = (df["order_month"].dt.year - df["cohort_month"].dt.year) * 12 + (df["order_month"].dt.month - df["cohort_month"].dt.month)

        cohort_group = df.groupby(["cohort_month", "cohort_index"])["customer_id"].nunique().reset_index()
        cohort_pivot = cohort_group.pivot(index="cohort_month", columns="cohort_index", values="customer_id").fillna(0)

        # Convert to retention percentages
        cohort_sizes = cohort_pivot.iloc[:, 0]
        retention = cohort_pivot.divide(cohort_sizes, axis=0) * 100

        cohort_records = []
        for period in retention.index:
            row_data = {"cohort": str(period), "size": int(cohort_sizes.loc[period])}
            for col in retention.columns:
                val = retention.loc[period, col]
                row_data[f"month_{col}"] = round(float(val), 1) if pd.notnull(val) else 0.0
            cohort_records.append(row_data)

        return {
            "segments": {
                "high_value": len(high_value),
                "frequent_buyers": len(frequent),
                "one_time": len(one_time),
                "inactive": len(inactive),
                "declining": len(declining)
            },
            "summary": {
                "total_customers": len(cust_agg),
                "repeat_customers": len(cust_agg[cust_agg["order_count"] > 1]),
                "repeat_rate_pct": round((len(cust_agg[cust_agg["order_count"] > 1]) / len(cust_agg) * 100) if len(cust_agg) > 0 else 0.0, 1),
                "avg_orders_per_customer": round(cust_agg["order_count"].mean(), 2) if len(cust_agg) > 0 else 0.0,
                "avg_customer_lifetime_rev": round(cust_agg["total_spent"].mean(), 2) if len(cust_agg) > 0 else 0.0,
            },
            "cohort_data": cohort_records[-6:]  # Last 6 cohorts
        }

    # =========================================================================
    # 6. ORDER & FULFILLMENT ANALYTICS
    # =========================================================================
    def get_order_analytics(
        self,
        start_utc: datetime,
        end_utc: datetime
    ) -> Dict[str, Any]:
        """Calculates order fulfillment, status distribution, and basket size metrics."""
        orders = self.db.query(Order).filter(
            Order.date_created_utc >= start_utc,
            Order.date_created_utc <= end_utc
        )
        if self.store_id:
            orders = orders.filter(Order.store_id == self.store_id)
        
        all_orders = orders.all()
        if not all_orders:
            return {"status_distribution": {}, "fulfillment": {}, "basket_metrics": {}}

        # Status distribution
        status_counts = {}
        for o in all_orders:
            st = o.status.lower()
            status_counts[st] = status_counts.get(st, 0) + 1

        # Fulfillment times (hours between created and completed)
        fulfillment_times = []
        for o in all_orders:
            if o.date_completed_utc and o.date_created_utc:
                diff_hours = (o.date_completed_utc - o.date_created_utc).total_seconds() / 3600.0
                if diff_hours >= 0:
                    fulfillment_times.append(diff_hours)

        avg_fulfillment_hours = np.mean(fulfillment_times) if fulfillment_times else 0.0

        # Basket size (items per order)
        valid_order_ids = [o.id for o in all_orders if o.status in VALID_ORDER_STATUSES]
        if valid_order_ids:
            items_per_order = self.db.query(
                OrderItem.order_id,
                func.sum(OrderItem.quantity).label("units"),
                func.count(OrderItem.id).label("unique_lines")
            ).filter(OrderItem.order_id.in_(valid_order_ids)).group_by(OrderItem.order_id).all()

            units_list = [r.units for r in items_per_order]
            lines_list = [r.unique_lines for r in items_per_order]

            avg_units_per_order = np.mean(units_list) if units_list else 0.0
            multi_item_order_pct = (sum(1 for u in lines_list if u > 1) / len(lines_list) * 100) if lines_list else 0.0
        else:
            avg_units_per_order = 0.0
            multi_item_order_pct = 0.0

        return {
            "status_distribution": status_counts,
            "fulfillment": {
                "avg_fulfillment_hours": round(avg_fulfillment_hours, 1),
                "avg_fulfillment_days": round(avg_fulfillment_hours / 24.0, 1),
                "tracked_orders_count": len(fulfillment_times)
            },
            "basket_metrics": {
                "avg_units_per_order": round(avg_units_per_order, 1),
                "multi_item_orders_pct": round(multi_item_order_pct, 1)
            }
        }
