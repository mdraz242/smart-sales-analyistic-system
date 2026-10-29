from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np

from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.utils.currency import format_currency


class InsightsEngine:
    """
    Automated plain-English business intelligence insight generator
    powered by statistical rules and metric verification.
    """

    def __init__(self, analytics_engine: AnalyticsEngine):
        self.analytics = analytics_engine

    def generate_insights(
        self,
        start_utc: datetime,
        end_utc: datetime,
        prev_start_utc: datetime,
        prev_end_utc: datetime,
        currency: str = "USD"
    ) -> List[Dict[str, Any]]:
        insights = []

        # 1. Fetch verified metrics
        kpis = self.analytics.get_executive_kpis(
            start_utc, end_utc, prev_start_utc, prev_end_utc, currency=currency
        )
        products = self.analytics.get_product_performance(
            start_utc, end_utc, prev_start_utc, prev_end_utc, rank_by="units_sold", limit=50
        )
        categories = self.analytics.get_category_analytics(
            start_utc, end_utc, prev_start_utc, prev_end_utc
        )
        cust_summary = self.analytics.get_customer_segments()

        # Rule 1: Period Revenue Growth / Contraction
        net_sales_cur = kpis["net_sales"]["current"]
        net_sales_prev = kpis["net_sales"]["previous"]
        sales_growth = kpis["sales_growth_pct"]["current"]

        if net_sales_prev > 100.0:  # Minimum threshold
            if sales_growth >= 10.0:
                insights.append({
                    "id": "rev_growth_strong",
                    "title": f"Revenue surged by {sales_growth:+.1f}% vs Previous Period",
                    "category": "Revenue & Growth",
                    "severity": "OPPORTUNITY",
                    "explanation": (
                        f"Net sales reached {format_currency(net_sales_cur, currency)}, growing from "
                        f"{format_currency(net_sales_prev, currency)} in the preceding equivalent period."
                    ),
                    "supporting_metrics": {
                        "current_net_sales": net_sales_cur,
                        "previous_net_sales": net_sales_prev,
                        "growth_percentage": sales_growth
                    },
                    "comparison_period": f"{prev_start_utc.strftime('%b %d')} - {prev_end_utc.strftime('%b %d, %Y')}",
                    "suggested_action": "Evaluate top contributing acquisition channels and scale ad spend on best-performing campaigns.",
                    "drilldown": "Executive Overview"
                })
            elif sales_growth <= -10.0:
                insights.append({
                    "id": "rev_decline_alert",
                    "title": f"Revenue declined by {abs(sales_growth):.1f}% vs Previous Period",
                    "category": "Revenue & Growth",
                    "severity": "WARNING",
                    "explanation": (
                        f"Net sales dropped to {format_currency(net_sales_cur, currency)} compared to "
                        f"{format_currency(net_sales_prev, currency)} previously."
                    ),
                    "supporting_metrics": {
                        "current_net_sales": net_sales_cur,
                        "previous_net_sales": net_sales_prev,
                        "decline_percentage": sales_growth
                    },
                    "comparison_period": f"{prev_start_utc.strftime('%b %d')} - {prev_end_utc.strftime('%b %d, %Y')}",
                    "suggested_action": "Audit top declining product categories and check for traffic drop-offs or checkout funnel friction.",
                    "drilldown": "Revenue Analytics"
                })

        # Rule 2: Top Best-Selling Product Concentration (Pareto analysis)
        if products:
            top_prod = products[0]
            if top_prod["units_sold"] >= 10:
                insights.append({
                    "id": "top_product_leader",
                    "title": f"'{top_prod['name']}' is leading sales volume",
                    "category": "Product Performance",
                    "severity": "INFO",
                    "explanation": (
                        f"'{top_prod['name']}' sold {top_prod['units_sold']:,} units generating "
                        f"{format_currency(top_prod['net_sales'], currency)} ({top_prod['net_sales_percentage']:.1f}% of total net sales)."
                    ),
                    "supporting_metrics": {
                        "product_name": top_prod["name"],
                        "units_sold": top_prod["units_sold"],
                        "net_sales": top_prod["net_sales"],
                        "net_sales_pct": top_prod["net_sales_percentage"]
                    },
                    "comparison_period": "Current Period",
                    "suggested_action": "Feature this hero product in email marketing campaigns and maintain safe safety stock.",
                    "drilldown": "Product Intelligence"
                })

            # Check Pareto concentration (top 5 products share)
            if len(products) >= 5 and net_sales_cur > 0:
                top_5_sales = sum(p["net_sales"] for p in products[:5])
                top_5_share = (top_5_sales / net_sales_cur) * 100
                if top_5_share >= 50.0:
                    insights.append({
                        "id": "pareto_concentration",
                        "title": f"Top 5 products generate {top_5_share:.1f}% of store revenue",
                        "category": "Catalog Risk",
                        "severity": "WARNING",
                        "explanation": (
                            f"The top 5 merchandise lines account for {format_currency(top_5_sales, currency)} "
                            f"out of {format_currency(net_sales_cur, currency)} total store sales."
                        ),
                        "supporting_metrics": {
                            "top_5_sales": round(top_5_sales, 2),
                            "top_5_percentage": round(top_5_share, 1)
                        },
                        "comparison_period": "Current Period",
                        "suggested_action": "Diversify catalog revenue by bundling high-margin mid-tier products with top sellers.",
                        "drilldown": "Product Intelligence"
                    })

        # Rule 3: Rising Stars and Declining Products
        rising_stars = [p for p in products if p.get("classification") == "Rising Star"]
        if rising_stars:
            star = rising_stars[0]
            insights.append({
                "id": f"rising_star_{star['product_id']}",
                "title": f"Rising Star: '{star['name']}' grew {star['growth_pct']:+.1f}%",
                "category": "Growth Opportunities",
                "severity": "OPPORTUNITY",
                "explanation": (
                    f"'{star['name']}' surged to {star['units_sold']} units sold (up from {star['previous_units_sold']} units in the previous period)."
                ),
                "supporting_metrics": {
                    "product": star["name"],
                    "current_units": star["units_sold"],
                    "previous_units": star["previous_units_sold"],
                    "growth_pct": star["growth_pct"]
                },
                "comparison_period": f"{prev_start_utc.strftime('%b %d')} - {prev_end_utc.strftime('%b %d, %Y')}",
                "suggested_action": "Increase PPC ad budget and ensure warehouse stock replenishment immediately.",
                "drilldown": "Product Intelligence"
            })

        declining_prods = [p for p in products if p.get("classification") == "Declining"]
        if declining_prods:
            dec = declining_prods[0]
            insights.append({
                "id": f"declining_{dec['product_id']}",
                "title": f"Declining Demand: '{dec['name']}' dropped {dec['growth_pct']:.1f}%",
                "category": "Product Health",
                "severity": "WARNING",
                "explanation": (
                    f"'{dec['name']}' fell to {dec['units_sold']} units from {dec['previous_units_sold']} units previously."
                ),
                "supporting_metrics": {
                    "product": dec["name"],
                    "current_units": dec["units_sold"],
                    "previous_units": dec["previous_units_sold"],
                    "drop_pct": dec["growth_pct"]
                },
                "comparison_period": f"{prev_start_utc.strftime('%b %d')} - {prev_end_utc.strftime('%b %d, %Y')}",
                "suggested_action": "Review pricing competitiveness, inspect customer reviews for quality feedback, or run a promotional flash sale.",
                "drilldown": "Product Intelligence"
            })

        # Rule 4: High Refund Risk Products
        refund_prods = [p for p in products if p.get("classification") == "High Refund Risk"]
        if refund_prods:
            rf = refund_prods[0]
            insights.append({
                "id": f"refund_risk_{rf['product_id']}",
                "title": f"High Refund Risk: '{rf['name']}' at {rf['refund_rate']:.1f}% returns",
                "category": "Customer Satisfaction",
                "severity": "CRITICAL",
                "explanation": (
                    f"'{rf['name']}' accumulated {format_currency(rf['refunds'], currency)} in refunds, "
                    f"representing {rf['refund_rate']:.1f}% of its gross sales."
                ),
                "supporting_metrics": {
                    "product": rf["name"],
                    "refund_amount": rf["refunds"],
                    "refund_rate_pct": rf["refund_rate"]
                },
                "comparison_period": "Current Period",
                "suggested_action": "Inspect return reasons (sizing, packaging, defect) and clarify product description specifications.",
                "drilldown": "Order Analytics"
            })

        # Rule 5: Stockout Risks
        stockout_prods = [p for p in products if p.get("classification") == "Stockout Risk"]
        if stockout_prods:
            sk = stockout_prods[0]
            insights.append({
                "id": f"stockout_risk_{sk['product_id']}",
                "title": f"Imminent Stockout Risk: '{sk['name']}' has only {sk['stock_quantity']} units left",
                "category": "Inventory Management",
                "severity": "CRITICAL",
                "explanation": (
                    f"'{sk['name']}' sold {sk['units_sold']} units during this period and current inventory "
                    f"is down to {sk['stock_quantity']} units."
                ),
                "supporting_metrics": {
                    "product": sk["name"],
                    "units_sold": sk["units_sold"],
                    "remaining_stock": sk["stock_quantity"]
                },
                "comparison_period": "Current Period",
                "suggested_action": "Place an expedited supplier replenishment PO to prevent revenue loss from out-of-stock listings.",
                "drilldown": "Product Intelligence"
            })

        # Rule 6: Category Contribution Dominance
        if categories:
            top_cat = categories[0]
            if top_cat["sales_contribution_pct"] >= 30.0:
                insights.append({
                    "id": f"category_leader_{top_cat['category_id']}",
                    "title": f"Category '{top_cat['name']}' generated {top_cat['sales_contribution_pct']:.1f}% of net sales",
                    "category": "Category Intelligence",
                    "severity": "INFO",
                    "explanation": (
                        f"The '{top_cat['name']}' collection drove {format_currency(top_cat['net_sales'], currency)} "
                        f"across {top_cat['orders_count']:,} orders with an AOV of {format_currency(top_cat['aov'], currency)}."
                    ),
                    "supporting_metrics": {
                        "category_name": top_cat["name"],
                        "net_sales": top_cat["net_sales"],
                        "share_pct": top_cat["sales_contribution_pct"],
                        "aov": top_cat["aov"]
                    },
                    "comparison_period": "Current Period",
                    "suggested_action": "Expand product breadth in this winning collection with complementary accessories.",
                    "drilldown": "Category Intelligence"
                })

        # Rule 7: Customer Retention & Repeat Purchase
        summary = cust_summary.get("summary", {})
        repeat_rate = summary.get("repeat_rate_pct", 0.0)
        if repeat_rate > 0:
            if repeat_rate < 20.0:
                insights.append({
                    "id": "low_repeat_rate",
                    "title": f"Customer Repeat Purchase Rate is {repeat_rate:.1f}%",
                    "category": "Customer Retention",
                    "severity": "WARNING",
                    "explanation": (
                        f"Only {repeat_rate:.1f}% of customers have placed more than one order. "
                        f"Average customer lifetime revenue is {format_currency(summary.get('avg_customer_lifetime_rev', 0.0), currency)}."
                    ),
                    "supporting_metrics": {
                        "repeat_purchase_rate": repeat_rate,
                        "avg_orders_per_customer": summary.get("avg_orders_per_customer", 1.0)
                    },
                    "comparison_period": "All Time Available",
                    "suggested_action": "Implement a post-purchase automated email sequence with a time-limited 15% discount for 2nd orders.",
                    "drilldown": "Customer Intelligence"
                })
            elif repeat_rate >= 35.0:
                insights.append({
                    "id": "strong_retention",
                    "title": f"High Customer Loyalty: {repeat_rate:.1f}% Repeat Rate",
                    "category": "Customer Retention",
                    "severity": "OPPORTUNITY",
                    "explanation": (
                        f"Over one-third of customers ({repeat_rate:.1f}%) are repeat buyers, indicating exceptional product satisfaction."
                    ),
                    "supporting_metrics": {
                        "repeat_purchase_rate": repeat_rate,
                        "repeat_customer_count": summary.get("repeat_customers", 0)
                    },
                    "comparison_period": "All Time Available",
                    "suggested_action": "Launch a tiered VIP loyalty or referral rewards program to maximize customer lifetime value.",
                    "drilldown": "Customer Intelligence"
                })

        return insights
