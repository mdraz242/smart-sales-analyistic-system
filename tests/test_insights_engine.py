import pytest
from datetime import datetime, timezone, timedelta
from backend.app.services.analytics_engine import AnalyticsEngine
from backend.app.services.insights_engine import InsightsEngine


def test_automated_insights_generation(populated_db):
    db, store = populated_db
    analytics = AnalyticsEngine(db, store_id=store.id)
    engine = InsightsEngine(analytics)

    now = datetime.now(timezone.utc)
    start_utc = now - timedelta(days=60)
    end_utc = now
    prev_start_utc = start_utc - timedelta(days=60)
    prev_end_utc = start_utc

    insights = engine.generate_insights(start_utc, end_utc, prev_start_utc, prev_end_utc, currency="USD")
    assert isinstance(insights, list)
    assert len(insights) > 0

    valid_severities = {"CRITICAL", "WARNING", "OPPORTUNITY", "INFO"}

    for ins in insights:
        assert "title" in ins
        assert "explanation" in ins
        assert "supporting_metrics" in ins
        assert "severity" in ins
        assert ins["severity"] in valid_severities
        assert "suggested_action" in ins
        assert len(ins["suggested_action"]) > 10
        assert "drilldown" in ins
