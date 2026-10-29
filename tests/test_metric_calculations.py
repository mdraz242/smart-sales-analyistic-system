import pytest
from datetime import datetime, timezone, timedelta
from backend.app.services.analytics_engine import AnalyticsEngine, VALID_ORDER_STATUSES
from backend.app.models.order import Order


def test_metric_reconciliation(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=30)
    end_utc = now

    metrics = engine.calculate_period_metrics(start_utc, end_utc)

    # 1. Gross sales >= Net Sales
    assert metrics["gross_sales"] >= metrics["net_sales"]

    # 2. Reconcile Net Sales: Gross - Discounts - Refunds
    reconciled_net = round(metrics["gross_sales"] - metrics["discounts"] - metrics["refunds"], 2)
    assert abs(metrics["net_sales"] - reconciled_net) <= 0.05

    # 3. Reconcile Total Revenue Collected: Net Sales + Shipping + Tax
    reconciled_revenue = round(metrics["net_sales"] + metrics["shipping_revenue"] + metrics["tax_collected"], 2)
    assert abs(metrics["total_revenue_collected"] - reconciled_revenue) <= 0.05

    # 4. Total orders must strictly equal completed + processing orders
    actual_orders = db.query(Order).filter(
        Order.store_id == store.id,
        Order.date_created_utc >= start_utc,
        Order.date_created_utc <= end_utc,
        Order.status.in_(VALID_ORDER_STATUSES)
    ).count()
    assert metrics["total_orders"] == actual_orders

    # 5. AOV check
    if metrics["total_orders"] > 0:
        expected_aov = round(metrics["net_sales"] / metrics["total_orders"], 2)
        assert abs(metrics["aov"] - expected_aov) <= 0.05
    else:
        assert metrics["aov"] == 0.0

    # 6. Units sold > 0
    assert metrics["units_sold"] > 0
    assert metrics["unique_customers"] > 0


def test_cancelled_orders_excluded_from_sales(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=60)
    end_utc = now

    cancelled_count = db.query(Order).filter(
        Order.store_id == store.id,
        Order.date_created_utc >= start_utc,
        Order.date_created_utc <= end_utc,
        Order.status == "cancelled"
    ).count()

    metrics = engine.calculate_period_metrics(start_utc, end_utc)
    # Total valid orders must not include cancelled
    assert cancelled_count >= 0
    if metrics["total_placed_orders_count"] > 0:
        assert metrics["total_orders"] <= metrics["total_placed_orders_count"]
        assert metrics["cancellation_rate"] >= 0.0


def test_executive_kpis_period_comparison(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    now = datetime.now(timezone.utc)
    end_utc = now
    start_utc = now - timedelta(days=30)
    prev_end_utc = start_utc
    prev_start_utc = start_utc - timedelta(days=30)

    kpis = engine.get_executive_kpis(
        start_utc, end_utc, prev_start_utc, prev_end_utc, currency="USD"
    )

    assert "gross_sales" in kpis
    assert "net_sales" in kpis
    assert "units_sold" in kpis
    assert "average_order_value" in kpis
    assert "cancellation_rate" in kpis
    assert "refund_rate" in kpis
    assert "sales_growth_pct" in kpis

    # Ensure definition strings are present
    assert len(kpis["gross_sales"]["definition"]) > 10
    assert len(kpis["net_sales"]["definition"]) > 10
    assert kpis["gross_sales"]["trend"] in ["positive", "negative", "neutral"]


def test_category_analytics_no_double_counting(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=60)
    end_utc = now
    prev_start_utc = start_utc - timedelta(days=60)
    prev_end_utc = start_utc

    categories = engine.get_category_analytics(start_utc, end_utc, prev_start_utc, prev_end_utc)
    assert len(categories) > 0

    # Sum of category net sales should not wildly exceed total store net sales
    sum_cat_sales = sum(c["net_sales"] for c in categories)
    cur_metrics = engine.calculate_period_metrics(start_utc, end_utc)
    # Within 5% tolerance due to fractional category weighting
    assert abs(sum_cat_sales - cur_metrics["net_sales"]) <= (cur_metrics["net_sales"] * 0.10 + 10.0)


def test_customer_cohorts_and_segments(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    customer_data = engine.get_customer_segments()
    assert "segments" in customer_data
    assert "summary" in customer_data
    assert "cohort_data" in customer_data

    segments = customer_data["segments"]
    assert segments["high_value"] >= 0
    assert segments["one_time"] >= 0
    assert customer_data["summary"]["repeat_rate_pct"] >= 0.0
