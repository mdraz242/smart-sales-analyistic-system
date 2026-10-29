import pytest
import io
import pandas as pd
from backend.app.services.import_service import DataImportService
from backend.app.models.product import Product
from backend.app.models.order import Order


def test_validate_and_commit_product_costs(populated_db):
    db, store = populated_db
    import_service = DataImportService(db, store_id=store.id)

    # 1. Test invalid file format / missing columns
    df_missing_cols = pd.DataFrame([{"foo": "bar", "baz": 123}])
    with pytest.raises(ValueError) as excinfo:
        import_service.validate_product_costs(df_missing_cols)
    assert "unit_cost" in str(excinfo.value)

    # 2. Test row validation with valid and invalid rows
    test_df = pd.DataFrame([
        {"sku": "ALT-RN-01", "unit_cost": "19.50"},    # Valid
        {"sku": "CPT-TI-02", "unit_cost": "$29.99"},   # Valid with dollar sign
        {"sku": "NON_EXISTENT_SKU", "unit_cost": 15.0}, # Unknown SKU
        {"sku": "VNT-SH-03", "unit_cost": -10.0},       # Negative cost error
        {"sku": "MTB-LS-05", "unit_cost": "not_a_num"}, # Numeric format error
    ])

    val_res = import_service.validate_product_costs(test_df)
    assert val_res.total_rows == 5
    assert val_res.valid_rows == 2
    assert val_res.error_rows == 3
    assert val_res.ready_to_import is True
    assert len(val_res.errors) == 3

    # 3. Commit costs and verify database updates
    commit_res = import_service.commit_product_costs(test_df)
    assert commit_res["success"] is True
    assert commit_res["imported_count"] == 2

    # Check updated products in DB
    p1 = db.query(Product).filter(Product.sku == "ALT-RN-01").first()
    assert p1.current_cost == 19.50

    p2 = db.query(Product).filter(Product.sku == "CPT-TI-02").first()
    assert p2.current_cost == 29.99


def test_validate_and_commit_inventory_levels(populated_db):
    db, store = populated_db
    import_service = DataImportService(db, store_id=store.id)

    test_df = pd.DataFrame([
        {"sku": "ALT-RN-01", "stock_quantity": "50"},
        {"sku": "CPT-TI-02", "stock_quantity": 0},
        {"sku": "NON_EXISTENT_SKU", "stock_quantity": 10},
        {"sku": "VNT-SH-03", "stock_quantity": -5},
    ])

    val_res = import_service.validate_inventory_levels(test_df)
    assert val_res.total_rows == 4
    assert val_res.valid_rows == 2
    assert val_res.error_rows == 2

    commit_res = import_service.commit_inventory_levels(test_df)
    assert commit_res["success"] is True
    assert commit_res["imported_count"] == 2

    p1 = db.query(Product).filter(Product.sku == "ALT-RN-01").first()
    assert p1.stock_quantity == 50
    assert p1.stock_status == "instock"

    p2 = db.query(Product).filter(Product.sku == "CPT-TI-02").first()
    assert p2.stock_quantity == 0
    assert p2.stock_status == "outofstock"


def test_validate_and_commit_historical_orders(populated_db):
    db, store = populated_db
    import_service = DataImportService(db, store_id=store.id)

    test_df = pd.DataFrame([
        {
            "order_number": "IMP-TEST-101",
            "date": "2026-10-20 12:00:00",
            "customer_email": "importer.user@test.com",
            "first_name": "Importer",
            "last_name": "Test",
            "sku": "ALT-RN-01",
            "quantity": 2,
            "total": 178.00,
            "status": "completed"
        },
        {
            "order_number": "IMP-TEST-102",
            "date": "2026-10-21 14:00:00",
            "customer_email": "importer.user2@test.com",
            "first_name": "User",
            "last_name": "Two",
            "sku": "CPT-TI-02",
            "quantity": 1,
            "total": -50.00, # Invalid negative total
            "status": "completed"
        }
    ])

    val_res = import_service.validate_historical_orders(test_df)
    assert val_res.total_rows == 2
    assert val_res.valid_rows == 1
    assert val_res.error_rows == 1

    commit_res = import_service.commit_historical_orders(test_df)
    assert commit_res["success"] is True
    assert commit_res["imported_count"] == 1

    ord_imported = db.query(Order).filter(Order.order_number == "IMP-TEST-101").first()
    assert ord_imported is not None
    assert ord_imported.total_amount == 178.00
    assert ord_imported.net_sales == 178.00


def test_template_generation_csv_and_xlsx(populated_db):
    db, store = populated_db
    import_service = DataImportService(db, store_id=store.id)

    # Costs templates
    csv_bytes = import_service.generate_template("costs", format_type="csv")
    assert b"sku,product_name,unit_cost" in csv_bytes

    xlsx_bytes = import_service.generate_template("costs", format_type="xlsx")
    assert len(xlsx_bytes) > 100
    df_read = pd.read_excel(io.BytesIO(xlsx_bytes))
    assert "unit_cost" in df_read.columns
    assert "sku" in df_read.columns

    # Inventory template
    inv_csv = import_service.generate_template("inventory", format_type="csv")
    assert b"stock_quantity" in inv_csv

    # Orders template
    ord_csv = import_service.generate_template("orders", format_type="csv")
    assert b"order_number" in ord_csv
