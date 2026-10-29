import pytest
from datetime import datetime, timezone, timedelta
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.export_service import ExportService


def test_excel_and_pdf_export_generation(populated_db):
    db, store = populated_db
    analytics = AnalyticsEngine(db, store_id=store.id)
    exporter = ExportService(analytics)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=30)
    end_utc = now
    prev_start_utc = start_utc - timedelta(days=30)
    prev_end_utc = start_utc

    # 1. Test Excel generation
    excel_bytes = exporter.generate_excel_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency="USD")
    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 2000  # Non-empty binary workbook

    # 2. Test PDF generation
    pdf_bytes = exporter.generate_pdf_report(start_utc, end_utc, prev_start_utc, prev_end_utc, currency="USD")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")
