import os
import sys
from pathlib import Path

# Ensure project root is in sys.path so 'backend' and 'frontend' modules are resolved
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import io
import random
from datetime import datetime, date, timezone
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy.orm import Session

from backend.app.database import init_db, SessionLocal
from backend.app.models.store import Store
from backend.app.models.product import Product, ProductCategory
from backend.app.models.order import Order
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.insights_engine import InsightsEngine
from backend.app.services.ai_report_service import AIReportService
from backend.app.services.import_service import DataImportService
from backend.app.services.export_service import ExportService
from backend.app.services.sync_service import SyncService
from backend.app.services.woocommerce_client import WooCommerceClient
from backend.app.services.sample_data_generator import generate_sample_dataset
from backend.app.utils.timezone import get_period_dates
from backend.app.utils.currency import format_currency
from frontend.components.kpi_cards import render_kpi_grid
from frontend.components.charts import (
    render_revenue_trend_chart, render_product_ranking_chart,
    render_category_donut_chart, render_heatmap_7x24, render_cohort_retention_heatmap
)
from frontend.components.filters import render_global_filter_bar

# Initialize Streamlit Page Config
st.set_page_config(
    page_title="WooCommerce B2C Sales Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS
css_path = os.path.join(os.path.dirname(__file__), "styles", "modern_theme.css")
if os.path.exists(css_path):
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Database Session Helper
@st.cache_resource
def get_db_session():
    init_db()
    return SessionLocal()


db: Session = get_db_session()

# Ensure at least one store exists
store = db.query(Store).filter(Store.is_active == True).first()
if not store:
    store = generate_sample_dataset(db, seed=42)

# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================
with st.sidebar:
    st.markdown("""
    <div style="padding: 10px 0 20px 0;">
        <h2 style="font-weight: 800; margin: 0; color: #F8FAFC; letter-spacing: -0.02em;">
            ⚡ CommercePulse
        </h2>
        <span style="font-size: 0.75rem; color: #60A5FA; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em;">
            B2C Sales Intelligence
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Store quick status card
    st.markdown(f"""
    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; margin-bottom: 1.25rem;">
        <div style="font-size: 0.75rem; color: #94A3B8;">ACTIVE STORE</div>
        <div style="font-size: 0.9rem; font-weight: 700; color: #F8FAFC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            {store.name}
        </div>
        <div style="font-size: 0.75rem; color: #10B981; margin-top: 4px;">● Connected ({store.currency})</div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        options=[
            "📊 Executive Overview",
            "🏷️ Product Intelligence",
            "📈 Revenue Analytics",
            "📂 Category Intelligence",
            "👥 Customer Intelligence",
            "📦 Order Analytics",
            "💡 Business Insights & AI Reports",
            "🔌 WooCommerce Sync",
            "📥 Data Imports & Product Costs",
            "⚙️ Settings & System"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("""
    <div style="font-size: 0.75rem; color: #64748B; text-align: center;">
        WooCommerce Intelligence Platform v1.0<br/>Production Analytics Engine
    </div>
    """, unsafe_allow_html=True)

# Shared Service Instances
analytics = AnalyticsEngine(db, store_id=store.id)
insights_engine = InsightsEngine(analytics)
exporter = ExportService(analytics)
ai_service = AIReportService(analytics)

# =============================================================================
# 1. EXECUTIVE OVERVIEW DASHBOARD
# =============================================================================
if page == "📊 Executive Overview":
    # Header Banner
    st.markdown(f"""
    <div class="brand-header-container">
        <div>
            <h1 class="brand-title">Executive Sales Intelligence</h1>
            <div class="brand-subtitle">
                Real-time financial reconciliation & growth diagnostics for {store.name}
            </div>
        </div>
        <div>
            <span class="brand-badge">● LIVE ANALYTICS</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Global Filter Bar
    filters = render_global_filter_bar(db, store)
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(
        filters["preset"], filters["custom_start"], filters["custom_end"]
    )

    # Quick Export Row
    exp_col1, exp_col2, exp_col3 = st.columns([6, 1.5, 1.5])
    with exp_col2:
        excel_data = exporter.generate_excel_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=filters["currency"])
        st.download_button(
            label="📥 Export Excel",
            data=excel_data,
            file_name=f"CommercePulse_Analytics_{start_utc.strftime('%Y%m%d')}_{end_utc.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with exp_col3:
        pdf_data = exporter.generate_pdf_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=filters["currency"])
        st.download_button(
            label="📄 Export PDF",
            data=pdf_data,
            file_name=f"Executive_BI_Report_{start_utc.strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # 1. KPI Cards Grid
    kpis = analytics.get_executive_kpis(
        start_utc=start_utc,
        end_utc=end_utc,
        prev_start_utc=prev_start_utc,
        prev_end_utc=prev_end_utc,
        category_id=filters["category_id"],
        order_status=filters["order_status"],
        currency=filters["currency"]
    )
    render_kpi_grid(kpis)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # 2. Main Visualizations
    col_chart1, col_chart2 = st.columns([2.2, 1.3])

    with col_chart1:
        revenue_series = analytics.get_revenue_time_series(start_utc, end_utc, interval="daily")
        fig_rev = render_revenue_trend_chart(revenue_series, currency=filters["currency"])
        st.plotly_chart(fig_rev, use_container_width=True)

    with col_chart2:
        categories_data = analytics.get_category_analytics(start_utc, end_utc, prev_start_utc, prev_end_utc)
        fig_cat = render_category_donut_chart(categories_data, currency=filters["currency"])
        st.plotly_chart(fig_cat, use_container_width=True)

    # 3. Top Products Quick Glance & High-Priority Insights
    c_p1, c_p2 = st.columns([1.8, 1.2])

    with c_p1:
        st.subheader("Top 5 Revenue Generating Products")
        top_5_prods = analytics.get_product_performance(start_utc, end_utc, prev_start_utc, prev_end_utc, rank_by="net_sales", limit=5)
        if top_5_prods:
            df_top = pd.DataFrame([{
                "Product": p["name"],
                "SKU": p["sku"],
                "Units Sold": f"{p['units_sold']:,}",
                "Net Sales": format_currency(p["net_sales"], filters["currency"]),
                "Margin %": f"{p['gross_margin_pct']:.1f}%" if p["gross_margin_pct"] is not None else "N/A",
                "Growth": f"{p['growth_pct']:+.1f}%",
                "Class": p["classification"]
            } for p in top_5_prods])
            st.dataframe(df_top, use_container_width=True, hide_index=True)

    with c_p2:
        st.subheader("Key Prescriptive Insights")
        top_insights = insights_engine.generate_insights(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=filters["currency"])
        for ins in top_insights[:2]:
            st.markdown(f"""
            <div class="insight-card insight-{ins['severity'].lower()}">
                <div class="insight-title">{ins['title']}</div>
                <div class="insight-explanation">{ins['explanation']}</div>
                <div class="insight-action-box">💡 <b>Action:</b> {ins['suggested_action']}</div>
            </div>
            """, unsafe_allow_html=True)

# =============================================================================
# 2. PRODUCT PERFORMANCE INTELLIGENCE
# =============================================================================
elif page == "🏷️ Product Intelligence":
    st.title("Product Performance Intelligence & Profitability")
    st.markdown("Detailed merchandise rankings, 9-class product performance taxonomy, gross margins, and multi-product comparisons.")

    filters = render_global_filter_bar(db, store)
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(
        filters["preset"], filters["custom_start"], filters["custom_end"]
    )

    tab_rank, tab_compare, tab_taxonomy = st.tabs(["🏆 Product Rankings & Margins", "📊 Product Trend Comparison", "🏷️ 9-Class Performance Taxonomy Rules"])

    with tab_rank:
        # Ranking criteria switch
        r_col1, r_col2, r_col3 = st.columns([2, 1.5, 1.5])
        with r_col1:
            rank_criteria = st.selectbox(
                "Rank Products By",
                options=[
                    ("units_sold", "Units Sold (Volume)"),
                    ("net_sales", "Net Sales (Top-Line Revenue)"),
                    ("gross_sales", "Gross Sales"),
                    ("orders_count", "Number of Orders"),
                    ("growth_pct", "Period Growth % (Velocity)"),
                    ("gross_profit", "Gross Profit (when cost data exists)")
                ],
                format_func=lambda x: x[1],
                index=0
            )[0]

        with r_col2:
            class_filter = st.selectbox(
                "Filter by Classification",
                options=["All Classes", "Best Seller", "Rising Star", "Declining", "Low Performer", "High Revenue", "High Margin", "High Refund Risk", "Discount Dependent", "Stockout Risk"],
                index=0
            )

        with r_col3:
            limit_count = st.number_input("Display Limit", min_value=5, max_value=100, value=20, step=5)

        # Query products
        products_perf = analytics.get_product_performance(
            start_utc, end_utc, prev_start_utc, prev_end_utc,
            rank_by=rank_criteria, limit=limit_count, category_id=filters["category_id"]
        )

        if class_filter != "All Classes":
            products_perf = [p for p in products_perf if p.get("classification") == class_filter]

        # Horizontal Bar Chart
        fig_bar = render_product_ranking_chart(products_perf, rank_col=rank_criteria, currency=filters["currency"])
        st.plotly_chart(fig_bar, use_container_width=True)

        # Interactive Table
        if products_perf:
            table_rows = []
            for p in products_perf:
                table_rows.append({
                    "Product Name": p["name"],
                    "SKU": p["sku"],
                    "Category": p["category"],
                    "Units Sold": p["units_sold"],
                    "Orders": p["orders_count"],
                    "Gross Sales": format_currency(p["gross_sales"], filters["currency"]),
                    "Discounts": format_currency(p["discounts"], filters["currency"]),
                    "Refunds": format_currency(p["refunds"], filters["currency"]),
                    "Net Sales": format_currency(p["net_sales"], filters["currency"]),
                    "% Net Sales": f"{p['net_sales_percentage']:.1f}%",
                    "Avg Selling Price": format_currency(p["average_selling_price"], filters["currency"]),
                    "COGS": format_currency(p["cogs"], filters["currency"]) if p["cogs"] is not None else "Unavailable (No Cost)",
                    "Gross Profit": format_currency(p["gross_profit"], filters["currency"]) if p["gross_profit"] is not None else "Unavailable",
                    "Gross Margin %": f"{p['gross_margin_pct']:.1f}%" if p["gross_margin_pct"] is not None else "N/A",
                    "Growth %": f"{p['growth_pct']:+.1f}%",
                    "Classification": p["classification"]
                })

            df_table = pd.DataFrame(table_rows)
            st.dataframe(df_table, use_container_width=True, hide_index=True)

            # CSV Download
            csv_buf = df_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Filtered Products CSV",
                data=csv_buf,
                file_name="products_performance.csv",
                mime="text/csv"
            )
        else:
            st.info("No products match the selected filters.")

    with tab_compare:
        st.subheader("Multi-Product Comparison")
        all_store_prods = db.query(Product).filter(Product.store_id == store.id).all()
        prod_options = {p.id: f"{p.name} ({p.sku or 'No SKU'})" for p in all_store_prods}

        selected_prod_ids = st.multiselect(
            "Select Products to Compare (up to 4)",
            options=list(prod_options.keys()),
            format_func=lambda x: prod_options[x],
            default=list(prod_options.keys())[:3] if len(prod_options) >= 3 else list(prod_options.keys())
        )

        if selected_prod_ids:
            compare_rows = []
            for pid in selected_prod_ids:
                p_perf = analytics.get_product_performance(start_utc, end_utc, prev_start_utc, prev_end_utc, limit=100)
                matched = next((p for p in p_perf if p["product_id"] == pid), None)
                if matched:
                    compare_rows.append(matched)

            if compare_rows:
                df_comp = pd.DataFrame(compare_rows)
                # Grouped bar chart comparing Units and Net Sales
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=df_comp["name"],
                    y=df_comp["units_sold"],
                    name="Units Sold",
                    marker_color="#3B82F6"
                ))
                fig_comp.add_trace(go.Bar(
                    x=df_comp["name"],
                    y=df_comp["net_sales"],
                    name="Net Sales ($)",
                    yaxis="y2",
                    marker_color="#10B981"
                ))
                fig_comp.update_layout(
                    title="<b>Comparative Volume vs Net Sales</b>",
                    yaxis=dict(title="Units Sold"),
                    yaxis2=dict(title="Net Sales ($)", overlaying="y", side="right"),
                    barmode="group",
                    paper_bgcolor="rgba(30, 41, 59, 0.4)",
                    plot_bgcolor="rgba(15, 23, 42, 0.6)",
                    font=dict(color="#CBD5E1")
                )
                st.plotly_chart(fig_comp, use_container_width=True)

    with tab_taxonomy:
        st.subheader("9-Class Product Performance Taxonomy Definitions")
        st.markdown(r"""
        Every product in the catalog is dynamically evaluated against objective statistical thresholds:
        - **Best Seller**: Top 20% in volume and net sales contribution across the period.
        - **Rising Star**: >25% unit sales growth compared to the prior baseline period (minimum 5 units).
        - **Declining**: <-20% unit sales decrease compared to the prior baseline period.
        - **Low Performer**: Bottom 25% in sales volume with stagnant or negative velocity.
        - **High Revenue**: Generates >=10% of total store net sales.
        - **High Margin**: Demonstrates gross margin $\ge 50\%$ when unit costs (COGS) are recorded.
        - **High Refund Risk**: Refund rate exceeds $1.5\times$ store average (minimum 3 returns).
        - **Discount Dependent**: Promotional discounts account for $\ge 25\%$ of gross sales.
        - **Stockout Risk**: Warehouse inventory is below 10 units with high demand velocity.
        """)

# =============================================================================
# 3. REVENUE ANALYTICS
# =============================================================================
elif page == "📈 Revenue Analytics":
    st.title("Revenue & Sales Intelligence")
    filters = render_global_filter_bar(db, store)
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(
        filters["preset"], filters["custom_start"], filters["custom_end"]
    )

    t_col1, t_col2 = st.columns([2, 1])
    with t_col1:
        interval_choice = st.radio("Time Interval", ["Daily", "Weekly", "Monthly"], horizontal=True)
    with t_col2:
        st.metric("Total Revenue Collected", format_currency(analytics.calculate_period_metrics(start_utc, end_utc)["total_revenue_collected"], filters["currency"]))

    # Time series
    series_data = analytics.get_revenue_time_series(start_utc, end_utc, interval=interval_choice.lower())
    fig_time = render_revenue_trend_chart(series_data, currency=filters["currency"])
    st.plotly_chart(fig_time, use_container_width=True)

    # Heatmap of 7x24 peak shopping hours
    st.subheader("Peak Sales Hours & Weekday Velocity Heatmap")
    heatmap_data = analytics.get_sales_heatmaps(start_utc, end_utc)
    fig_heat = render_heatmap_7x24(heatmap_data)
    st.plotly_chart(fig_heat, use_container_width=True)

    # Breakdowns
    st.subheader("Payment, Shipping & Geographic Distribution")
    breakdowns = analytics.get_breakdowns(start_utc, end_utc)

    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown("**By Payment Method**")
        if breakdowns["payment_methods"]:
            df_pm = pd.DataFrame(breakdowns["payment_methods"])
            st.dataframe(df_pm, use_container_width=True, hide_index=True)
        else:
            st.write("No payment data recorded.")

    with b2:
        st.markdown("**By Shipping Method**")
        if breakdowns["shipping_methods"]:
            df_sm = pd.DataFrame(breakdowns["shipping_methods"])
            st.dataframe(df_sm, use_container_width=True, hide_index=True)
        else:
            st.write("No shipping data recorded.")

    with b3:
        st.markdown("**By Country**")
        if breakdowns["countries"]:
            df_geo = pd.DataFrame(breakdowns["countries"])
            st.dataframe(df_geo, use_container_width=True, hide_index=True)
        else:
            st.write("No geographic data recorded.")

# =============================================================================
# 4. CATEGORY INTELLIGENCE
# =============================================================================
elif page == "📂 Category Intelligence":
    st.title("Category Intelligence & Drilldown")
    filters = render_global_filter_bar(db, store)
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(
        filters["preset"], filters["custom_start"], filters["custom_end"]
    )

    categories = analytics.get_category_analytics(start_utc, end_utc, prev_start_utc, prev_end_utc)

    c_col1, c_col2 = st.columns([1.5, 2.5])
    with c_col1:
        fig_cat = render_category_donut_chart(categories, currency=filters["currency"])
        st.plotly_chart(fig_cat, use_container_width=True)

    with c_col2:
        st.subheader("Category Performance Breakdown")
        if categories:
            df_cat = pd.DataFrame([{
                "Category": c["name"],
                "Net Sales": format_currency(c["net_sales"], filters["currency"]),
                "Share %": f"{c['sales_contribution_pct']:.1f}%",
                "Units Sold": c["units_sold"],
                "Orders": c["orders_count"],
                "AOV": format_currency(c["aov"], filters["currency"]),
                "Growth": f"{c['growth_pct']:+.1f}%"
            } for c in categories])
            st.dataframe(df_cat, use_container_width=True, hide_index=True)

    st.subheader("Category Products Drill-down")
    if categories:
        chosen_cat = st.selectbox("Select Category to Inspect Products", [c["name"] for c in categories])
        cat_obj = next((c for c in categories if c["name"] == chosen_cat), None)
        if cat_obj:
            cat_prods = analytics.get_product_performance(start_utc, end_utc, prev_start_utc, prev_end_utc, category_id=cat_obj["category_id"])
            df_cp = pd.DataFrame([{
                "Product": p["name"],
                "SKU": p["sku"],
                "Units Sold": p["units_sold"],
                "Net Sales": format_currency(p["net_sales"], filters["currency"]),
                "Margin %": f"{p['gross_margin_pct']:.1f}%" if p["gross_margin_pct"] is not None else "N/A",
                "Class": p["classification"]
            } for p in cat_prods])
            st.dataframe(df_cp, use_container_width=True, hide_index=True)

# =============================================================================
# 5. CUSTOMER INTELLIGENCE
# =============================================================================
elif page == "👥 Customer Intelligence":
    st.title("B2C Customer Intelligence & Retention")
    customer_data = analytics.get_customer_segments()
    summary = customer_data.get("summary", {})
    segments = customer_data.get("segments", {})

    # Customer KPI cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Customer Accounts", f"{summary.get('total_customers', 0):,}")
    with c2:
        st.metric("Repeat Purchase Rate", f"{summary.get('repeat_rate_pct', 0.0):.1f}%")
    with c3:
        st.metric("Avg Orders / Customer", f"{summary.get('avg_orders_per_customer', 0.0):.2f}")
    with c4:
        st.metric("Avg Customer Lifetime Sales", format_currency(summary.get("avg_customer_lifetime_rev", 0.0), store.currency))

    st.markdown("---")

    col_seg, col_cohort = st.columns([1.2, 1.8])
    with col_seg:
        st.subheader("Behavioral Segments")
        st.markdown(f"""
        - 💎 **High-Value Customers**: `{segments.get('high_value', 0)}` accounts (Top 15% spenders)
        - 🔄 **Frequent Buyers**: `{segments.get('frequent_buyers', 0)}` accounts (3+ orders)
        - 🛒 **One-Time Buyers**: `{segments.get('one_time', 0)}` accounts
        - 💤 **Inactive (>90 Days)**: `{segments.get('inactive', 0)}` accounts
        - ⚠️ **Declining Frequency**: `{segments.get('declining', 0)}` accounts
        """)

    with col_cohort:
        st.subheader("Customer Monthly Retention Matrix")
        cohort_records = customer_data.get("cohort_data", [])
        if cohort_records:
            fig_cohort = render_cohort_retention_heatmap(cohort_records)
            st.plotly_chart(fig_cohort, use_container_width=True)
        else:
            st.info("Cohort data requires at least 2 distinct calendar months of order history.")

# =============================================================================
# 6. ORDER ANALYTICS
# =============================================================================
elif page == "📦 Order Analytics":
    st.title("Order & Fulfillment Analytics")
    filters = render_global_filter_bar(db, store)
    start_utc, end_utc, _, _ = get_period_dates(filters["preset"], filters["custom_start"], filters["custom_end"])

    order_metrics = analytics.get_order_analytics(start_utc, end_utc)
    fulfillment = order_metrics.get("fulfillment", {})
    basket = order_metrics.get("basket_metrics", {})
    status_dist = order_metrics.get("status_distribution", {})

    o1, o2, o3 = st.columns(3)
    with o1:
        st.metric("Avg Fulfillment Time", f"{fulfillment.get('avg_fulfillment_hours', 0.0):.1f} hrs", f"{fulfillment.get('avg_fulfillment_days', 0.0):.1f} days")
    with o2:
        st.metric("Avg Items per Order", f"{basket.get('avg_units_per_order', 0.0):.1f} units")
    with o3:
        st.metric("Multi-Item Orders %", f"{basket.get('multi_item_orders_pct', 0.0):.1f}%")

    st.subheader("Order Status Distribution")
    if status_dist:
        df_status = pd.DataFrame([{"Status": k.title(), "Count": v} for k, v in status_dist.items()])
        fig_st = px.pie(df_status, names="Status", values="Count", hole=0.5, color_discrete_sequence=px.colors.qualitative.Plotly)
        fig_st.update_layout(paper_bgcolor="rgba(30, 41, 59, 0.4)", plot_bgcolor="rgba(15, 23, 42, 0.6)", font=dict(color="#CBD5E1"))
        st.plotly_chart(fig_st, use_container_width=True)

# =============================================================================
# 7. BUSINESS INSIGHTS & AI REPORTS
# =============================================================================
elif page == "💡 Business Insights & AI Reports":
    st.title("Business Insights & AI Report Generator")
    filters = render_global_filter_bar(db, store)
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(
        filters["preset"], filters["custom_start"], filters["custom_end"]
    )

    tab_ins, tab_ai = st.tabs(["💡 Automated Plain-English Insights", "🤖 AI Executive Business Report"])

    with tab_ins:
        st.subheader("Verified Data-Backed Insights")
        insights = insights_engine.generate_insights(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=filters["currency"])

        for ins in insights:
            st.markdown(f"""
            <div class="insight-card insight-{ins['severity'].lower()}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="insight-title">{ins['title']}</span>
                    <span class="class-tag class-{ins['severity'].lower()}">{ins['severity']}</span>
                </div>
                <div class="insight-explanation">{ins['explanation']}</div>
                <div class="insight-action-box">
                    💡 <b>Prescribed Action:</b> {ins['suggested_action']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    with tab_ai:
        st.subheader("AI-Powered Executive Analytics Briefing")
        st.markdown("Generates a comprehensive executive report strictly grounded on verified aggregated metrics.")

        if st.button("🚀 Generate AI Business Report", type="primary"):
            with st.spinner("Compiling validated metrics and generating executive report..."):
                report_result = ai_service.generate_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=filters["currency"])
                st.markdown(report_result["report_markdown"])

                # Provide export buttons
                st.download_button(
                    "📄 Download Executive PDF",
                    data=exporter.generate_pdf_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=filters["currency"]),
                    file_name="Executive_AI_Briefing.pdf",
                    mime="application/pdf"
                )

# =============================================================================
# 8. WOOCOMMERCE SYNC
# =============================================================================
elif page == "🔌 WooCommerce Sync":
    st.title("WooCommerce Integration & Synchronization")
    st.markdown("Connect your live WooCommerce REST API credentials and manage background synchronization.")

    with st.form("wc_connect_form"):
        st.subheader("WooCommerce Store Credentials")
        store_url = st.text_input("Store URL", value=store.store_url)
        ck = st.text_input("Consumer Key", value=store.consumer_key, type="password")
        cs = st.text_input("Consumer Secret", value=store.consumer_secret, type="password")
        verify_ssl = st.checkbox("Verify SSL Certificates", value=True)

        c1, c2 = st.columns(2)
        with c1:
            test_submitted = st.form_submit_button("🔌 Test API Connection")
        with c2:
            save_submitted = st.form_submit_button("💾 Save Credentials")

        if test_submitted:
            client = WooCommerceClient(store_url=store_url, consumer_key=ck, consumer_secret=cs, verify_ssl=verify_ssl)
            res = client.test_connection()
            if res["success"]:
                st.success(f"Connection Successful! Store: {res.get('store_name')} ({res.get('currency')})")
            else:
                st.error(f"Connection Failed: {res.get('message')}")

        if save_submitted:
            store.store_url = store_url
            store.consumer_key = ck
            store.consumer_secret = cs
            db.commit()
            st.success("Credentials saved successfully.")

    st.markdown("---")
    st.subheader("Data Synchronization")
    sc1, sc2 = st.columns(2)
    with sc1:
        if st.button("⚡ Run Incremental Sync", use_container_width=True):
            with st.spinner("Synchronizing updated records..."):
                sync_service = SyncService(db, store)
                log = sync_service.run_sync(sync_type="incremental")
                if log.status == "success":
                    st.success(f"Sync complete: {log.records_fetched} fetched, {log.records_inserted} inserted, {log.records_updated} updated.")
                else:
                    st.error(f"Sync failed: {log.error_message}")

    with sc2:
        if st.button("🔄 Run Full Re-Sync", use_container_width=True):
            with st.spinner("Synchronizing full historical store catalog..."):
                sync_service = SyncService(db, store)
                log = sync_service.run_sync(sync_type="full")
                if log.status == "success":
                    st.success(f"Full sync completed successfully!")
                else:
                    st.error(f"Full sync error: {log.error_message}")

# =============================================================================
# 9. DATA IMPORTS & PRODUCT COSTS
# =============================================================================
elif page == "📥 Data Imports & Product Costs":
    st.title("Data Imports & Multi-Format Ingestion")
    st.markdown("Import data from **CSV** or **Excel (.xlsx)** spreadsheets for **Product Costs (COGS)**, **Inventory Stock Levels**, or **Historical Offline Orders**. Every uploaded row is strictly pre-validated before committing to the database.")

    import_service = DataImportService(db, store_id=store.id)

    # 1. Import Category Selector
    import_type_label = st.radio(
        "Select Import Type:",
        [
            "💰 Product Costs (COGS & Margins)",
            "📦 Inventory Stock Levels",
            "🧾 Historical Orders & Sales"
        ],
        horizontal=True
    )

    if "Product Costs" in import_type_label:
        type_key = "costs"
        type_desc = "Update unit production/acquisition costs to calculate exact gross profit and profit margins."
    elif "Inventory" in import_type_label:
        type_key = "inventory"
        type_desc = "Update live stock quantities and track inventory snapshots across your product catalog."
    else:
        type_key = "orders"
        type_desc = "Upload historical POS, phone, or legacy e-commerce orders to incorporate into customer analytics."

    st.info(f"ℹ️ **{type_desc}**")

    # 2. Download Sample Templates
    with st.expander("📥 Need a sample template? Download pre-filled CSV or Excel formats", expanded=False):
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            csv_data = import_service.generate_template(type_key, format_type="csv")
            st.download_button(
                label=f"📄 Download {type_key.title()} Template (.CSV)",
                data=csv_data,
                file_name=f"sample_{type_key}_template.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c_t2:
            xlsx_data = import_service.generate_template(type_key, format_type="xlsx")
            st.download_button(
                label=f"📊 Download {type_key.title()} Template (.XLSX)",
                data=xlsx_data,
                file_name=f"sample_{type_key}_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # 3. File Uploader
    uploaded_file = st.file_uploader(
        f"Upload {type_key.title()} Spreadsheet (.CSV or .XLSX)",
        type=["csv", "xlsx", "xls"],
        key=f"uploader_{type_key}"
    )

    if uploaded_file is not None:
        contents = uploaded_file.read()
        try:
            df = import_service.parse_file(contents, uploaded_file.name)
            st.write(f"**Loaded {len(df)} rows from `{uploaded_file.name}`**")

            # Validate based on selected type
            if type_key == "costs":
                val_res = import_service.validate_product_costs(df)
            elif type_key == "inventory":
                val_res = import_service.validate_inventory_levels(df)
            else:
                val_res = import_service.validate_historical_orders(df)

            v1, v2, v3 = st.columns(3)
            v1.metric("Total Rows", val_res.total_rows)
            v2.metric("Valid Rows", val_res.valid_rows)
            v3.metric("Error Rows", val_res.error_rows)

            st.subheader("Data Preview & Validation Status")
            st.dataframe(pd.DataFrame(val_res.preview_data), use_container_width=True)

            if val_res.errors:
                st.warning(f"Found {len(val_res.errors)} validation errors. Rows with errors will be skipped.")
                with st.expander("Inspect Validation Error Log"):
                    st.dataframe(pd.DataFrame(val_res.errors), use_container_width=True)

            if val_res.ready_to_import:
                commit_btn_label = f"✅ Commit {val_res.valid_rows} Valid Rows to Database"
                if st.button(commit_btn_label, type="primary"):
                    if type_key == "costs":
                        commit_res = import_service.commit_product_costs(df, source_name=uploaded_file.name)
                        st.success(f"Successfully imported costs for {commit_res['imported_count']} products! Gross margins are now updated.")
                    elif type_key == "inventory":
                        commit_res = import_service.commit_inventory_levels(df, source_name=uploaded_file.name)
                        st.success(f"Successfully updated inventory for {commit_res['imported_count']} products!")
                    else:
                        commit_res = import_service.commit_historical_orders(df, source_name=uploaded_file.name)
                        st.success(f"Successfully imported {commit_res['imported_count']} historical orders!")
                    st.rerun()

        except Exception as e:
            st.error(f"Error parsing file: {str(e)}")

# =============================================================================
# 10. SETTINGS & SYSTEM
# =============================================================================
elif page == "⚙️ Settings & System":
    st.title("Settings & System Diagnostics")
    st.markdown("System architecture diagnostics and demo data reset utilities.")

    s1, s2 = st.columns(2)
    with s1:
        st.subheader("Database & Environment")
        st.write(f"**Active Store URL:** `{store.store_url}`")
        st.write(f"**Currency:** `{store.currency}`")
        st.write(f"**Timezone:** `{store.timezone}`")
        st.write(f"**Products in Database:** `{db.query(Product).filter(Product.store_id == store.id).count()}`")
        st.write(f"**Orders in Database:** `{db.query(Order).filter(Order.store_id == store.id).count()}`")

    with s2:
        st.subheader("Synthetic Dataset Reset")
        st.markdown("Re-generate the 180-day realistic sample dataset with 800+ orders, refunds, and costs:")
        if st.button("⚡ Reset / Seed Sample Store Data"):
            with st.spinner("Generating sample dataset..."):
                generate_sample_dataset(db, seed=random.randint(1, 9999))
                st.success("Sample store data regenerated successfully!")
                st.rerun()
