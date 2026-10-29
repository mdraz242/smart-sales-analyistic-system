from datetime import date, datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.insights_engine import InsightsEngine
from backend.app.utils.timezone import get_period_dates
from backend.app.models.store import Store

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def get_active_store(db: Session = Depends(get_db)) -> Store:
    store = db.query(Store).filter(Store.is_active == True).first()
    if not store:
        # Fallback to any store
        store = db.query(Store).first()
    if not store:
        raise HTTPException(status_code=404, detail="No store configured. Please connect a WooCommerce store or initialize sample data.")
    return store


@router.get("/kpis")
def get_kpis(
    preset: str = Query("last_30_days", description="Preset range: today, yesterday, last_7_days, last_30_days, last_90_days, this_month, previous_month, this_quarter, this_year, custom"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    category_id: Optional[int] = None,
    order_status: Optional[str] = None,
    coupon_code: Optional[str] = None,
    customer_type: Optional[str] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_executive_kpis(
        start_utc=start_utc,
        end_utc=end_utc,
        prev_start_utc=prev_start_utc,
        prev_end_utc=prev_end_utc,
        category_id=category_id,
        product_id=product_id,
        order_status=order_status,
        coupon_code=coupon_code,
        customer_type=customer_type,
        currency=store.currency or "USD"
    )


@router.get("/products")
def get_products(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    rank_by: str = Query("units_sold", description="units_sold, net_sales, gross_sales, orders_count, growth_pct, gross_profit"),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_product_performance(
        start_utc=start_utc,
        end_utc=end_utc,
        prev_start_utc=prev_start_utc,
        prev_end_utc=prev_end_utc,
        rank_by=rank_by,
        limit=limit,
        category_id=category_id
    )


@router.get("/revenue-series")
def get_revenue_series(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    interval: str = Query("daily", description="daily, weekly, monthly"),
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, _, _ = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_revenue_time_series(start_utc, end_utc, interval=interval)


@router.get("/sales-heatmaps")
def get_heatmaps(
    preset: str = Query("last_90_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, _, _ = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_sales_heatmaps(start_utc, end_utc)


@router.get("/breakdowns")
def get_breakdowns(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, _, _ = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_breakdowns(start_utc, end_utc)


@router.get("/categories")
def get_categories(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_category_analytics(start_utc, end_utc, prev_start_utc, prev_end_utc)


@router.get("/customers")
def get_customers(
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_customer_segments()


@router.get("/orders")
def get_orders_analytics(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, _, _ = get_period_dates(preset, start_date, end_date)
    engine = AnalyticsEngine(db, store_id=store.id)
    return engine.get_order_analytics(start_utc, end_utc)


@router.get("/insights")
def get_insights(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    analytics = AnalyticsEngine(db, store_id=store.id)
    insights_engine = InsightsEngine(analytics)
    return insights_engine.generate_insights(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=store.currency or "USD")
