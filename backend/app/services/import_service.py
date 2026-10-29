import io
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.models.product import Product, InventorySnapshot
from backend.app.models.cost import ProductCostHistory
from backend.app.models.customer import Customer
from backend.app.models.order import Order, OrderItem
from backend.app.schemas.import_export import ImportValidationResult

logger = logging.getLogger("import_service")


class DataImportService:
    def __init__(self, db: Session, store_id: Optional[int] = None):
        self.db = db
        self.store_id = store_id

    def parse_file(self, file_bytes: bytes, filename: str) -> pd.DataFrame:
        """Parses CSV or Excel bytes into a Pandas DataFrame."""
        if filename.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(file_bytes))
        else:
            raise ValueError(f"Unsupported file format: {filename}. Please upload a .csv or .xlsx file.")

    # =========================================================================
    # 1. PRODUCT COST (COGS) IMPORT
    # =========================================================================
    def validate_product_costs(self, df: pd.DataFrame) -> ImportValidationResult:
        """Validates cost import rows before committing to database."""
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        required_cost_cols = ["cost", "unit_cost", "product_cost", "cogs"]
        cost_col = next((c for c in required_cost_cols if c in df.columns), None)

        if not cost_col:
            raise ValueError("File must contain a 'unit_cost', 'cost', or 'cogs' column.")

        sku_col = next((c for c in ["sku", "product_sku", "item_sku"] if c in df.columns), None)
        id_col = next((c for c in ["product_id", "id", "wc_id"] if c in df.columns), None)
        name_col = next((c for c in ["name", "product_name", "title"] if c in df.columns), None)

        if not sku_col and not id_col and not name_col:
            raise ValueError("File must contain at least one identifier column: 'sku', 'product_id', or 'product_name'.")

        preview_rows = []
        errors = []
        valid_count = 0
        error_count = 0

        prod_query = self.db.query(Product)
        if self.store_id:
            prod_query = prod_query.filter(Product.store_id == self.store_id)
        prods = prod_query.all()

        sku_to_prod = {p.sku.strip().lower(): p for p in prods if p.sku}
        id_to_prod = {p.id: p for p in prods}
        name_to_prod = {p.name.strip().lower(): p for p in prods if p.name}

        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_errors = []

            raw_cost = row.get(cost_col)
            try:
                clean_cost = float(str(raw_cost).replace("$", "").replace(",", "").strip())
                if clean_cost < 0:
                    row_errors.append("Unit cost cannot be negative.")
            except (ValueError, TypeError):
                row_errors.append(f"Invalid numeric cost value: '{raw_cost}'")
                clean_cost = None

            matched_prod = None
            if sku_col and pd.notna(row.get(sku_col)):
                sku_val = str(row.get(sku_col)).strip().lower()
                matched_prod = sku_to_prod.get(sku_val)
            if not matched_prod and id_col and pd.notna(row.get(id_col)):
                try:
                    matched_prod = id_to_prod.get(int(row.get(id_col)))
                except ValueError:
                    pass
            if not matched_prod and name_col and pd.notna(row.get(name_col)):
                matched_prod = name_to_prod.get(str(row.get(name_col)).strip().lower())

            if not matched_prod:
                row_errors.append(f"No matching product found in database for SKU/ID/Name: {row.get(sku_col or id_col or name_col)}")

            if row_errors:
                error_count += 1
                errors.append({
                    "row_index": idx + 2,
                    "errors": "; ".join(row_errors),
                    "data": row_dict
                })
                row_dict["_validation_status"] = "ERROR: " + "; ".join(row_errors)
            else:
                valid_count += 1
                row_dict["_validation_status"] = f"MATCHED: {matched_prod.name} (SKU: {matched_prod.sku or 'N/A'})"
                row_dict["_clean_cost"] = clean_cost
                row_dict["_matched_product_id"] = matched_prod.id

            if len(preview_rows) < 15:
                preview_rows.append(row_dict)

        return ImportValidationResult(
            total_rows=len(df),
            valid_rows=valid_count,
            error_rows=error_count,
            preview_data=preview_rows,
            errors=errors,
            ready_to_import=(valid_count > 0)
        )

    def commit_product_costs(self, df: pd.DataFrame, source_name: str = "import") -> Dict[str, Any]:
        """Applies validated costs to Product and ProductCostHistory tables."""
        val_result = self.validate_product_costs(df)
        if val_result.valid_rows == 0:
            raise ValueError("Cannot import: no valid rows found.")

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        cost_col = next(c for c in ["cost", "unit_cost", "product_cost", "cogs"] if c in df.columns)
        sku_col = next((c for c in ["sku", "product_sku", "item_sku"] if c in df.columns), None)
        id_col = next((c for c in ["product_id", "id", "wc_id"] if c in df.columns), None)
        name_col = next((c for c in ["name", "product_name", "title"] if c in df.columns), None)

        prods = self.db.query(Product).all()
        sku_to_prod = {p.sku.strip().lower(): p for p in prods if p.sku}
        id_to_prod = {p.id: p for p in prods}
        name_to_prod = {p.name.strip().lower(): p for p in prods if p.name}

        imported_count = 0
        now = datetime.now(timezone.utc)

        for _, row in df.iterrows():
            try:
                clean_cost = float(str(row.get(cost_col)).replace("$", "").replace(",", "").strip())
                if clean_cost < 0:
                    continue
            except Exception:
                continue

            matched_prod = None
            if sku_col and pd.notna(row.get(sku_col)):
                matched_prod = sku_to_prod.get(str(row.get(sku_col)).strip().lower())
            if not matched_prod and id_col and pd.notna(row.get(id_col)):
                try:
                    matched_prod = id_to_prod.get(int(row.get(id_col)))
                except ValueError:
                    pass
            if not matched_prod and name_col and pd.notna(row.get(name_col)):
                matched_prod = name_to_prod.get(str(row.get(name_col)).strip().lower())

            if matched_prod:
                matched_prod.current_cost = clean_cost
                cost_hist = ProductCostHistory(
                    product_id=matched_prod.id,
                    sku=matched_prod.sku,
                    unit_cost=clean_cost,
                    effective_date=now,
                    source=source_name,
                    notes="Imported via Data Import Module"
                )
                self.db.add(cost_hist)
                imported_count += 1

        self.db.commit()
        return {
            "success": True,
            "imported_count": imported_count,
            "errors_count": val_result.error_rows,
            "errors": val_result.errors
        }

    # =========================================================================
    # 2. INVENTORY LEVEL IMPORT
    # =========================================================================
    def validate_inventory_levels(self, df: pd.DataFrame) -> ImportValidationResult:
        """Validates inventory stock level rows before committing."""
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        qty_col = next((c for c in ["stock_quantity", "quantity", "stock", "qty", "inventory"] if c in df.columns), None)
        if not qty_col:
            raise ValueError("File must contain a stock quantity column ('stock_quantity', 'quantity', 'stock', or 'qty').")

        sku_col = next((c for c in ["sku", "product_sku"] if c in df.columns), None)
        id_col = next((c for c in ["product_id", "id", "wc_id"] if c in df.columns), None)
        name_col = next((c for c in ["name", "product_name"] if c in df.columns), None)

        if not sku_col and not id_col and not name_col:
            raise ValueError("File must contain at least one identifier column: 'sku', 'product_id', or 'product_name'.")

        preview_rows = []
        errors = []
        valid_count = 0
        error_count = 0

        prod_query = self.db.query(Product)
        if self.store_id:
            prod_query = prod_query.filter(Product.store_id == self.store_id)
        prods = prod_query.all()

        sku_to_prod = {p.sku.strip().lower(): p for p in prods if p.sku}
        id_to_prod = {p.id: p for p in prods}
        name_to_prod = {p.name.strip().lower(): p for p in prods if p.name}

        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_errors = []

            raw_qty = row.get(qty_col)
            try:
                clean_qty = int(float(str(raw_qty).strip()))
                if clean_qty < 0:
                    row_errors.append("Stock quantity cannot be negative.")
            except (ValueError, TypeError):
                row_errors.append(f"Invalid integer stock quantity: '{raw_qty}'")
                clean_qty = None

            matched_prod = None
            if sku_col and pd.notna(row.get(sku_col)):
                matched_prod = sku_to_prod.get(str(row.get(sku_col)).strip().lower())
            if not matched_prod and id_col and pd.notna(row.get(id_col)):
                try:
                    matched_prod = id_to_prod.get(int(row.get(id_col)))
                except ValueError:
                    pass
            if not matched_prod and name_col and pd.notna(row.get(name_col)):
                matched_prod = name_to_prod.get(str(row.get(name_col)).strip().lower())

            if not matched_prod:
                row_errors.append(f"No matching product found in database for SKU/ID/Name: {row.get(sku_col or id_col or name_col)}")

            if row_errors:
                error_count += 1
                errors.append({
                    "row_index": idx + 2,
                    "errors": "; ".join(row_errors),
                    "data": row_dict
                })
                row_dict["_validation_status"] = "ERROR: " + "; ".join(row_errors)
            else:
                valid_count += 1
                row_dict["_validation_status"] = f"MATCHED: {matched_prod.name} (SKU: {matched_prod.sku or 'N/A'})"
                row_dict["_clean_qty"] = clean_qty
                row_dict["_matched_product_id"] = matched_prod.id

            if len(preview_rows) < 15:
                preview_rows.append(row_dict)

        return ImportValidationResult(
            total_rows=len(df),
            valid_rows=valid_count,
            error_rows=error_count,
            preview_data=preview_rows,
            errors=errors,
            ready_to_import=(valid_count > 0)
        )

    def commit_inventory_levels(self, df: pd.DataFrame, source_name: str = "inventory_import") -> Dict[str, Any]:
        """Updates stock quantities and creates inventory snapshots."""
        val_result = self.validate_inventory_levels(df)
        if val_result.valid_rows == 0:
            raise ValueError("Cannot import: no valid inventory rows found.")

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        qty_col = next(c for c in ["stock_quantity", "quantity", "stock", "qty", "inventory"] if c in df.columns)
        sku_col = next((c for c in ["sku", "product_sku"] if c in df.columns), None)
        id_col = next((c for c in ["product_id", "id", "wc_id"] if c in df.columns), None)
        name_col = next((c for c in ["name", "product_name"] if c in df.columns), None)

        prods = self.db.query(Product).all()
        sku_to_prod = {p.sku.strip().lower(): p for p in prods if p.sku}
        id_to_prod = {p.id: p for p in prods}
        name_to_prod = {p.name.strip().lower(): p for p in prods if p.name}

        updated_count = 0
        now = datetime.now(timezone.utc)

        for _, row in df.iterrows():
            try:
                clean_qty = int(float(str(row.get(qty_col)).strip()))
                if clean_qty < 0:
                    continue
            except Exception:
                continue

            matched_prod = None
            if sku_col and pd.notna(row.get(sku_col)):
                matched_prod = sku_to_prod.get(str(row.get(sku_col)).strip().lower())
            if not matched_prod and id_col and pd.notna(row.get(id_col)):
                try:
                    matched_prod = id_to_prod.get(int(row.get(id_col)))
                except ValueError:
                    pass
            if not matched_prod and name_col and pd.notna(row.get(name_col)):
                matched_prod = name_to_prod.get(str(row.get(name_col)).strip().lower())

            if matched_prod:
                matched_prod.stock_quantity = clean_qty
                matched_prod.manage_stock = True
                matched_prod.stock_status = "instock" if clean_qty > 0 else "outofstock"
                
                # Snapshot
                snap = InventorySnapshot(
                    product_id=matched_prod.id,
                    sku=matched_prod.sku,
                    stock_quantity=clean_qty,
                    snapshot_date=now
                )
                self.db.add(snap)
                updated_count += 1

        self.db.commit()
        return {
            "success": True,
            "imported_count": updated_count,
            "errors_count": val_result.error_rows,
            "errors": val_result.errors
        }

    # =========================================================================
    # 3. HISTORICAL ORDERS IMPORT
    # =========================================================================
    def validate_historical_orders(self, df: pd.DataFrame) -> ImportValidationResult:
        """Validates historical order records."""
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        order_col = next((c for c in ["order_number", "order_id", "order_no", "order"] if c in df.columns), None)
        if not order_col:
            raise ValueError("File must contain an 'order_number' or 'order_id' column.")

        total_col = next((c for c in ["total", "total_amount", "net_sales", "amount", "order_total"] if c in df.columns), None)
        if not total_col:
            raise ValueError("File must contain a 'total' or 'total_amount' column.")

        date_col = next((c for c in ["date", "order_date", "date_created", "created_at"] if c in df.columns), None)
        email_col = next((c for c in ["customer_email", "email", "billing_email"] if c in df.columns), None)

        preview_rows = []
        errors = []
        valid_count = 0
        error_count = 0

        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_errors = []

            # Check total
            raw_total = row.get(total_col)
            try:
                clean_total = float(str(raw_total).replace("$", "").replace(",", "").strip())
                if clean_total < 0:
                    row_errors.append("Order total cannot be negative.")
            except (ValueError, TypeError):
                row_errors.append(f"Invalid numeric order total: '{raw_total}'")

            # Check date if provided
            if date_col and pd.notna(row.get(date_col)):
                try:
                    pd.to_datetime(str(row.get(date_col)))
                except Exception:
                    row_errors.append(f"Invalid date format: '{row.get(date_col)}'")

            if row_errors:
                error_count += 1
                errors.append({
                    "row_index": idx + 2,
                    "errors": "; ".join(row_errors),
                    "data": row_dict
                })
                row_dict["_validation_status"] = "ERROR: " + "; ".join(row_errors)
            else:
                valid_count += 1
                row_dict["_validation_status"] = "VALID ORDER RECORD"

            if len(preview_rows) < 15:
                preview_rows.append(row_dict)

        return ImportValidationResult(
            total_rows=len(df),
            valid_rows=valid_count,
            error_rows=error_count,
            preview_data=preview_rows,
            errors=errors,
            ready_to_import=(valid_count > 0)
        )

    def commit_historical_orders(self, df: pd.DataFrame, source_name: str = "order_import") -> Dict[str, Any]:
        """Commits historical orders and associated customer records into database."""
        val_result = self.validate_historical_orders(df)
        if val_result.valid_rows == 0:
            raise ValueError("Cannot import: no valid order rows found.")

        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        order_col = next(c for c in ["order_number", "order_id", "order_no", "order"] if c in df.columns)
        total_col = next(c for c in ["total", "total_amount", "net_sales", "amount", "order_total"] if c in df.columns)
        date_col = next((c for c in ["date", "order_date", "date_created", "created_at"] if c in df.columns), None)
        email_col = next((c for c in ["customer_email", "email", "billing_email"] if c in df.columns), None)
        status_col = next((c for c in ["status", "order_status"] if c in df.columns), None)
        sku_col = next((c for c in ["sku", "product_sku", "item_sku"] if c in df.columns), None)
        qty_col = next((c for c in ["quantity", "qty", "items_count"] if c in df.columns), None)
        first_name_col = next((c for c in ["first_name", "billing_first_name"] if c in df.columns), None)
        last_name_col = next((c for c in ["last_name", "billing_last_name"] if c in df.columns), None)

        imported_count = 0
        now = datetime.now(timezone.utc)

        # Cache existing orders to avoid duplicate PKs
        existing_orders = {o.order_number: o for o in self.db.query(Order).all()}
        all_prods = {p.sku.strip().lower(): p for p in self.db.query(Product).all() if p.sku}

        # Calculate max order ID for synthetic ID generation if needed
        max_order_id = self.db.query(Order.id).order_by(Order.id.desc()).first()
        next_order_id = (max_order_id[0] + 1) if max_order_id else 10001

        max_cust_id = self.db.query(Customer.id).order_by(Customer.id.desc()).first()
        next_cust_id = (max_cust_id[0] + 1) if max_cust_id else 5001

        for _, row in df.iterrows():
            try:
                order_num = str(row.get(order_col)).strip()
                clean_total = float(str(row.get(total_col)).replace("$", "").replace(",", "").strip())
                if clean_total < 0:
                    continue
            except Exception:
                continue

            # Parse date
            order_date = now
            if date_col and pd.notna(row.get(date_col)):
                try:
                    parsed_dt = pd.to_datetime(str(row.get(date_col)), utc=True)
                    order_date = parsed_dt.to_pydatetime()
                except Exception:
                    pass

            # Customer management
            cust = None
            if email_col and pd.notna(row.get(email_col)):
                cust_email = str(row.get(email_col)).strip().lower()
                cust = self.db.query(Customer).filter(Customer.email == cust_email).first()
                if not cust:
                    email_hash = hashlib.sha256(cust_email.encode("utf-8")).hexdigest()
                    cust = Customer(
                        id=next_cust_id,
                        store_id=self.store_id or 1,
                        email=cust_email,
                        email_hash=email_hash,
                        first_name=str(row.get(first_name_col, "Customer")),
                        last_name=str(row.get(last_name_col, "")),
                        created_at_utc=order_date
                    )
                    self.db.add(cust)
                    self.db.flush()
                    next_cust_id += 1

            status_val = str(row.get(status_col, "completed")).strip().lower()

            # Order upsert
            order = existing_orders.get(order_num)
            if not order:
                order = Order(
                    id=next_order_id,
                    store_id=self.store_id or 1,
                    customer_id=cust.id if cust else None,
                    order_number=order_num,
                    status=status_val,
                    currency="USD",
                    total_amount=clean_total,
                    discount_total=0.0,
                    shipping_total=0.0,
                    total_tax=0.0,
                    total_refunded=0.0,
                    net_sales=clean_total if status_val not in ["cancelled", "failed"] else 0.0,
                    date_created_utc=order_date
                )
                self.db.add(order)
                self.db.flush()
                existing_orders[order_num] = order
                next_order_id += 1
            else:
                order.total_amount = clean_total
                order.net_sales = clean_total if status_val not in ["cancelled", "failed"] else 0.0
                order.status = status_val

            # Line item if SKU provided
            if sku_col and pd.notna(row.get(sku_col)):
                item_sku = str(row.get(sku_col)).strip().lower()
                prod = all_prods.get(item_sku)
                qty = 1
                if qty_col and pd.notna(row.get(qty_col)):
                    try:
                        qty = max(1, int(float(str(row.get(qty_col)).strip())))
                    except Exception:
                        qty = 1

                line_item = OrderItem(
                    order_id=order.id,
                    product_id=prod.id if prod else None,
                    name=prod.name if prod else f"Item {item_sku.upper()}",
                    sku=item_sku.upper(),
                    quantity=qty,
                    unit_price=clean_total / qty if qty > 0 else clean_total,
                    subtotal=clean_total,
                    total=clean_total
                )
                self.db.add(line_item)

            imported_count += 1

        self.db.commit()
        return {
            "success": True,
            "imported_count": imported_count,
            "errors_count": val_result.error_rows,
            "errors": val_result.errors
        }

    # =========================================================================
    # 4. DOWNLOADABLE TEMPLATE GENERATORS
    # =========================================================================
    @staticmethod
    def generate_template(import_type: str, format_type: str = "csv") -> bytes:
        """Generates downloadable sample template file in CSV or Excel format."""
        if import_type == "costs":
            data = [
                {"sku": "ALT-RN-01", "product_name": "Altitude Pro Running Shoes", "unit_cost": 28.50},
                {"sku": "CPT-TI-02", "product_name": "Carbon Pulse Titanium Watch", "unit_cost": 49.00},
                {"sku": "VNT-SH-03", "product_name": "Venture Tech Shell Jacket", "unit_cost": 38.00},
                {"sku": "MTB-LS-05", "product_name": "Matrix Merino Base Layer", "unit_cost": 15.50},
                {"sku": "ZNT-FL-07", "product_name": "Zenith Cloud Knit Fleece", "unit_cost": 22.00},
            ]
        elif import_type == "inventory":
            data = [
                {"sku": "ALT-RN-01", "product_name": "Altitude Pro Running Shoes", "stock_quantity": 85, "stock_status": "instock"},
                {"sku": "CPT-TI-02", "product_name": "Carbon Pulse Titanium Watch", "stock_quantity": 42, "stock_status": "instock"},
                {"sku": "VNT-SH-03", "product_name": "Venture Tech Shell Jacket", "stock_quantity": 18, "stock_status": "instock"},
                {"sku": "MTB-LS-05", "product_name": "Matrix Merino Base Layer", "stock_quantity": 0, "stock_status": "outofstock"},
                {"sku": "ZNT-FL-07", "product_name": "Zenith Cloud Knit Fleece", "stock_quantity": 60, "stock_status": "instock"},
            ]
        elif import_type == "orders":
            data = [
                {"order_number": "ORD-9001", "date": "2026-10-15 14:30:00", "customer_email": "jane.doe@example.com", "first_name": "Jane", "last_name": "Doe", "sku": "ALT-RN-01", "quantity": 1, "total": 89.00, "status": "completed"},
                {"order_number": "ORD-9002", "date": "2026-10-16 09:15:00", "customer_email": "john.smith@example.com", "first_name": "John", "last_name": "Smith", "sku": "CPT-TI-02", "quantity": 1, "total": 149.00, "status": "completed"},
                {"order_number": "ORD-9003", "date": "2026-10-17 18:45:00", "customer_email": "alex.m@example.com", "first_name": "Alex", "last_name": "Morgan", "sku": "VNT-SH-03", "quantity": 2, "total": 230.00, "status": "completed"},
            ]
        else:
            raise ValueError(f"Unknown import template type: {import_type}")

        df = pd.DataFrame(data)

        if format_type.lower() in ["xlsx", "excel"]:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Import_Template")
            return output.getvalue()
        else:
            return df.to_csv(index=False).encode("utf-8")
