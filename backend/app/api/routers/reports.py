from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.store import Store
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.ai_report_service import AIReportService
from backend.app.services.export_service import ExportService
from backend.app.utils.timezone import get_period_dates

router = APIRouter(prefix="/api/reports", tags=["Reports & Exports"])


def get_active_store(db: Session = Depends(get_db)) -> Store:
    store = db.query(Store).filter(Store.is_active == True).first()
    if not store:
        store = db.query(Store).first()
    if not store:
        raise HTTPException(status_code=404, detail="No store configured.")
    return store


@router.get("/ai-summary")
def get_ai_summary(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    analytics = AnalyticsEngine(db, store_id=store.id)
    ai_service = AIReportService(analytics)
    return ai_service.generate_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=store.currency or "USD")


@router.get("/export/excel")
def export_excel(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    analytics = AnalyticsEngine(db, store_id=store.id)
    exporter = ExportService(analytics)
    excel_bytes = exporter.generate_excel_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=store.currency or "USD")

    filename = f"WooCommerce_Analytics_{start_utc.strftime('%Y%m%d')}_{end_utc.strftime('%Y%m%d')}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/pdf")
def export_pdf(
    preset: str = Query("last_30_days"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    store: Store = Depends(get_active_store)
):
    start_utc, end_utc, prev_start_utc, prev_end_utc = get_period_dates(preset, start_date, end_date)
    analytics = AnalyticsEngine(db, store_id=store.id)
    exporter = ExportService(analytics)
    pdf_bytes = exporter.generate_pdf_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency=store.currency or "USD")

    filename = f"Executive_BI_Report_{start_utc.strftime('%Y%m%d')}_{end_utc.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
