from datetime import datetime, date, time, timedelta, timezone
from typing import Tuple


def get_period_dates(preset: str, custom_start: date = None, custom_end: date = None) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Returns (start_utc, end_utc, prev_start_utc, prev_end_utc)
    All timestamps are aware UTC datetimes.
    """
    now = datetime.now(timezone.utc)
    today = now.date()

    if preset == "today":
        start_date = today
        end_date = today
        duration = timedelta(days=1)
        prev_start_date = today - timedelta(days=1)
        prev_end_date = today - timedelta(days=1)
    elif preset == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
        prev_start_date = today - timedelta(days=2)
        prev_end_date = today - timedelta(days=2)
    elif preset == "last_7_days":
        start_date = today - timedelta(days=7)
        end_date = today
        prev_start_date = start_date - timedelta(days=7)
        prev_end_date = start_date
    elif preset == "last_30_days":
        start_date = today - timedelta(days=30)
        end_date = today
        prev_start_date = start_date - timedelta(days=30)
        prev_end_date = start_date
    elif preset == "last_90_days":
        start_date = today - timedelta(days=90)
        end_date = today
        prev_start_date = start_date - timedelta(days=90)
        prev_end_date = start_date
    elif preset == "this_month":
        start_date = today.replace(day=1)
        end_date = today
        # Previous month equivalent
        last_day_prev_month = start_date - timedelta(days=1)
        prev_start_date = last_day_prev_month.replace(day=1)
        # Match days elapsed in current month
        days_in = (end_date - start_date).days
        prev_end_date = min(prev_start_date + timedelta(days=days_in), last_day_prev_month)
    elif preset == "previous_month":
        first_of_this_month = today.replace(day=1)
        end_date = first_of_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
        # Month before previous
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date.replace(day=1)
    elif preset == "this_quarter":
        quarter = (today.month - 1) // 3 + 1
        start_month = 3 * (quarter - 1) + 1
        start_date = today.replace(month=start_month, day=1)
        end_date = today
        days_diff = (end_date - start_date).days + 1
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=days_diff - 1)
    elif preset == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        days_diff = (end_date - start_date).days + 1
        prev_start_date = (start_date - timedelta(days=365)).replace(month=1, day=1)
        prev_end_date = prev_start_date + timedelta(days=days_diff - 1)
    elif preset == "custom" and custom_start and custom_end:
        start_date = custom_start
        end_date = custom_end
        days_diff = (end_date - start_date).days + 1
        prev_end_date = start_date - timedelta(days=1)
        prev_start_date = prev_end_date - timedelta(days=days_diff - 1)
    else:
        # Default to last 30 days
        start_date = today - timedelta(days=30)
        end_date = today
        prev_start_date = start_date - timedelta(days=30)
        prev_end_date = start_date

    # Convert to full day boundaries in UTC
    start_utc = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
    end_utc = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
    prev_start_utc = datetime.combine(prev_start_date, time.min).replace(tzinfo=timezone.utc)
    prev_end_utc = datetime.combine(prev_end_date, time.max).replace(tzinfo=timezone.utc)

    return start_utc, end_utc, prev_start_utc, prev_end_utc
