"""
Tenants - File Validators.

Validators for uploaded media files (images).
"""
from django.core.exceptions import ValidationError


MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]


def validate_image_file(file) -> None:
    """
    Validate an uploaded image file.

    Rules:
    - Must be an image type (jpeg, png, webp, gif)
    - Must be under 2MB

    Raises:
        ValidationError if file is invalid.
    """
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f"حجم فایل بیش از حد مجاز است. حداکثر: {MAX_IMAGE_SIZE // (1024*1024)} مگابایت"
        )

    content_type = getattr(file, "content_type", "")
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            "فقط فایل‌های تصویری (JPEG, PNG, WebP, GIF) مجاز هستند."
        )
