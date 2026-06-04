"""
Invoices - Models.

Tenant-scoped invoice system.
All invoice data MUST be isolated by company.

Phase 23A note:
- Order data is copied into invoice snapshots so later order/customer edits do not
  rewrite an already issued invoice.
- Invoice prices live here, not on the order form.
"""
import secrets
import string

from django.conf import settings
from django.db import models

from apps.common.models import CompanyOwnedModel


class Invoice(CompanyOwnedModel):
    """
    Invoice generated for an order or created as a standalone draft.
    Tenant-scoped: always filtered by company.

    Statuses:
        DRAFT → ISSUED → PAID
        DRAFT/ISSUED → CANCELLED
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    # Relationships
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )

    # Invoice identity
    invoice_number = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Unique per company. Format: INV-<CODE>-<SEQUENCE>",
    )
    public_code = models.CharField(
        max_length=24,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Short public code for read-only invoice sharing.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # Snapshots copied from the order/customer at invoice creation time
    customer_name_snapshot = models.CharField(max_length=200, blank=True)
    customer_phone_snapshot = models.CharField(max_length=30, blank=True)
    address_snapshot = models.TextField(blank=True)
    technician_name_snapshot = models.CharField(max_length=200, blank=True)
    technician_phone_snapshot = models.CharField(max_length=30, blank=True)
    service_title_snapshot = models.CharField(max_length=250, blank=True)
    service_date_snapshot = models.DateField(null=True, blank=True)

    # Technician wage percentage snapshots (frozen at invoice creation/issue time)
    technician_service_wage_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
    )
    technician_goods_wage_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
    )
    technician_travel_wage_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
    )

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Legacy total invoice-level discount. Kept in sync with extra + campaign discounts.",
    )

    # Phase 1 financial foundation fields.
    # These fields separate row-level discounts from invoice-level discounts.
    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Sum of row gross amounts before row discounts.",
    )
    row_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Total discount applied directly on invoice rows.",
    )
    net_amount_before_invoice_discounts = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Gross amount minus row discounts, before extra/campaign discounts.",
    )
    extra_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Manual/extra invoice-level discount.",
    )
    campaign_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Campaign/discount-code invoice-level discount.",
    )
    total_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Total invoice-level discount: extra + campaign.",
    )

    total_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    # Settlement snapshots. These are null until the invoice is finalized at PAID time.
    settled_service_total = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_goods_total = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_travel_total = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_extra_discount_amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_campaign_discount_amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_campaign_discount_policy = models.CharField(max_length=30, null=True, blank=True)
    settled_extra_discount_policy = models.CharField(max_length=30, null=True, blank=True)
    settled_technician_gross_share = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_company_gross_share = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_technician_absorbed_discount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_company_absorbed_discount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_technician_wage = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_company_share = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    settled_payment_method = models.CharField(max_length=50, null=True, blank=True)
    settled_payment_reference = models.CharField(max_length=200, null=True, blank=True)
    settled_discount_code_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="DiscountCode id used at settlement time, stored without FK for audit stability.",
    )
    settled_at = models.DateTimeField(null=True, blank=True)

    # Dates
    issued_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    footer_text = models.TextField(
        blank=True,
        default="مسئولیت فاکتور صادره بر عهده ارائه‌دهنده خدمت می‌باشد.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "invoice_number"],
                name="unique_invoice_number_per_company",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "customer"]),
            models.Index(fields=["public_code"]),
        ]

    def __str__(self) -> str:
        return f"Invoice #{self.invoice_number} [{self.status}]"

    @property
    def is_payable(self) -> bool:
        """Invoice can be paid only if it is ISSUED."""
        return self.status == self.Status.ISSUED

    @property
    def display_customer_name(self) -> str:
        if self.customer_name_snapshot:
            return self.customer_name_snapshot
        if self.customer_id:
            return str(self.customer)
        return ""

    @property
    def display_customer_phone(self) -> str:
        if self.customer_phone_snapshot:
            return self.customer_phone_snapshot
        if self.customer_id:
            return self.customer.phone
        return ""

    @property
    def display_service_date_jalali(self) -> str:
        if not self.service_date_snapshot:
            return ""
        from apps.common.jalali import format_jalali_date
        return format_jalali_date(self.service_date_snapshot)

    @staticmethod
    def _generate_public_code(invoice_id: int) -> str:
        alphabet = string.ascii_letters + string.digits
        token = "".join(secrets.choice(alphabet) for _ in range(6))
        return f"{invoice_id}-{token}"

    def ensure_public_code(self) -> None:
        if self.public_code or not self.pk:
            return
        code = self._generate_public_code(self.pk)
        while Invoice.objects.filter(public_code=code).exclude(pk=self.pk).exists():
            code = self._generate_public_code(self.pk)
        self.public_code = code

    def recalculate_totals(self, *, save: bool = True) -> None:
        gross_amount = sum(item.gross_price for item in self.items.all())
        row_discount_amount = sum((item.discount_amount or 0) for item in self.items.all())
        subtotal = sum(item.net_price for item in self.items.all())

        extra_discount = self.extra_discount_amount or 0
        campaign_discount = self.campaign_discount_amount or 0
        total_discount = extra_discount + campaign_discount

        self.gross_amount = gross_amount
        self.row_discount_amount = row_discount_amount
        self.net_amount_before_invoice_discounts = subtotal
        self.subtotal = subtotal
        self.total_discount_amount = total_discount
        self.discount_amount = total_discount
        self.total_amount = max(0, subtotal + (self.tax_amount or 0) - total_discount)
        if save:
            self.save(update_fields=[
                "gross_amount",
                "row_discount_amount",
                "net_amount_before_invoice_discounts",
                "subtotal",
                "extra_discount_amount",
                "campaign_discount_amount",
                "total_discount_amount",
                "discount_amount",
                "total_amount",
                "updated_at",
            ])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if (is_new or not self.public_code) and self.pk:
            self.ensure_public_code()
            super().save(update_fields=["public_code"])


class InvoiceItem(CompanyOwnedModel):
    """
    Line item on an invoice.
    Prices are deliberately stored on invoice items, not on Order.
    """

    class RowType(models.TextChoices):
        SERVICE = "service", "اجرت خدمات"
        GOODS = "goods", "کالا / قطعه"
        TRAVEL = "travel", "ایاب و ذهاب"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=300)
    row_type = models.CharField(
        max_length=10,
        choices=RowType.choices,
        default=RowType.SERVICE,
        help_text="نوع ردیف برای محاسبه دستمزد تکنسین.",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.description} x {self.quantity}"

    @property
    def gross_price(self):
        return (self.quantity or 0) * (self.unit_price or 0)

    @property
    def net_price(self):
        return max(0, self.gross_price - (self.discount_amount or 0))

    def save(self, *args, **kwargs):
        """Auto-calculate total_price."""
        self.total_price = self.net_price
        super().save(*args, **kwargs)


def generate_invoice_number(company) -> str:
    """
    Generate a unique invoice number for a company.

    Format: INV-<COMPANY_CODE>-<SEQUENCE_PADDED>
    Example: INV-N54-00042
    """
    count = Invoice.objects.filter(company=company).count()
    number = f"INV-{company.code.upper()}-{count + 1:05d}"
    while Invoice.objects.filter(company=company, invoice_number=number).exists():
        count += 1
        number = f"INV-{company.code.upper()}-{count + 1:05d}"
    return number

