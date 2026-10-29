import random
import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.app.models.store import Store
from backend.app.models.product import Product, ProductCategory, ProductCategoryMapping, ProductVariation
from backend.app.models.customer import Customer
from backend.app.models.order import Order, OrderItem, Refund, RefundItem, OrderCoupon
from backend.app.models.cost import ProductCostHistory


def generate_sample_dataset(db: Session, seed: int = 42) -> Store:
    """Generates a comprehensive, realistic B2C WooCommerce dataset spanning the last 180 days."""
    random.seed(seed)

    # 1. Create or fetch store
    existing_store = db.query(Store).filter(Store.store_url == "https://demo.apexlifestyle.co").first()
    if existing_store:
        return existing_store

    store = Store(
        store_url="https://demo.apexlifestyle.co",
        name="Apex Lifestyle & Apparel Co.",
        consumer_key="ck_sample_demo_apex_ecom_key_2026",
        consumer_secret="cs_sample_demo_apex_ecom_secret_2026",
        currency="USD",
        timezone="UTC",
        is_active=True,
        last_sync_at=datetime.now(timezone.utc)
    )
    db.add(store)
    db.flush()

    # 2. Product Categories
    categories_data = [
        ("Performance Activewear", "activewear"),
        ("Technical Footwear", "footwear"),
        ("Smart Accessories", "accessories"),
        ("Hydration & Nutrition", "hydration-nutrition"),
        ("Travel & Everyday Packs", "packs-bags"),
        ("Recovery & Wellness", "recovery")
    ]
    categories = []
    for cat_name, cat_slug in categories_data:
        cat = ProductCategory(
            id=random.randint(100, 999),
            store_id=store.id,
            name=cat_name,
            slug=cat_slug,
            count=0
        )
        db.add(cat)
        categories.append(cat)
    db.flush()

    # 3. Products catalogue with unit costs (COGS)
    raw_products = [
        # Activewear
        ("AeroLite Seamless Running Tee", "ALT-RN-01", 48.0, 16.0, 120, categories[0]),
        ("Core Pro Compression Tights", "CPT-TI-02", 78.0, 26.0, 85, categories[0]),
        ("Ventus Ultra-Breathe Shorts", "VNT-SH-03", 54.0, 18.0, 95, categories[0]),
        ("Element Weatherproof Shell Jacket", "EWS-JK-04", 165.0, 62.0, 40, categories[0]),
        ("Merino Thermal Baselayer", "MTB-LS-05", 88.0, 32.0, 60, categories[0]),
        ("SprintFlex Training Tank", "SFT-TK-06", 42.0, 14.0, 150, categories[0]),

        # Footwear
        ("Strata Glide Carbon Racer", "SGC-FW-07", 220.0, 85.0, 30, categories[1]),
        ("CloudTerra Trail Cruiser", "CTC-FW-08", 160.0, 60.0, 45, categories[1]),
        ("Nova Flow Daily Trainer", "NFD-FW-09", 135.0, 50.0, 70, categories[1]),
        ("Apex Recovery Slide V2", "ARS-FW-10", 55.0, 18.0, 110, categories[1]),

        # Smart Accessories
        ("PaceTrack Pro GPS Heart Rate Monitor", "PTP-AC-11", 119.0, 42.0, 55, categories[2]),
        ("Titanium Ergonomic Sport Sunglasses", "TES-AC-12", 145.0, 48.0, 35, categories[2]),
        ("Reflective Night Runner Headband 2-Pack", "RNR-AC-13", 24.0, 6.0, 200, categories[2]),
        ("AeroGrip Touchscreen Gloves", "AGT-AC-14", 34.0, 11.0, 130, categories[2]),

        # Hydration & Nutrition
        ("HydroShield Vacuum Insulated Flask 750ml", "HSV-HN-15", 38.0, 12.0, 180, categories[3]),
        ("ElectroBoost Electrolyte Powder 30-Pack", "EBE-HN-16", 32.0, 9.0, 240, categories[3]),
        ("Organic Energy Gel Variety Pack 12ct", "OEG-HN-17", 28.0, 8.5, 300, categories[3]),
        ("Whey Isolate Clean Protein (Vanilla)", "WIC-HN-18", 58.0, 22.0, 90, categories[3]),

        # Packs & Bags
        ("Expedition 30L Commuter Duffel", "E30-PK-19", 125.0, 44.0, 40, categories[4]),
        ("Apex Stealth Running Waist Pack", "ASW-PK-20", 35.0, 10.0, 160, categories[4]),
        ("HydraPulse 10L Ultra Vest", "HPU-PK-21", 110.0, 38.0, 50, categories[4]),

        # Recovery
        ("HyperPulse Deep Tissue Massage Gun", "HPD-RC-22", 189.0, 65.0, 25, categories[5]),
        ("Density Grid Foam Roller 26in", "DGF-RC-23", 42.0, 12.0, 75, categories[5]),
        ("CryoTherapy Ice Compression Knee Sleeve", "CTC-RC-24", 49.0, 15.0, 80, categories[5]),
    ]

    products = []
    pid_counter = 1001
    for name, sku, price, cost, stock, cat in raw_products:
        prod = Product(
            id=pid_counter,
            store_id=store.id,
            name=name,
            sku=sku,
            type="simple",
            status="publish",
            regular_price=price,
            sale_price=price if random.random() > 0.3 else round(price * 0.85, 2),
            current_cost=cost,
            stock_quantity=stock,
            stock_status="instock" if stock > 0 else "outofstock",
            manage_stock=True,
            total_sales=0,
            average_rating=round(random.uniform(4.2, 4.9), 1),
            rating_count=random.randint(15, 120),
            created_at_utc=datetime.now(timezone.utc) - timedelta(days=220)
        )
        db.add(prod)
        db.flush()

        # Add Category Mapping
        mapping = ProductCategoryMapping(product_id=prod.id, category_id=cat.id)
        db.add(mapping)

        # Add Cost History
        cost_entry = ProductCostHistory(
            product_id=prod.id,
            sku=prod.sku,
            unit_cost=cost,
            effective_date=datetime.now(timezone.utc) - timedelta(days=200),
            source="initial_seed",
            notes="Standard initial inventory unit cost"
        )
        db.add(cost_entry)

        products.append(prod)
        pid_counter += 1
    db.flush()

    # 4. Customers
    cities = [
        ("Austin", "TX", "US"), ("Seattle", "WA", "US"), ("New York", "NY", "US"),
        ("Denver", "CO", "US"), ("Chicago", "IL", "US"), ("San Francisco", "CA", "US"),
        ("Toronto", "ON", "CA"), ("Vancouver", "BC", "CA"), ("London", "ENG", "GB"),
        ("Sydney", "NSW", "AU"), ("Melbourne", "VIC", "AU"), ("Miami", "FL", "US")
    ]

    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Casey", "Riley", "Jamie", "Avery", "Cameron", "Dakota", "Reese", "Quinn", "Skyler", "Jesse"]
    last_names = ["Vance", "Mercer", "Chen", "Sterling", "Hayes", "Kowalski", "Patel", "Novak", "O'Connor", "Sinclair", "Kim", "Bennett", "Rhodes", "Hawthorne"]

    customers = []
    for cid in range(2001, 2121):  # 120 realistic customers
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        city, state, country = random.choice(cities)
        email = f"{fn.lower()}.{ln.lower()}{cid % 89}@example.com"
        email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()

        cust = Customer(
            id=cid,
            store_id=store.id,
            email=email,
            email_hash=email_hash,
            first_name=fn,
            last_name=ln,
            username=f"{fn.lower()}{cid}",
            billing_city=city,
            billing_state=state,
            billing_country=country,
            billing_postcode=f"{random.randint(10000, 99999)}",
            orders_count=0,
            total_spent=0.0,
            created_at_utc=datetime.now(timezone.utc) - timedelta(days=random.randint(20, 180))
        )
        db.add(cust)
        customers.append(cust)
    db.flush()

    # 5. Orders Generation over 180 days with realistic trends
    payment_methods = [
        ("stripe", "Credit Card (Stripe)", 0.60),
        ("paypal", "PayPal Express", 0.25),
        ("apple_pay", "Apple Pay", 0.10),
        ("klarna", "Klarna Buy Now Pay Later", 0.05)
    ]
    shipping_methods = [
        ("Standard Ground (3-5 Days)", 6.95, 0.65),
        ("Express 2-Day Air", 14.95, 0.25),
        ("Free Shipping (Orders $150+)", 0.0, 0.10)
    ]
    coupons_list = [
        ("SUMMER20", 0.20, 0.15),
        ("WELCOME10", 0.10, 0.25),
        ("VIP25", 0.25, 0.08)
    ]

    now = datetime.now(timezone.utc)
    order_id_seq = 5001
    item_id_seq = 8001
    refund_id_seq = 9001

    for days_ago in range(180, -1, -1):
        # Weekday uplift + growth trend over time
        day_date = now - timedelta(days=days_ago)
        is_weekend = day_date.weekday() >= 5
        base_orders = 4 if is_weekend else 6
        # Slight upward trend in recent months
        growth_factor = 1.0 + ((180 - days_ago) / 180.0) * 0.4
        orders_today = int(random.gauss(base_orders * growth_factor, 1.5))
        orders_today = max(2, orders_today)

        for _ in range(orders_today):
            order_id = order_id_seq
            order_id_seq += 1

            # Order timestamp (peak hours 10:00 to 21:00)
            hour = int(random.choices(
                list(range(24)),
                weights=[1, 1, 1, 1, 1, 2, 3, 5, 8, 10, 12, 11, 12, 10, 9, 8, 10, 12, 13, 11, 9, 6, 4, 2]
            )[0])
            minute = random.randint(0, 59)
            order_time = day_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))

            # Status distribution: 88% completed, 5% processing, 4% cancelled, 3% refunded
            status_rand = random.random()
            if status_rand < 0.88:
                status = "completed"
            elif status_rand < 0.93:
                status = "processing"
            elif status_rand < 0.97:
                status = "cancelled"
            else:
                status = "refunded"

            customer = random.choice(customers)
            pm = random.choices([p[0] for p in payment_methods], weights=[p[2] for p in payment_methods])[0]
            pm_title = next(p[1] for p in payment_methods if p[0] == pm)

            sm_choice = random.choices(shipping_methods, weights=[s[2] for s in shipping_methods])[0]
            shipping_title = sm_choice[0]
            shipping_fee = sm_choice[1]

            # Line items (1 to 4 products)
            num_items = random.choices([1, 2, 3, 4], weights=[0.55, 0.30, 0.10, 0.05])[0]
            selected_prods = random.sample(products, num_items)

            items_subtotal = 0.0
            order_line_items = []
            for prod in selected_prods:
                qty = random.choices([1, 2, 3], weights=[0.80, 0.15, 0.05])[0]
                unit_price = prod.sale_price if prod.sale_price else prod.regular_price
                line_subtotal = round(unit_price * qty, 2)
                items_subtotal += line_subtotal

                item = OrderItem(
                    id=item_id_seq,
                    order_id=order_id,
                    product_id=prod.id,
                    name=prod.name,
                    sku=prod.sku,
                    quantity=qty,
                    unit_price=unit_price,
                    subtotal=line_subtotal,
                    total=line_subtotal,  # will adjust if coupon applied
                    subtotal_tax=round(line_subtotal * 0.07, 2),
                    total_tax=round(line_subtotal * 0.07, 2)
                )
                item_id_seq += 1
                order_line_items.append(item)

            # Coupon check
            applied_coupon = None
            discount_amount = 0.0
            if random.random() < 0.28:
                c_choice = random.choices(coupons_list, weights=[c[2] for c in coupons_list])[0]
                discount_amount = round(items_subtotal * c_choice[1], 2)
                applied_coupon = c_choice[0]

                # Distribute discount across line items
                ratio = (items_subtotal - discount_amount) / items_subtotal if items_subtotal > 0 else 1.0
                for item in order_line_items:
                    item.total = round(item.subtotal * ratio, 2)

            tax_total = round((items_subtotal - discount_amount + shipping_fee) * 0.07, 2)
            total_amount = round(items_subtotal - discount_amount + shipping_fee + tax_total, 2)

            # Refund handling
            total_refunded = 0.0
            is_refund_order = (status == "refunded") or (status == "completed" and random.random() < 0.04)

            order = Order(
                id=order_id,
                store_id=store.id,
                customer_id=customer.id,
                order_number=f"ORD-{order_id}",
                status=status,
                currency="USD",
                total_amount=total_amount,
                discount_total=discount_amount,
                shipping_total=shipping_fee,
                total_tax=tax_total,
                shipping_tax=0.0,
                total_refunded=0.0,
                net_sales=max(0.0, items_subtotal - discount_amount),
                payment_method=pm,
                payment_method_title=pm_title,
                shipping_method=shipping_title,
                billing_city=customer.billing_city,
                billing_state=customer.billing_state,
                billing_country=customer.billing_country,
                billing_postcode=customer.billing_postcode,
                date_created_utc=order_time,
                date_completed_utc=order_time + timedelta(hours=random.randint(6, 48)) if status in ["completed", "refunded"] else None,
                date_paid_utc=order_time + timedelta(minutes=5) if status != "failed" else None
            )
            db.add(order)
            db.flush()

            for item in order_line_items:
                db.add(item)

            if applied_coupon:
                oc = OrderCoupon(
                    order_id=order.id,
                    code=applied_coupon,
                    discount_amount=discount_amount,
                    discount_tax=round(discount_amount * 0.07, 2)
                )
                db.add(oc)

            # Process refund record if refunded
            if is_refund_order:
                # Full or partial refund
                refund_pct = 1.0 if status == "refunded" else random.choice([0.5, 1.0])
                refund_val = round(order.net_sales * refund_pct, 2)
                order.total_refunded = refund_val
                order.net_sales = max(0.0, order.net_sales - refund_val)

                ref = Refund(
                    id=refund_id_seq,
                    order_id=order.id,
                    amount=refund_val,
                    reason="Customer returned merchandise / sizing exchange",
                    date_created_utc=order_time + timedelta(days=random.randint(1, 14))
                )
                refund_id_seq += 1
                db.add(ref)
                db.flush()

                # Refund items line mapping
                for it in order_line_items:
                    ref_item = RefundItem(
                        refund_id=ref.id,
                        order_item_id=it.id,
                        product_id=it.product_id,
                        quantity=it.quantity if refund_pct == 1.0 else 1,
                        refund_subtotal=round(it.subtotal * refund_pct, 2),
                        refund_total=round(it.total * refund_pct, 2)
                    )
                    db.add(ref_item)

            # Update customer counters
            if status in ["completed", "processing"]:
                customer.orders_count += 1
                customer.total_spent += order.net_sales

    db.commit()
    return store
