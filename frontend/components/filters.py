import sys
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Any, Tuple
import streamlit as st

# Ensure project root is in sys.path
ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy.orm import Session
from backend.app.models.product import ProductCategory, Product
from backend.app.models.store import Store


def render_global_filter_bar(db: Session, store: Store) -> Dict[str, Any]:
    """Renders the top filter controls bar and returns the active filter state."""
    st.markdown("""
    <div class="filter-header-bar">
        <div class="filter-header-left">
            <span style="font-size: 1rem;">🔍</span>
            <span class="filter-title">Global Dashboard Filters</span>
        </div>
        <span class="filter-badge">Period & Slice Controls</span>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1.8, 1.8, 1.4, 1.2])

    with c1:
        preset = st.selectbox(
            "Reporting Window",
            options=[
                ("last_30_days", "Last 30 Days"),
                ("last_7_days", "Last 7 Days"),
                ("today", "Today"),
                ("yesterday", "Yesterday"),
                ("last_90_days", "Last 90 Days"),
                ("this_month", "This Month (MTD)"),
                ("previous_month", "Previous Month"),
                ("this_quarter", "This Quarter (QTD)"),
                ("this_year", "This Year (YTD)"),
                ("custom", "Custom Date Range")
            ],
            format_func=lambda x: x[1],
            index=0,
            key="filter_preset"
        )[0]

    custom_start = None
    custom_end = None
    if preset == "custom":
        with c2:
            date_range = st.date_input(
                "Select Custom Range",
                value=(date.today() - timedelta(days=30), date.today()),
                max_value=date.today(),
                key="filter_custom_dates"
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                custom_start, custom_end = date_range
    else:
        with c2:
            # Category filter
            categories = db.query(ProductCategory).filter(ProductCategory.store_id == store.id).all()
            cat_options = [(0, "All Categories")] + [(c.id, c.name) for c in categories]
            selected_cat = st.selectbox(
                "Product Category",
                options=cat_options,
                format_func=lambda x: x[1],
                key="filter_category"
            )[0]

    with c3:
        order_status = st.selectbox(
            "Order Status",
            options=["All Valid (Completed + Processing)", "Completed Only", "Processing Only", "All Placed Orders"],
            index=0,
            key="filter_order_status"
        )

    with c4:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        refresh_btn = st.button("🔄 Refresh", use_container_width=True, key="filter_refresh_btn")

    # Map status string
    status_map = {
        "All Valid (Completed + Processing)": None,
        "Completed Only": "completed",
        "Processing Only": "processing",
        "All Placed Orders": "all"
    }

    return {
        "preset": preset,
        "custom_start": custom_start,
        "custom_end": custom_end,
        "category_id": selected_cat if preset != "custom" and selected_cat > 0 else None,
        "order_status": status_map.get(order_status),
        "currency": store.currency or "USD"
    }
