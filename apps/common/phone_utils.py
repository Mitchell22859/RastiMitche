"""
Common - Phone Number Utilities.

Central phone normalization for Iranian mobile numbers.
All phone storage in the database uses the format: 09xxxxxxxxx (11 digits).

Usage:
    from apps.common.phone_utils import normalize_iran_mobile, is_valid_iran_mobile

    phone = normalize_iran_mobile("+98 912 123 4567")  # "09121234567"
    valid = is_valid_iran_mobile("09121234567")         # True
"""
import re


# Persian/Arabic digit mapping to ASCII
_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# Valid Iranian mobile: exactly 11 digits starting with 09
_IRAN_MOBILE_RE = re.compile(r"^09\d{9}$")


def normalize_iran_mobile(value: str) -> str:
    """
    Normalize an Iranian mobile phone number to 09xxxxxxxxx format.

    Handles:
    - Persian/Arabic digits (۰۹۱۲... → 0912...)
    - International formats (+989121234567, 989121234567, 00989121234567)
    - Short format without leading zero (9121234567 → 09121234567)
    - Spaces, dashes, parentheses removed

    Returns:
        Normalized 11-digit string starting with "09", or "" if invalid.

    Examples:
        >>> normalize_iran_mobile("09121234567")
        '09121234567'
        >>> normalize_iran_mobile("+989121234567")
        '09121234567'
        >>> normalize_iran_mobile("۰۹۱۲۱۲۳۴۵۶۷")
        '09121234567'
        >>> normalize_iran_mobile("00989121234567")
        '09121234567'
        >>> normalize_iran_mobile("9121234567")
        '09121234567'
        >>> normalize_iran_mobile("invalid")
        ''
    """
    if not value:
        return ""

    # Convert Persian/Arabic digits to ASCII
    phone = str(value).translate(_DIGIT_MAP)

    # Remove whitespace, dashes, parentheses, dots
    phone = re.sub(r"[\s\-\(\)\.\u200c]+", "", phone)

    # Remove leading +
    if phone.startswith("+"):
        phone = phone[1:]

    # Handle various prefixes
    if phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone

    # Validate final format
    if _IRAN_MOBILE_RE.match(phone):
        return phone

    return ""


def is_valid_iran_mobile(value: str) -> bool:
    """
    Check if a value is a valid Iranian mobile number (after normalization).

    Returns True if normalize_iran_mobile(value) produces a valid result.
    """
    return bool(normalize_iran_mobile(value))
