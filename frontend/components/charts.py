from typing import List, Dict, Any
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


GRID_COLOR = "#334155"

CHART_THEME = {
    "paper_bgcolor": "rgba(30, 41, 59, 0.4)",
    "plot_bgcolor": "rgba(15, 23, 42, 0.6)",
    "font": {"family": "Inter, sans-serif", "color": "#CBD5E1"},
    "margin": dict(l=40, r=30, t=40, b=40),
}


def render_revenue_trend_chart(series_data: List[Dict[str, Any]], currency: str = "USD") -> go.Figure:
    """Renders revenue area trend line with secondary order volume bars."""
    if not series_data:
        fig = go.Figure()
        fig.add_annotation(text="No sales data found for the selected filter period.", showarrow=False, font=dict(size=14, color="#94A3B8"))
        fig.update_layout(**CHART_THEME)
        return fig

    df = pd.DataFrame(series_data)

    fig = go.Figure()

    # Net Sales Gradient Area
    fig.add_trace(go.Scatter(
        x=df["date_str"],
        y=df["net_sales"],
        mode="lines+markers",
        name="Net Sales",
        line=dict(color="#3B82F6", width=3, shape="spline"),
        fill="tozeroy",
        fillcolor="rgba(59, 130, 246, 0.15)",
        marker=dict(size=6, color="#60A5FA"),
        hovertemplate="<b>Date</b>: %{x}<br><b>Net Sales</b>: " + currency + " %{y:,.2f}<extra></extra>"
    ))

    # Total Orders Line
    fig.add_trace(go.Scatter(
        x=df["date_str"],
        y=df["orders"],
        mode="lines+markers",
        name="Orders Count",
        yaxis="y2",
        line=dict(color="#10B981", width=2, dash="dot"),
        marker=dict(size=4, color="#34D399"),
        hovertemplate="<b>Orders</b>: %{y}<extra></extra>"
    ))

    fig.update_layout(
        title=dict(text="<b>Revenue & Order Velocity Over Time</b>", font=dict(size=15, color="#F8FAFC")),
        xaxis=dict(showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
        yaxis=dict(
            title=f"Net Sales ({currency})",
            showgrid=True,
            gridcolor=GRID_COLOR,
            zeroline=False
        ),
        yaxis2=dict(
            title="Orders",
            overlaying="y",
            side="right",
            showgrid=False
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **CHART_THEME
    )
    return fig


def render_product_ranking_chart(products: List[Dict[str, Any]], rank_col: str = "net_sales", currency: str = "USD") -> go.Figure:
    """Renders horizontal bar chart for top products."""
    if not products:
        fig = go.Figure()
        fig.add_annotation(text="No products recorded in period.", showarrow=False)
        fig.update_layout(**CHART_THEME)
        return fig

    top_10 = products[:10][::-1]  # reverse for top at top
    names = [p["name"][:28] + ("..." if len(p["name"]) > 28 else "") for p in top_10]
    values = [p.get(rank_col, 0) for p in top_10]

    color_map = {
        "Best Seller": "#3B82F6",
        "Rising Star": "#10B981",
        "Declining": "#F43F5E",
        "High Revenue": "#8B5CF6",
        "Stockout Risk": "#F59E0B"
    }
    bar_colors = [color_map.get(p.get("classification"), "#64748B") for p in top_10]

    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color="#1E293B", width=1)),
        text=[f"{v:,.0f}" if rank_col == "units_sold" else f"{currency} {v:,.0f}" for v in values],
        textposition="auto",
        hovertemplate="<b>%{y}</b><br>Value: %{x:,.2f}<extra></extra>"
    ))

    metric_label = "Net Sales (" + currency + ")" if rank_col == "net_sales" else rank_col.replace("_", " ").title()

    fig.update_layout(
        title=dict(text=f"<b>Top Products by {metric_label}</b>", font=dict(size=14, color="#F8FAFC")),
        xaxis=dict(showgrid=True, gridcolor=GRID_COLOR),
        yaxis=dict(showgrid=False),
        **CHART_THEME
    )
    return fig


def render_category_donut_chart(categories: List[Dict[str, Any]], currency: str = "USD") -> go.Figure:
    """Renders category revenue distribution donut chart."""
    if not categories:
        fig = go.Figure()
        fig.update_layout(**CHART_THEME)
        return fig

    labels = [c["name"] for c in categories]
    values = [c["net_sales"] for c in categories]

    colors_palette = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#06B6D4", "#EC4899", "#64748B"]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors_palette),
        textinfo="percent+label",
        hoverinfo="label+value+percent",
        hovertemplate="<b>%{label}</b><br>Net Sales: " + currency + " %{value:,.2f}<br>Share: %{percent}<extra></extra>"
    )])

    fig.update_layout(
        title=dict(text="<b>Category Share of Total Net Sales</b>", font=dict(size=14, color="#F8FAFC")),
        showlegend=False,
        **CHART_THEME
    )
    return fig


def render_heatmap_7x24(heatmap_data: Dict[str, Any]) -> go.Figure:
    """Renders peak sales hours and days matrix."""
    matrix = heatmap_data.get("heatmap_matrix", [])
    days = heatmap_data.get("heatmap_days", [])
    hours = heatmap_data.get("heatmap_hours", [])

    if not matrix:
        fig = go.Figure()
        fig.update_layout(**CHART_THEME)
        return fig

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=hours,
        y=days,
        colorscale="Blues",
        hoverongaps=False,
        hovertemplate="<b>Day</b>: %{y}<br><b>Hour</b>: %{x}<br><b>Net Sales</b>: $%{z:,.2f}<extra></extra>"
    ))

    fig.update_layout(
        title=dict(text="<b>Sales Intensity by Day of Week & Hour (Heatmap)</b>", font=dict(size=14, color="#F8FAFC")),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        **CHART_THEME
    )
    return fig


def render_cohort_retention_heatmap(cohort_records: List[Dict[str, Any]]) -> go.Figure:
    """Renders customer monthly cohort retention matrix."""
    if not cohort_records:
        fig = go.Figure()
        fig.update_layout(**CHART_THEME)
        return fig

    df = pd.DataFrame(cohort_records)
    cohorts = df["cohort"].tolist()
    month_cols = [c for c in df.columns if c.startswith("month_")]
    z_matrix = df[month_cols].values

    fig = go.Figure(data=go.Heatmap(
        z=z_matrix,
        x=[f"Month {c.replace('month_', '')}" for c in month_cols],
        y=cohorts,
        colorscale="Viridis",
        text=z_matrix,
        texttemplate="%{text:.0f}%",
        hovertemplate="<b>Cohort</b>: %{y}<br><b>Period</b>: %{x}<br><b>Retention</b>: %{z:.1f}%<extra></extra>"
    ))

    fig.update_layout(
        title=dict(text="<b>Monthly Customer Cohort Retention Rate (%)</b>", font=dict(size=14, color="#F8FAFC")),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False, autorange="reversed"),
        **CHART_THEME
    )
    return fig
