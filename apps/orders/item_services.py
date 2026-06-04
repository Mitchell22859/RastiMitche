"""
Orders - Dynamic Item Services.

Reusable helpers for parsing, saving, loading, and cleaning
OrderItemDefinition/OrderItemValue data in admin order forms.

Used by both admin_order_create and admin_order_edit views.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db import transaction

from .models import Order, OrderItemDefinition, OrderItemValue


class OrderItemService:
    """
    Service for managing dynamic order item values.

    Form field naming convention:
        item_<definition_id> = value

    Example POST data:
        item_5 = "3"       (NUMBER kind, definition id=5)
        item_6 = "150000"  (MONEY kind, definition id=6)
        item_7 = "Some text" (TEXT kind, definition id=7)
        item_8 = "on"      (BOOL kind, definition id=8, checkbox)
    """

    @staticmethod
    def get_definitions_for_category(*, company, category_id: Optional[int]):
        """
        Get active OrderItemDefinitions for a category (ordered by sort_order, id).

        Returns empty queryset if category_id is None.
        """
        if not category_id:
            return OrderItemDefinition.objects.none()
        return OrderItemDefinition.objects.filter(
            company=company,
            category_id=category_id,
            is_active=True,
        ).order_by("sort_order", "id")

    @staticmethod
    def get_existing_values(*, order: Order) -> dict:
        """
        Load existing OrderItemValues for an order.

        Returns:
            Dict mapping item_definition_id → OrderItemValue instance.
        """
        values = OrderItemValue.objects.filter(order=order).select_related("item")
        return {v.item_id: v for v in values}

    @staticmethod
    def get_values_display(*, order: Order) -> list:
        """
        Get item values as a display-friendly list of dicts.

        Returns:
            List of {definition, value} dicts for template rendering.
        """
        values = OrderItemValue.objects.filter(order=order).select_related("item")
        result = []
        for v in values:
            if v.item.kind == OrderItemDefinition.Kind.NUMBER:
                display_val = v.value_number
            elif v.item.kind == OrderItemDefinition.Kind.MONEY:
                display_val = v.value_number
            elif v.item.kind == OrderItemDefinition.Kind.TEXT:
                display_val = v.value_text
            elif v.item.kind == OrderItemDefinition.Kind.BOOL:
                display_val = v.value_bool
            else:
                display_val = None
            result.append({"definition": v.item, "value": display_val})
        return result

    @staticmethod
    def parse_value_from_post(*, definition: OrderItemDefinition, raw_value: str):
        """
        Parse a raw POST value into typed (field_name, value) tuple.

        Returns:
            Tuple of (field_name, parsed_value) or None if empty/invalid.
        """
        if definition.kind in (
            OrderItemDefinition.Kind.NUMBER,
            OrderItemDefinition.Kind.MONEY,
        ):
            if not raw_value or raw_value.strip() == "":
                return None
            try:
                return ("value_number", Decimal(raw_value.strip()))
            except (InvalidOperation, ValueError):
                return None

        elif definition.kind == OrderItemDefinition.Kind.TEXT:
            text = raw_value.strip() if raw_value else ""
            if not text:
                return None
            return ("value_text", text)

        elif definition.kind == OrderItemDefinition.Kind.BOOL:
            # Checkbox: "on" or "1" or "true" = True; absent = False
            if raw_value and raw_value.lower() in ("on", "1", "true", "yes"):
                return ("value_bool", True)
            # Explicitly False is still a value worth saving
            return ("value_bool", False)

        return None

    @staticmethod
    @transaction.atomic
    def save_items_from_post(*, order: Order, post_data: dict, company):
        """
        Parse and save dynamic item values from POST data for an order.

        Handles:
        - Creating new OrderItemValue rows
        - Updating existing values
        - Deleting values that are now empty
        - Only processes items belonging to the order's current service_category

        Args:
            order: The order to save items for.
            post_data: The request.POST dict.
            company: The tenant company (for security).
        """
        if not order.service_category_id:
            # No category → delete any orphaned values and return
            OrderItemValue.objects.filter(order=order).delete()
            return

        # Get valid definitions for current category
        definitions = OrderItemDefinition.objects.filter(
            company=company,
            category_id=order.service_category_id,
            is_active=True,
        )
        valid_def_ids = set(definitions.values_list("id", flat=True))

        # Delete values for definitions not in current category (category change cleanup)
        OrderItemValue.objects.filter(order=order).exclude(
            item_id__in=valid_def_ids
        ).delete()

        # Process each definition
        for definition in definitions:
            field_name = f"item_{definition.id}"
            raw_value = post_data.get(field_name, "")

            # For BOOL: checkbox absent means False
            if definition.kind == OrderItemDefinition.Kind.BOOL:
                if field_name not in post_data:
                    raw_value = ""  # Will parse as False

            parsed = OrderItemService.parse_value_from_post(
                definition=definition, raw_value=raw_value,
            )

            existing = OrderItemValue.objects.filter(
                order=order, item=definition,
            ).first()

            if parsed is None:
                # Empty value → delete existing if any (except BOOL which defaults False)
                if definition.kind != OrderItemDefinition.Kind.BOOL and existing:
                    existing.delete()
                continue

            field_key, value = parsed

            if existing:
                # Update existing
                # Clear other value fields
                existing.value_number = None
                existing.value_text = None
                existing.value_bool = None
                setattr(existing, field_key, value)
                existing.save()
            else:
                # Create new
                kwargs = {
                    "order": order,
                    "item": definition,
                    field_key: value,
                }
                OrderItemValue.objects.create(**kwargs)

    @staticmethod
    @transaction.atomic
    def cleanup_incompatible_values(*, order: Order):
        """
        Remove OrderItemValues that don't belong to the order's current category.

        Called when category changes during edit to prevent orphaned data.
        """
        if not order.service_category_id:
            OrderItemValue.objects.filter(order=order).delete()
            return

        valid_def_ids = OrderItemDefinition.objects.filter(
            category_id=order.service_category_id,
        ).values_list("id", flat=True)

        OrderItemValue.objects.filter(order=order).exclude(
            item_id__in=valid_def_ids
        ).delete()

    @staticmethod
    def get_definitions_json(*, company) -> list:
        """
        Get all active definitions grouped by category for client-side JS rendering.

        Returns list of {id, title, kind, category_id, sort_order} dicts.
        """
        defs = OrderItemDefinition.objects.filter(
            company=company, is_active=True,
        ).order_by("sort_order", "id").values(
            "id", "title", "kind", "category_id", "sort_order",
        )
        return list(defs)
