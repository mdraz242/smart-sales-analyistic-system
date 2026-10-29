from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DateRangeFilter(BaseModel):
    preset: Optional[str] = "last_30_days"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    compare_previous: bool = True
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    order_status: Optional[str] = None
    coupon_code: Optional[str] = None
    customer_type: Optional[str] = None  # all, new, returning


class MetricSummary(BaseModel):
    current: float
    previous: float
    delta_abs: float
    delta_pct: float
    formatted_current: str
    formatted_previous: str
    trend: str  # positive, negative, neutral
    definition: str


class ExecutiveKPIDashboard(BaseModel):
    gross_sales: MetricSummary
    net_sales: MetricSummary
    revenue_collected: MetricSummary
    total_orders: MetricSummary
    units_sold: MetricSummary
    average_order_value: MetricSummary
    total_discounts: MetricSummary
    total_refunds: MetricSummary
    tax_collected: MetricSummary
    shipping_revenue: MetricSummary
    unique_customers: MetricSummary
    new_customers: MetricSummary
    returning_customers: MetricSummary
    cancellation_rate: MetricSummary
    refund_rate: MetricSummary
    sales_growth_pct: MetricSummary
    currency: str = "USD"
    period_start: datetime
    period_end: datetime
    previous_period_start: datetime
    previous_period_end: datetime


class ProductRankItem(BaseModel):
    product_id: int
    name: str
    sku: Optional[str] = "N/A"
    category: str = "Uncategorized"
    units_sold: int
    orders_count: int
    gross_sales: float
    discounts: float
    refunds: float
    net_sales: float
    net_sales_percentage: float
    average_selling_price: float
    cogs: Optional[float] = None
    gross_profit: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    previous_units_sold: int = 0
    previous_net_sales: float = 0.0
    growth_pct: float = 0.0
    classification: str = "Regular"
