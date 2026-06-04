from django import template

register = template.Library()


@register.filter
def jalali_date(value):
    if not value:
        return ""
    try:
        from apps.common.jalali import format_jalali
        return format_jalali(value)
    except Exception:
        try:
            return value.strftime("%Y/%m/%d")
        except Exception:
            return str(value)


@register.filter
def jalali_datetime(value):
    if not value:
        return ""
    try:
        from apps.common.jalali import format_jalali_datetime
        return format_jalali_datetime(value)
    except Exception:
        try:
            return value.strftime("%Y/%m/%d %H:%M")
        except Exception:
            return str(value)
