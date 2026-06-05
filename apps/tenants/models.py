"""
Tenants - Models.

Company model represents a tenant in the system.
All tenant-scoped resources reference Company via company_id.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class Company(models.Model):
    """
    Core tenant model.

    Each company is a separate tenant with its own isolated data.
    The 'code' field is used for path-based tenant resolution.

    Example URL: /n54/ → Company with code='n54'
    """

    name = models.CharField(max_length=200)
    code = models.SlugField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique code used in URLs for tenant resolution. e.g. 'n54'",
    )
    slug = models.SlugField(max_length=200, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive companies cannot be accessed.",
    )
    logo = models.ImageField(upload_to="companies/logos/", blank=True, null=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    economic_code = models.CharField(max_length=50, blank=True)
    website = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class CompanyFinancialPolicy(models.Model):
    """
    Per-company financial policy for discount absorption and settlement.

    These policies are read when an invoice is financially settled.
    Values are later snapshotted on the invoice so historical settlement does
    not change if the company updates its policy.
    """

    class DiscountPolicy(models.TextChoices):
        COMPANY = "company", "Company absorbs discount"
        TECHNICIAN = "technician", "Technician absorbs discount"
        HALF_HALF = "half_half", "Split equally"
        PROPORTIONAL_SHARE = "proportional_share", "Split by share ratio"

    class PayoutStrategy(models.TextChoices):
        DIRECT_TO_COMPANY = "direct_to_company", "واریز کامل به حساب شرکت"
        SPLIT_WITH_TECHNICIAN = "split_with_technician", "تسهیم با تکنسین تأییدشده"

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_policy",
    )
    campaign_discount_policy = models.CharField(
        max_length=30,
        choices=DiscountPolicy.choices,
        default=DiscountPolicy.COMPANY,
        help_text="Who absorbs campaign/discount-code discounts by default.",
    )
    extra_discount_policy = models.CharField(
        max_length=30,
        choices=DiscountPolicy.choices,
        default=DiscountPolicy.TECHNICIAN,
        help_text="Who absorbs extra/manual invoice discounts by default.",
    )
    # Payout strategy fields (Payment P2)
    payout_strategy = models.CharField(
        max_length=30,
        choices=PayoutStrategy.choices,
        default=PayoutStrategy.DIRECT_TO_COMPANY,
        help_text="نحوه پرداخت دستمزد تکنسین پس از وصول فاکتور",
    )
    platform_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="درصد کارمزد پلتفرم از کل مبلغ فاکتور — فقط توسط پلتفرم قابل تغییر است",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Financial Policy"
        verbose_name_plural = "Company Financial Policies"

    def __str__(self) -> str:
        return f"Financial Policy: {self.company.name}"


class CompanyPage(models.Model):
    """
    Public landing page content for a company.
    Each company can have a customized public page.
    Managed by COMPANY_ADMIN via /<company_code>/admin/page/
    """

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="page",
    )
    title = models.CharField(max_length=200, blank=True)
    intro_text = models.TextField(
        blank=True,
        help_text="Introduction text displayed on the public page.",
    )
    logo = models.ImageField(upload_to="companies/pages/logos/", blank=True, null=True)
    hero_image = models.ImageField(upload_to="companies/pages/heroes/", blank=True, null=True)
    is_request_form_enabled = models.BooleanField(
        default=True,
        help_text="If disabled, visitors cannot submit service requests.",
    )
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    working_hours = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. Saturday-Thursday 9:00-18:00",
    )
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Page: {self.company.name}"


class CompanyService(CompanyOwnedModel):
    """
    A service offered by a company.
    Displayed on the public page for customers to select.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class CompanyGalleryImage(CompanyOwnedModel):
    """
    Gallery image for the company public page.
    """

    image = models.ImageField(upload_to="companies/gallery/")
    caption = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self) -> str:
        return f"Gallery: {self.caption or 'Image'} ({self.company.name})"


class CompanyServiceCategory(CompanyOwnedModel):
    """
    Service category for a company.
    Groups subcategories under a top-level category.
    Used in admin order creation and public display.
    """

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]
        verbose_name_plural = "Service Categories"

    def __str__(self) -> str:
        return self.title


class CompanyServiceSubCategory(CompanyOwnedModel):
    """
    Subcategory under a service category.
    Represents a specific service type with base price.
    """

    category = models.ForeignKey(
        CompanyServiceCategory,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]
        verbose_name_plural = "Service Subcategories"

    def __str__(self) -> str:
        return f"{self.category.title} → {self.title}"


class CompanySettings(models.Model):
    """
    Per-company configuration for order routing and technician visibility.

    Controls:
    - Delayed visibility for lower-priority technicians
    - Future order visibility rules
    - Workload limits
    - Auto-recycle behaviour on cancel requests
    """

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    priority2_delay_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Minutes before priority-2 technicians see a new order.",
    )
    priority3_delay_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Minutes before priority-3 technicians see a new order.",
    )
    show_future_orders_to_technicians = models.BooleanField(
        default=False,
        help_text="If True, technicians can see orders scheduled in the future.",
    )
    future_orders_visible_after = models.TimeField(
        default="07:30", null=True, blank=True,
        help_text="Time of day after which future orders become visible (if enabled).",
    )
    max_active_orders_per_technician = models.PositiveIntegerField(
        default=5,
        help_text="Max concurrent in-progress orders a technician can hold.",
    )
    auto_recycle_cancel_request = models.BooleanField(
        default=False,
        help_text="If True, cancelled orders are automatically recycled back to NEW.",
    )
    respect_sms_template_time_window = models.BooleanField(
        default=True,
        help_text="If True, SMS messages respect template send_start_time/send_end_time windows.",
    )

    class Meta:
        verbose_name_plural = "Company Settings"

    def __str__(self) -> str:
        return f"Settings: {self.company.name}"


class ServiceRequest(CompanyOwnedModel):
    """
    Public service request submitted by a visitor.
    Creates an Order + optionally a Customer record.

    Flow:
    1. Visitor fills form on /<company_code>/request/
    2. ServiceRequest is created
    3. Order is created with status NEW
    4. Customer is created or matched by phone
    """

    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    service = models.ForeignKey(
        CompanyService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests",
    )
    description = models.TextField(blank=True)
    preferred_time = models.CharField(
        max_length=200,
        blank=True,
        help_text="Preferred date/time for service.",
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_request",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Request: {self.customer_name} ({self.customer_phone})"
