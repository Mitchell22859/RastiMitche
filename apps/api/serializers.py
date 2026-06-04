"""
API - Serializers.

DRF serializers for core models.
Serializers are thin — they serialize/deserialize data only.
Business logic remains in services.
"""
from rest_framework import serializers

from apps.accounts.models import Customer, Technician
from apps.invoices.models import Invoice, InvoiceItem
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderStatusLog
from apps.tenants.models import Company, CompanyService, ServiceRequest


# =============================================================================
# TENANT SERIALIZERS
# =============================================================================


class OrderSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    customer_name = serializers.SerializerMethodField()
    technician_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "title", "description", "address", "status", "status_display",
            "priority", "priority_display", "price_estimate", "final_price",
            "required_skill", "scheduled_for", "completed_at",
            "customer", "customer_name", "technician", "technician_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "completed_at", "created_at", "updated_at"]

    def get_customer_name(self, obj) -> str:
        return str(obj.customer) if obj.customer else ""

    def get_technician_name(self, obj) -> str:
        return str(obj.technician) if obj.technician else ""


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating orders via API."""
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, default="")
    address = serializers.CharField(required=False, default="")
    priority = serializers.ChoiceField(choices=Order.Priority.choices, default=Order.Priority.NORMAL)
    price_estimate = serializers.IntegerField(required=False, default=0)
    required_skill = serializers.CharField(required=False, default="", max_length=100)
    customer_id = serializers.IntegerField()


class OrderStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusLog
        fields = ["id", "old_status", "new_status", "changed_by", "note", "created_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_payable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "status", "status_display", "is_payable",
            "subtotal", "tax_amount", "discount_amount", "total_amount",
            "issued_at", "paid_at", "customer", "order",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["id", "description", "quantity", "unit_price", "total_price"]


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_notification_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "notification_type", "type_display", "title", "message",
            "is_read", "read_at", "related_order", "related_invoice",
            "created_at",
        ]
        read_only_fields = fields


class CompanyServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyService
        fields = ["id", "title", "description", "base_price", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ServiceRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequest
        fields = [
            "id", "customer_name", "customer_phone", "customer_email",
            "address", "service", "description", "preferred_time",
            "order", "created_at",
        ]
        read_only_fields = ["id", "order", "created_at"]


class ServiceRequestCreateSerializer(serializers.Serializer):
    """Serializer for public service request creation."""
    customer_name = serializers.CharField(max_length=200)
    customer_phone = serializers.CharField(max_length=15)
    customer_email = serializers.EmailField(required=False, default="")
    address = serializers.CharField(required=False, default="")
    service_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, default="")
    preferred_time = serializers.CharField(required=False, default="", max_length=200)


# =============================================================================
# PLATFORM SERIALIZERS
# =============================================================================


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = [
            "id", "name", "code", "slug", "is_active",
            "email", "phone", "address", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
