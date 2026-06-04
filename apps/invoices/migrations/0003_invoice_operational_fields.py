# Generated for Phase 23A - invoice workflow cleanup

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("invoices", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_invoices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="public_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Short public code for read-only invoice sharing.",
                max_length=24,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="customer_name_snapshot",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="invoice",
            name="customer_phone_snapshot",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="invoice",
            name="address_snapshot",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="technician_name_snapshot",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="invoice",
            name="technician_phone_snapshot",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="invoice",
            name="service_title_snapshot",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddField(
            model_name="invoice",
            name="service_date_snapshot",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="footer_text",
            field=models.TextField(
                blank=True,
                default="مسئولیت فاکتور صادره بر عهده ارائه‌دهنده خدمت می‌باشد.",
            ),
        ),
        migrations.AlterField(
            model_name="invoiceitem",
            name="quantity",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=12),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="discount_amount",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterUniqueTogether(
            name="invoice",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                fields=("company", "invoice_number"),
                name="unique_invoice_number_per_company",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=models.Index(fields=["public_code"], name="invoices_in_public_08b0d2_idx"),
        ),
    ]
