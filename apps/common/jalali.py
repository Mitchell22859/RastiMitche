from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional, Union

try:
    from django.utils import timezone
except Exception:
    timezone = None


PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_digits(value) -> str:
    return str(value or "").translate(PERSIAN_DIGITS).strip()


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + g_d_m[gm - 1]
    )

    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30

    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    if jy > 979:
        gy = 1600
        jy -= 979
    else:
        gy = 621

    days = (
        365 * jy
        + (jy // 33) * 8
        + ((jy % 33) + 3) // 4
        + 78
        + jd
    )

    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186

    gy += 400 * (days // 146097)
    days %= 146097

    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1

    gy += 4 * (days // 1461)
    days %= 1461

    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365

    gd = days + 1
    sal_a = [
        0,
        31,
        29 if (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]

    gm = 1
    while gm <= 12 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1

    return gy, gm, gd


def parse_jalali_date(value) -> Optional[date]:
    value = normalize_digits(value)
    if not value:
        return None

    value = value.replace("-", "/").replace(".", "/")
    parts = [p for p in value.split("/") if p]

    if len(parts) != 3:
        return None

    try:
        jy, jm, jd = [int(p) for p in parts]
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        return date(gy, gm, gd)
    except Exception:
        return None


def format_jalali(value, include_time: bool = False, empty: str = "-") -> str:
    if value in (None, ""):
        return empty

    try:
        if isinstance(value, datetime):
            dt = value
            if timezone is not None:
                try:
                    dt = timezone.localtime(dt)
                except Exception:
                    pass
            jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
            result = f"{jy:04d}/{jm:02d}/{jd:02d}"
            if include_time:
                result += f" {dt.hour:02d}:{dt.minute:02d}"
            return result

        if isinstance(value, date):
            jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
            return f"{jy:04d}/{jm:02d}/{jd:02d}"

        text = str(value)
        # Try ISO-ish values.
        try:
            if "T" in text or ":" in text:
                return format_jalali(datetime.fromisoformat(text.replace("Z", "+00:00")), include_time=include_time)
            return format_jalali(date.fromisoformat(text[:10]), include_time=False)
        except Exception:
            return text

    except Exception:
        return str(value)


def format_jalali_datetime(value, empty: str = "-") -> str:
    return format_jalali(value, include_time=True, empty=empty)


def jalali_range_to_gregorian(start_value, end_value):
    start = parse_jalali_date(start_value)
    end = parse_jalali_date(end_value)
    return start, end

# -----------------------------------------------------------------------------
# Rasti Phase 46B - Backward-compatible Jalali function aliases
# -----------------------------------------------------------------------------

def format_jalali_date(value, empty: str = "-") -> str:
    """
    Backward-compatible alias used by older views.
    Returns Jalali date without time.
    """
    return format_jalali(value, include_time=False, empty=empty)


def format_jalali_time(value, empty: str = "-") -> str:
    """
    Backward-compatible helper for time-only display when needed.
    """
    if value in (None, ""):
        return empty
    try:
        if isinstance(value, datetime):
            dt = value
            if timezone is not None:
                try:
                    dt = timezone.localtime(dt)
                except Exception:
                    pass
            return f"{dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        pass
    return str(value)


def today_jalali_date() -> str:
    """
    Backward-compatible helper used by older views/forms.
    Returns today's date in yyyy/mm/dd Jalali format.
    """
    if timezone is not None:
        try:
            today = timezone.localdate()
        except Exception:
            today = date.today()
    else:
        today = date.today()
    return format_jalali(today, include_time=False)


def today_jalali_datetime() -> str:
    """
    Backward-compatible helper for today's Jalali date and current time.
    """
    if timezone is not None:
        try:
            now = timezone.localtime(timezone.now())
        except Exception:
            now = datetime.now()
    else:
        now = datetime.now()
    return format_jalali(now, include_time=True)


def jalali_date_to_gregorian(value):
    """
    Backward-compatible alias.
    """
    return parse_jalali_date(value)


def gregorian_date_to_jalali(value):
    """
    Backward-compatible alias.
    """
    return format_jalali_date(value)
