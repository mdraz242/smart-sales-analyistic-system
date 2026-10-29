from typing import Dict, Any
import streamlit as st


def render_kpi_card(
    title: str,
    metric_data: Dict[str, Any],
    currency: str = "USD",
    help_text: str = None
):
    """Renders a single high-impact KPI card with trend pill and baseline."""
    current_val = metric_data.get("formatted_current", "0")
    prev_val = metric_data.get("formatted_previous", "0")
    delta_pct = metric_data.get("delta_pct", 0.0)
    trend = metric_data.get("trend", "neutral")
    definition = help_text or metric_data.get("definition", "")

    if trend == "positive":
        pill_class = "delta-positive"
        icon = "▲"
    elif trend == "negative":
        pill_class = "delta-negative"
        icon = "▼"
    else:
        pill_class = "delta-neutral"
        icon = "●"

    delta_str = f"{icon} {abs(delta_pct):.1f}%"

    card_html = f"""
    <div class="kpi-card" title="{definition}">
        <div class="kpi-header">
            <span class="kpi-title">{title}</span>
        </div>
        <div class="kpi-value">{current_val}</div>
        <div class="kpi-footer">
            <span class="kpi-delta-pill {pill_class}">{delta_str}</span>
            <span class="kpi-baseline">vs prev ({prev_val})</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_kpi_grid(kpis: Dict[str, Any]):
    """Renders the executive overview KPI card grid."""
    curr = kpis.get("currency", "USD")

    # Row 1: Core Top-Line Revenue & Volume
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Net Sales", kpis["net_sales"], curr)
    with c2:
        render_kpi_card("Total Revenue", kpis["revenue_collected"], curr)
    with c3:
        render_kpi_card("Total Orders", kpis["total_orders"], curr)
    with c4:
        render_kpi_card("Average Order Value", kpis["average_order_value"], curr)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Row 2: Merchandise Volume, Growth & Deductions
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        render_kpi_card("Units Sold", kpis["units_sold"], curr)
    with c6:
        render_kpi_card("Sales Growth", kpis["sales_growth_pct"], curr)
    with c7:
        render_kpi_card("Discounts Granted", kpis["total_discounts"], curr)
    with c8:
        render_kpi_card("Customer Refunds", kpis["total_refunds"], curr)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Row 3: Customer Base, Tax, Shipping & Quality
    c9, c10, c11, c12 = st.columns(4)
    with c9:
        render_kpi_card("Unique Customers", kpis["unique_customers"], curr)
    with c10:
        render_kpi_card("New vs Returning", {
            "formatted_current": f"{kpis['new_customers']['current']} / {kpis['returning_customers']['current']}",
            "formatted_previous": f"{kpis['new_customers']['previous']} / {kpis['returning_customers']['previous']}",
            "delta_pct": kpis["new_customers"]["delta_pct"],
            "trend": kpis["new_customers"]["trend"],
            "definition": "Ratio of first-time buyers versus returning customers in the period."
        }, curr)
    with c11:
        render_kpi_card("Refund Rate", kpis["refund_rate"], curr)
    with c12:
        render_kpi_card("Order Cancellation Rate", kpis["cancellation_rate"], curr)
