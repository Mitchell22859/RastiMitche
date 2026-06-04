# Generated for RastiClean financial policy Phase 1

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0005_invoice_technician_goods_wage_percent_snapshot_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="gross_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Sum of row gross amounts before row discounts.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="row_discount_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Total discount applied directly on invoice rows.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="net_amount_before_invoice_discounts",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Gross amount minus row discounts, before extra/campaign discounts.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="extra_discount_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Manual/extra invoice-level discount.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="campaign_discount_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Campaign/discount-code invoice-level discount.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="total_discount_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Total invoice-level discount: extra + campaign.",
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_service_total",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_goods_total",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_travel_total",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_extra_discount_amount",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_campaign_discount_amount",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_campaign_discount_policy",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_extra_discount_policy",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_technician_gross_share",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_company_gross_share",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_technician_absorbed_discount",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_company_absorbed_discount",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_technician_wage",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_company_share",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_payment_method",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_payment_reference",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="settled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                help_text="Legacy total invoice-level discount. Kept in sync with extra + campaign discounts.",
                max_digits=12,
            ),
        ),
    ]
