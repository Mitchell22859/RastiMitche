"""
Orders - Models.

The order engine is the HEART of Rasti Service.
All order models are tenant-scoped via CompanyOwnedModel.

IMPORTANT: Orders MUST always be filtered by company. No exceptions.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class Order(CompanyOwnedModel):
    """
    Service order placed by a customer.

    Workflow:
        NEW → WAITING → IN_PROGRESS → DONE
        NEW → CANCELLED (admin force cancel)
        IN_PROGRESS → CANCEL_REQUESTED → CANCELLED (cancel request flow)
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        WAITING = "waiting", "Waiting"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"
        CANCEL_REQUESTED = "cancel_requested", "Cancel Requested"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    # Relationships
    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
    )

    # Per-order customer snapshot.
    # Admin orders must keep the exact name/phone entered for that order,
    # even when a reusable Customer profile also exists.
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True, db_index=True)
    technician = models.ForeignKey(
        "accounts.Technician",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    # Order details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    service_date = models.DateField(
        null=True, blank=True,
        help_text="Gregorian storage for the Jalali service date entered by admin.",
    )
    scheduled_for = models.DateTimeField(null=True, blank=True)

    # Status & priority
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    # Pricing
    price_estimate = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        help_text="Estimated price before work starts.",
    )
    final_price = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        help_text="Final price after work is done.",
    )

    # Operational settlement fields. These are not the customer invoice.
    extra_payment = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        help_text="Additional payment recorded on the order workflow.",
    )
    wage_deduction = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        help_text="Amount deducted from technician wage for this order.",
    )

    # Skill requirement for technician matching
    required_skill = models.CharField(
        max_length=100,
        blank=True,
        help_text="Required skill name for technician matching.",
    )

    # Service category/subcategory (optional, for structured service selection)
    service_category = models.ForeignKey(
        "tenants.CompanyServiceCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    service_subcategory = models.ForeignKey(
        "tenants.CompanyServiceSubCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    # Priority-based visibility timestamps (for delayed technician visibility)
    priority2_visible_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this order becomes visible to priority-2 technicians.",
    )
    priority3_visible_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this order becomes visible to priority-3 technicians.",
    )
    accepted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp when a technician accepted this order.",
    )

    # Timestamps
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    internal_note = models.TextField(
        blank=True,
        help_text="Admin/staff internal note. Not visible to customers.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "customer"]),
            models.Index(fields=["company", "technician"]),
        ]

    def __str__(self) -> str:
        return f"Order #{self.pk} - {self.title} [{self.status}]"

    @property
    def display_customer_name(self) -> str:
        if self.customer_name:
            return self.customer_name
        if self.customer_id:
            return f"{self.customer.first_name} {self.customer.last_name}".strip()
        return ""

    @property
    def display_customer_phone(self) -> str:
        if self.customer_phone:
            return self.customer_phone
        if self.customer_id:
            return self.customer.phone
        return ""

    @property
    def address_text(self) -> str:
        """
        Backward-compatible address label for invoices/templates.

        Some invoice templates read `order.address_text`. The real database field
        on this model is `address`, so this property prevents template crashes
        without requiring a migration.
        """
        if self.address:
            return self.address

        customer = getattr(self, "customer", None)
        if customer:
            for field_name in ("address", "full_address", "customer_address", "location_text"):
                value = getattr(customer, field_name, None)
                if value:
                    return str(value)

        return "آدرس ثبت نشده"

    @property
    def display_service_date_jalali(self) -> str:
        if not self.service_date:
            return ""
        from apps.common.jalali import format_jalali_date
        return format_jalali_date(self.service_date)


class OrderItemDefinition(CompanyOwnedModel):
    """
    Dynamic item definition for orders.

    Admins define what data fields should be collected per order
    for a given service category. Each definition has a kind (number, money, text, bool).

    Example:
        Category: "نصب کولر" (AC Install)
        Items: "تعداد اسپلیت" (NUMBER), "هزینه لوله‌کشی" (MONEY), "آدرس دقیق" (TEXT)
    """

    class Kind(models.TextChoices):
        NUMBER = "number", "Number"
        MONEY = "money", "Money"
        TEXT = "text", "Text"
        BOOL = "bool", "Boolean"

    category = models.ForeignKey(
        "tenants.CompanyServiceCategory",
        on_delete=models.CASCADE,
        related_name="item_definitions",
    )
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return f"{self.title} ({self.get_kind_display()})"


class OrderItemValue(models.Model):
    """
    Captured value for a dynamic order item.

    Each order can have multiple item values, one per OrderItemDefinition.
    The value is stored in the appropriate typed field based on the definition's kind.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="item_values",
    )
    item = models.ForeignKey(
        OrderItemDefinition,
        on_delete=models.CASCADE,
        related_name="values",
    )
    value_number = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    value_text = models.TextField(blank=True, null=True)
    value_bool = models.BooleanField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "item"],
                name="unique_order_item_value",
            ),
        ]

    def __str__(self) -> str:
        return f"Order#{self.order_id} → {self.item.title}"


class OrderStatusLog(CompanyOwnedModel):
    """
    Audit log for order status changes.

    Every status transition creates a log entry.
    Used for:
    - Audit trail
    - Dispute resolution
    - Analytics
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    old_status = models.CharField(max_length=20, choices=Order.Status.choices)
    new_status = models.CharField(max_length=20, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_status_changes",
    )
    note = models.TextField(blank=True, help_text="Optional note about the change.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.order_id}: {self.old_status} → {self.new_status}"
