from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _clean_number(value):
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    raw = str(value).strip()
    if raw == "":
        return None

    raw = (
        raw
        .replace(",", "")
        .replace("٬", "")
        .replace("،", "")
        .replace(" ", "")
        .replace("۰", "0").replace("۱", "1").replace("۲", "2").replace("۳", "3").replace("۴", "4")
        .replace("۵", "5").replace("۶", "6").replace("۷", "7").replace("۸", "8").replace("۹", "9")
        .replace("٠", "0").replace("١", "1").replace("٢", "2").replace("٣", "3").replace("٤", "4")
        .replace("٥", "5").replace("٦", "6").replace("٧", "7").replace("٨", "8").replace("٩", "9")
    )

    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value):
    d = _clean_number(value)
    if d is None:
        return value

    sign = "-" if d < 0 else ""
    d = abs(d)

    if d == d.to_integral_value():
        return sign + f"{int(d):,}"

    s = format(d.normalize(), "f")
    if "." in s:
        integer, fraction = s.split(".", 1)
        fraction = fraction.rstrip("0")
        if fraction:
            return sign + f"{int(integer):,}" + "." + fraction
        return sign + f"{int(integer):,}"

    return sign + f"{int(d):,}"


@register.filter(name="smart_number")
def smart_number(value):
    return _format_decimal(value)


@register.filter(name="smart_money")
def smart_money(value):
    return _format_decimal(value)
