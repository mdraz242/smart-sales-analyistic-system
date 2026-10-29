import pytest
from datetime import datetime, timezone, timedelta
from backend.app.services.analytics_engine import AnalyticsEngine


def test_product_ranking_by_units_and_net_sales(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=60)
    end_utc = now
    prev_start_utc = start_utc - timedelta(days=60)
    prev_end_utc = start_utc

    # Rank by units sold
    by_units = engine.get_product_performance(
        start_utc, end_utc, prev_start_utc, prev_end_utc, rank_by="units_sold", limit=20
    )
    assert len(by_units) > 0
    # Check descending order of units
    for i in range(len(by_units) - 1):
        assert by_units[i]["units_sold"] >= by_units[i + 1]["units_sold"]

    # Rank by net sales
    by_sales = engine.get_product_performance(
        start_utc, end_utc, prev_start_utc, prev_end_utc, rank_by="net_sales", limit=20
    )
    assert len(by_sales) > 0
    for i in range(len(by_sales) - 1):
        assert by_sales[i]["net_sales"] >= by_sales[i + 1]["net_sales"]


def test_product_classification_rules(populated_db):
    db, store = populated_db
    engine = AnalyticsEngine(db, store_id=store.id)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=60)
    end_utc = now
    prev_start_utc = start_utc - timedelta(days=60)
    prev_end_utc = start_utc

    products = engine.get_product_performance(
        start_utc, end_utc, prev_start_utc, prev_end_utc, limit=50
    )
    assert len(products) > 0

    valid_classes = {
        "Best Seller", "Rising Star", "Declining", "Low Performer",
        "High Revenue", "High Margin", "High Refund Risk",
        "Discount Dependent", "Stockout Risk", "Steady"
    }

    found_classes = set()
    for p in products:
        assert p["classification"] in valid_classes
        found_classes.add(p["classification"])
        # If cost data exists, margin must be calculated
        if p["cogs"] is not None:
            assert p["gross_profit"] is not None
            assert p["gross_margin_pct"] is not None

    # Should have identified multiple classes across products
    assert len(found_classes) >= 3
