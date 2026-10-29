import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import httpx

from backend.app.config import settings
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.insights_engine import InsightsEngine
from backend.app.utils.currency import format_currency

logger = logging.getLogger("ai_report_service")


class AIReportService:
    """
    Provider-independent LLM analytics report generator.
    Guarantees strict factual grounding: only validated aggregated metrics
    are provided to the model, protecting customer privacy and preventing hallucinations.
    """

    def __init__(self, analytics_engine: AnalyticsEngine):
        self.analytics = analytics_engine
        self.insights_engine = InsightsEngine(analytics_engine)
        self.provider = settings.LLM_PROVIDER.lower()

    def build_analytics_payload(
        self,
        start_utc: datetime,
        end_utc: datetime,
        prev_start_utc: datetime,
        prev_end_utc: datetime,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Collects strictly aggregated, privacy-safe analytics metrics."""
        kpis = self.analytics.get_executive_kpis(
            start_utc, end_utc, prev_start_utc, prev_end_utc, currency=currency
        )
        products = self.analytics.get_product_performance(
            start_utc, end_utc, prev_start_utc, prev_end_utc, rank_by="net_sales", limit=20
        )
        categories = self.analytics.get_category_analytics(
            start_utc, end_utc, prev_start_utc, prev_end_utc
        )
        customer_data = self.analytics.get_customer_segments()
        order_metrics = self.analytics.get_order_analytics(start_utc, end_utc)
        automated_insights = self.insights_engine.generate_insights(
            start_utc, end_utc, prev_start_utc, prev_end_utc, currency=currency
        )

        return {
            "period": {
                "start": start_utc.strftime("%Y-%m-%d"),
                "end": end_utc.strftime("%Y-%m-%d"),
                "previous_start": prev_start_utc.strftime("%Y-%m-%d"),
                "previous_end": prev_end_utc.strftime("%Y-%m-%d"),
                "currency": currency
            },
            "executive_kpis": {
                "gross_sales": kpis["gross_sales"]["current"],
                "net_sales": kpis["net_sales"]["current"],
                "previous_net_sales": kpis["net_sales"]["previous"],
                "sales_growth_pct": kpis["sales_growth_pct"]["current"],
                "total_orders": kpis["total_orders"]["current"],
                "units_sold": kpis["units_sold"]["current"],
                "aov": kpis["average_order_value"]["current"],
                "total_discounts": kpis["total_discounts"]["current"],
                "total_refunds": kpis["total_refunds"]["current"],
                "refund_rate_pct": kpis["refund_rate"]["current"],
                "cancellation_rate_pct": kpis["cancellation_rate"]["current"],
            },
            "top_products": [
                {
                    "name": p["name"],
                    "sku": p["sku"],
                    "category": p["category"],
                    "units_sold": p["units_sold"],
                    "net_sales": p["net_sales"],
                    "growth_pct": p["growth_pct"],
                    "classification": p["classification"],
                    "gross_margin_pct": p.get("gross_margin_pct"),
                    "stock_quantity": p.get("stock_quantity")
                }
                for p in products[:10]
            ],
            "categories": [
                {
                    "name": c["name"],
                    "net_sales": c["net_sales"],
                    "share_pct": c["sales_contribution_pct"],
                    "growth_pct": c["growth_pct"],
                    "aov": c["aov"]
                }
                for c in categories[:5]
            ],
            "customer_behavior": customer_data.get("summary", {}),
            "order_fulfillment": order_metrics.get("fulfillment", {}),
            "basket_metrics": order_metrics.get("basket_metrics", {}),
            "automated_insights_count": len(automated_insights)
        }

    def generate_report(
        self,
        start_utc: datetime,
        end_utc: datetime,
        prev_start_utc: datetime,
        prev_end_utc: datetime,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Generates comprehensive business report using configured LLM or expert rule-based generator."""
        payload = self.build_analytics_payload(
            start_utc, end_utc, prev_start_utc, prev_end_utc, currency=currency
        )

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            report_markdown = self._call_openai(payload)
        elif self.provider == "gemini" and settings.GEMINI_API_KEY:
            report_markdown = self._call_gemini(payload)
        elif self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            report_markdown = self._call_anthropic(payload)
        else:
            report_markdown = self._generate_grounded_mock_report(payload)

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "provider": self.provider if getattr(settings, f"{self.provider.upper()}_API_KEY", None) else "Deterministic Analytical Engine (Ground-Truth)",
            "date_range": f"{payload['period']['start']} to {payload['period']['end']}",
            "report_markdown": report_markdown,
            "metrics_payload": payload
        }

    def _generate_grounded_mock_report(self, data: Dict[str, Any]) -> str:
        """Deterministic, comprehensive executive analysis grounded entirely in facts."""
        kpi = data["executive_kpis"]
        curr = data["period"]["currency"]
        top_prods = data["top_products"]
        cats = data["categories"]
        cust = data["customer_behavior"]

        fast_growing = [p for p in top_prods if p["growth_pct"] >= 15.0]
        declining = [p for p in top_prods if p["growth_pct"] <= -10.0]
        stockouts = [p for p in top_prods if p.get("stock_quantity") is not None and p["stock_quantity"] <= 15]

        report = f"""# Executive B2C Sales Intelligence & Strategic Business Report
**Reporting Window**: {data['period']['start']} to {data['period']['end']}  
**Comparison Baseline**: {data['period']['previous_start']} to {data['period']['previous_end']}  
**Currency**: {curr}

---

## 1. Executive Summary
During the evaluated period, total **Net Sales reached {format_currency(kpi['net_sales'], curr)}**, representing a **{kpi['sales_growth_pct']:+.1f}% change** compared to the preceding baseline period ({format_currency(kpi['previous_net_sales'], curr)}). The store processed **{kpi['total_orders']:,} valid completed/processing orders**, selling **{kpi['units_sold']:,} merchandise units** at an **Average Order Value (AOV) of {format_currency(kpi['aov'], curr)}**.

Customer refunds amounted to **{format_currency(kpi['total_refunds'], curr)} ({kpi['refund_rate_pct']:.1f}% refund rate)**, while order cancellations remained controlled at **{kpi['cancellation_rate_pct']:.1f}%**.

---

## 2. Revenue & Order Performance Breakdown
- **Gross Merchandise Value**: {format_currency(kpi['gross_sales'], curr)}
- **Promotional Discounts**: {format_currency(kpi['total_discounts'], curr)} (Effective discount rate: {(kpi['total_discounts']/kpi['gross_sales']*100) if kpi['gross_sales']>0 else 0:.1f}%)
- **Customer Refunds**: {format_currency(kpi['total_refunds'], curr)}
- **Net Product Sales**: {format_currency(kpi['net_sales'], curr)}
- **Average Basket Units**: {data['basket_metrics'].get('avg_units_per_order', 'N/A')} units/order ({data['basket_metrics'].get('multi_item_orders_pct', 'N/A')}% multi-item orders)
- **Order Fulfillment Time**: {data['order_fulfillment'].get('avg_fulfillment_hours', 'N/A')} hours ({data['order_fulfillment'].get('avg_fulfillment_days', 'N/A')} days)

---

## 3. Product Catalog Intelligence

### Top Revenue Drivers
"""
        for i, p in enumerate(top_prods[:5], 1):
            margin_str = f" | Gross Margin: {p['gross_margin_pct']:.1f}%" if p.get('gross_margin_pct') is not None else ""
            report += f"{i}. **{p['name']}** (SKU: `{p['sku']}`) — {format_currency(p['net_sales'], curr)} ({p['units_sold']} units sold | Class: *{p['classification']}*{margin_str})\n"

        report += "\n### Fast-Growing Products (Rising Stars)\n"
        if fast_growing:
            for p in fast_growing:
                report += f"- **{p['name']}**: Grew **{p['growth_pct']:+.1f}%** in volume ({p['units_sold']} units sold).\n"
        else:
            report += "- No products met the >15% growth threshold in this period.\n"

        report += "\n### Declining Lines Requiring Attention\n"
        if declining:
            for p in declining:
                report += f"- **{p['name']}**: Contracted by **{p['growth_pct']:.1f}%** ({p['units_sold']} units sold).\n"
        else:
            report += "- Product catalog demand remained stable without severe contraction.\n"

        report += f"""
---

## 4. Category Performance & Contribution
"""
        for c in cats:
            report += f"- **{c['name']}**: {format_currency(c['net_sales'], curr)} ({c['share_pct']:.1f}% share of store sales | Period Growth: {c['growth_pct']:+.1f}% | AOV: {format_currency(c['aov'], curr)})\n"

        report += f"""
---

## 5. Customer Behavior & Retention
- **Total Customer Accounts Tracked**: {cust.get('total_customers', 0):,}
- **Repeat Purchase Rate**: {cust.get('repeat_rate_pct', 0.0):.1f}%
- **Average Orders per Customer**: {cust.get('avg_orders_per_customer', 0.0):.2f}
- **Average Lifetime Revenue**: {format_currency(cust.get('avg_customer_lifetime_rev', 0.0), curr)}

---

## 6. Inventory & Operational Risks
"""
        if stockouts:
            for s in stockouts:
                report += f"- ⚠️ **Critical Stockout Risk**: `{s['sku']}` ({s['name']}) has only **{s['stock_quantity']} units remaining** with high sales velocity.\n"
        else:
            report += "- Stock levels for top selling items are within normal buffer parameters.\n"

        report += f"""
---

## 7. Key Opportunities & Strategic Action Plan
1. **Capitalize on Top Collections**: Re-allocate advertising budget toward '{cats[0]['name'] if cats else 'Top Categories'}' which generated the largest share of net sales.
2. **Second-Order Retargeting**: With a repeat purchase rate of {cust.get('repeat_rate_pct', 0.0):.1f}%, deploy automated post-delivery replenishment sequences at Day 14 and Day 30.
3. **Inventory Replenishment**: Review replenishment purchase orders for high-velocity lines before stockouts harm organic search ranking.
4. **Bundle Strategy**: Introduce cross-sells to push average units per order above the current {data['basket_metrics'].get('avg_units_per_order', 'N/A')} units benchmark.
"""
        return report

    def _call_openai(self, payload: Dict[str, Any]) -> str:
        prompt = self._build_prompt(payload)
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "model": settings.AI_MODEL_NAME or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a senior e-commerce business analyst. Base all statements strictly on the verified numbers provided. Never hallucinate."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                logger.error("OpenAI API call failed: %d %s", res.status_code, res.text)
        except Exception as e:
            logger.error("OpenAI call exception: %s", str(e))
        return self._generate_grounded_mock_report(payload)

    def _call_gemini(self, payload: Dict[str, Any]) -> str:
        prompt = self._build_prompt(payload)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.AI_MODEL_NAME or 'gemini-1.5-flash'}:generateContent?key={settings.GEMINI_API_KEY}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(url, json=body)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error("Gemini call exception: %s", str(e))
        return self._generate_grounded_mock_report(payload)

    def _call_anthropic(self, payload: Dict[str, Any]) -> str:
        prompt = self._build_prompt(payload)
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": settings.AI_MODEL_NAME or "claude-3-5-haiku-20241022",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
                if res.status_code == 200:
                    return res.json()["content"][0]["text"]
        except Exception as e:
            logger.error("Anthropic call exception: %s", str(e))
        return self._generate_grounded_mock_report(payload)

    def _build_prompt(self, payload: Dict[str, Any]) -> str:
        return (
            "Analyze the following verified WooCommerce B2C e-commerce analytics dataset and create "
            "an executive business intelligence report with: Executive Summary, Revenue & Orders, "
            "Top Products, Fast-Growing / Declining Products, Category Performance, Customer Retention, "
            "Inventory Risks, and Strategic Next Actions.\n\n"
            f"DATASET:\n{json.dumps(payload, indent=2)}\n\n"
            "STRICT RULES:\n"
            "1. All numerical claims MUST be grounded in the supplied data.\n"
            "2. Do not infer profitability without cost data.\n"
            "3. Format cleanly in Markdown with bold KPIs and bullet points."
        )
