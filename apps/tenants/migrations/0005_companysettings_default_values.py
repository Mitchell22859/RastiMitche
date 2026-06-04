# Generated for Phase 21A: CompanySettings defaults matching old workflow

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0004_company_economic_code_company_website"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companysettings",
            name="priority2_delay_minutes",
            field=models.PositiveIntegerField(default=30, help_text="Minutes before priority-2 technicians see a new order."),
        ),
        migrations.AlterField(
            model_name="companysettings",
            name="priority3_delay_minutes",
            field=models.PositiveIntegerField(default=60, help_text="Minutes before priority-3 technicians see a new order."),
        ),
        migrations.AlterField(
            model_name="companysettings",
            name="future_orders_visible_after",
            field=models.TimeField(blank=True, default="07:30", help_text="Time of day after which future orders become visible (if enabled).", null=True),
        ),
        migrations.AlterField(
            model_name="companysettings",
            name="max_active_orders_per_technician",
            field=models.PositiveIntegerField(default=5, help_text="Max concurrent in-progress orders a technician can hold."),
        ),
    ]
