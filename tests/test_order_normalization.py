import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from backend.app.services.woocommerce_client import WooCommerceClient, WooCommerceAPIError
from backend.app.services.sync_service import parse_wc_datetime, SyncService
from backend.app.models.order import Order, OrderItem, Refund


def test_parse_wc_datetime():
    # Test ISO strings
    dt1 = parse_wc_datetime("2026-03-24T18:25:43")
    assert dt1 is not None
    assert dt1.year == 2026
    assert dt1.tzinfo is not None

    dt2 = parse_wc_datetime("2026-03-24T18:25:43Z")
    assert dt2 is not None
    assert dt2.tzinfo is not None

    # None and invalid cases
    assert parse_wc_datetime(None) is None
    assert parse_wc_datetime("not-a-date") is None


def test_order_sync_normalization_and_idempotency(populated_db):
    db, store = populated_db
    sync_service = SyncService(db, store)

    sample_wc_order = {
        "id": 99991,
        "number": "ORD-99991",
        "status": "completed",
        "currency": "USD",
        "date_created_gmt": "2026-03-15T14:30:00",
        "date_modified_gmt": "2026-03-15T14:35:00",
        "date_completed_gmt": "2026-03-16T10:00:00",
        "total": "115.00",
        "discount_total": "10.00",
        "shipping_total": "5.00",
        "total_tax": "7.00",
        "shipping_tax": "0.00",
        "payment_method": "stripe",
        "payment_method_title": "Credit Card (Stripe)",
        "billing": {
            "city": "Austin",
            "state": "TX",
            "country": "US",
            "postcode": "78701"
        },
        "line_items": [
            {
                "id": 88881,
                "product_id": 1001,
                "name": "AeroLite Running Tee",
                "sku": "ALT-RN-01",
                "quantity": 2,
                "price": "48.00",
                "subtotal": "96.00",
                "total": "86.00",
                "subtotal_tax": "6.72",
                "total_tax": "6.02"
            }
        ],
        "coupon_lines": [
            {
                "id": 1,
                "code": "SAVE10",
                "discount": "10.00",
                "discount_tax": "0.70"
            }
        ],
        "refunds": [
            {
                "id": 77771,
                "total": "-20.00",
                "reason": "Damaged sleeve"
            }
        ]
    }

    # Mock the client's fetch_paginated call
    with patch.object(sync_service.client, "fetch_paginated", return_value=[sample_wc_order]):
        fetched, inserted, updated = sync_service._sync_orders("full")
        assert fetched == 1
        assert inserted == 1
        assert updated == 0

        # Verify normalized record in database
        saved_order = db.query(Order).filter(Order.id == 99991).first()
        assert saved_order is not None
        assert saved_order.order_number == "ORD-99991"
        assert saved_order.status == "completed"
        assert saved_order.discount_total == 10.0
        assert saved_order.total_refunded == 20.0
        # Net sales = 96.0 (subtotal) - 10.0 (discount) - 20.0 (refund) = 66.0
        assert saved_order.net_sales == 66.0
        assert saved_order.billing_city == "Austin"

        # Verify line items
        line_items = db.query(OrderItem).filter(OrderItem.order_id == 99991).all()
        assert len(line_items) == 1
        assert line_items[0].quantity == 2
        assert line_items[0].sku == "ALT-RN-01"

        # Re-run sync with updated status - MUST update existing record, NOT insert duplicate!
        sample_wc_order["status"] = "refunded"
        sample_wc_order["date_modified_gmt"] = "2026-03-20T12:00:00"

        fetched2, inserted2, updated2 = sync_service._sync_orders("incremental")
        assert fetched2 == 1
        assert inserted2 == 0  # Idempotent!
        assert updated2 == 1   # Updated!

        # Check order count in database hasn't duplicated
        all_order_99991 = db.query(Order).filter(Order.id == 99991).all()
        assert len(all_order_99991) == 1
        assert all_order_99991[0].status == "refunded"
