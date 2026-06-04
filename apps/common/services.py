"""
Common - Base Service Pattern.

All services should follow this pattern:
- Services handle write operations and business logic
- Services receive validated data
- Services never handle HTTP request/response
- Services can call selectors for reads
- Services can call other services for cross-domain operations

Usage:
    class OrderService(BaseService):
        model = Order
"""
from typing import Any, Optional

from django.db import models


class BaseService:
    """
    Base service class providing common write operations.

    Subclass and set `model` attribute.
    Override methods to add custom business logic.
    """

    model: Optional[type[models.Model]] = None

    @classmethod
    def create(cls, *, data: dict[str, Any]) -> models.Model:
        """
        Create a new instance with validation.

        Args:
            data: Dictionary of field values.

        Returns:
            Created model instance.
        """
        assert cls.model is not None, "Service.model must be defined"
        instance = cls.model(**data)
        instance.full_clean()
        instance.save()
        return instance

    @classmethod
    def update(cls, *, instance: models.Model, data: dict[str, Any]) -> models.Model:
        """
        Update an existing instance with validation.

        Args:
            instance: The model instance to update.
            data: Dictionary of fields to update.

        Returns:
            Updated model instance.
        """
        for key, value in data.items():
            setattr(instance, key, value)
        instance.full_clean()
        instance.save()
        return instance
