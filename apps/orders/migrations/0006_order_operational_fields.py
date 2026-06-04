# Generated for Phase 20A: restore operational admin order fields.
from django.db import migrations, models


def copy_customer_snapshot(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.select_related("customer").all().iterator():
        changed = []
        if order.customer_id:
            name = f"{order.customer.first_name} {order.customer.last_name}".strip()
            if name and not order.customer_name:
                order.customer_name = name
                changed.append("customer_name")
            if order.customer.phone and not order.customer_phone:
                order.customer_phone = order.customer.phone
                changed.append("customer_phone")
        if order.scheduled_for and not order.service_date:
            order.service_date = order.scheduled_for.date()
            changed.append("service_date")
        if changed:
            order.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_order_accepted_at_order_priority2_visible_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_phone",
            field=models.CharField(blank=True, db_index=True, max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="service_date",
            field=models.DateField(blank=True, help_text="Gregorian storage for the Jalali service date entered by admin.", null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="extra_payment",
            field=models.DecimalField(decimal_places=0, default=0, help_text="Additional payment recorded on the order workflow.", max_digits=12),
        ),
        migrations.AddField(
            model_name="order",
            name="wage_deduction",
            field=models.DecimalField(decimal_places=0, default=0, help_text="Amount deducted from technician wage for this order.", max_digits=12),
        ),
        migrations.RunPython(copy_customer_snapshot, migrations.RunPython.noop),
    ]
