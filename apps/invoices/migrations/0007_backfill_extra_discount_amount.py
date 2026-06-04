# Generated for RastiClean financial policy Phase 1

from decimal import Decimal

from django.db import migrations


def _d(value):
    return value or Decimal("0")


def backfill_invoice_financial_amounts(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")
    InvoiceItem = apps.get_model("invoices", "InvoiceItem")

    for invoice in Invoice.objects.all().iterator(chunk_size=200):
        gross_amount = Decimal("0")
        row_discount_amount = Decimal("0")
        net_amount = Decimal("0")

        for item in InvoiceItem.objects.filter(invoice_id=invoice.id).iterator(chunk_size=200):
            gross = _d(item.quantity) * _d(item.unit_price)
            row_discount = _d(item.discount_amount)
            net = gross - row_discount
            if net < 0:
                net = Decimal("0")
            gross_amount += gross
            row_discount_amount += row_discount
            net_amount += net

        # If an old invoice has no item rows available, preserve its current subtotal.
        if gross_amount == 0 and net_amount == 0 and _d(invoice.subtotal) > 0:
            gross_amount = _d(invoice.subtotal)
            net_amount = _d(invoice.subtotal)
            row_discount_amount = Decimal("0")

        legacy_discount = _d(invoice.discount_amount)
        invoice.gross_amount = gross_amount
        invoice.row_discount_amount = row_discount_amount
        invoice.net_amount_before_invoice_discounts = net_amount
        invoice.extra_discount_amount = legacy_discount
        invoice.campaign_discount_amount = Decimal("0")
        invoice.total_discount_amount = legacy_discount
        invoice.save(
            update_fields=[
                "gross_amount",
                "row_discount_amount",
                "net_amount_before_invoice_discounts",
                "extra_discount_amount",
                "campaign_discount_amount",
                "total_discount_amount",
            ]
        )


def reverse_backfill_invoice_financial_amounts(apps, schema_editor):
    Invoice = apps.get_model("invoices", "Invoice")
    Invoice.objects.update(
        gross_amount=0,
        row_discount_amount=0,
        net_amount_before_invoice_discounts=0,
        extra_discount_amount=0,
        campaign_discount_amount=0,
        total_discount_amount=0,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0006_invoice_financial_policy_fields"),
    ]

    operations = [
        migrations.RunPython(
            backfill_invoice_financial_amounts,
            reverse_backfill_invoice_financial_amounts,
        ),
    ]
