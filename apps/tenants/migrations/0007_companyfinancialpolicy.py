# Generated for RastiClean financial policy Phase 1

from django.db import migrations, models
import django.db.models.deletion


def create_default_financial_policies(apps, schema_editor):
    Company = apps.get_model("tenants", "Company")
    CompanyFinancialPolicy = apps.get_model("tenants", "CompanyFinancialPolicy")

    existing_company_ids = set(
        CompanyFinancialPolicy.objects.values_list("company_id", flat=True)
    )
    policies = []
    for company in Company.objects.all().only("id"):
        if company.id in existing_company_ids:
            continue
        policies.append(
            CompanyFinancialPolicy(
                company_id=company.id,
                campaign_discount_policy="company",
                extra_discount_policy="technician",
            )
        )
    if policies:
        CompanyFinancialPolicy.objects.bulk_create(policies, batch_size=500)


def delete_default_financial_policies(apps, schema_editor):
    CompanyFinancialPolicy = apps.get_model("tenants", "CompanyFinancialPolicy")
    CompanyFinancialPolicy.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_phase26_sms_templates"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyFinancialPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "campaign_discount_policy",
                    models.CharField(
                        choices=[
                            ("company", "Company absorbs discount"),
                            ("technician", "Technician absorbs discount"),
                            ("half_half", "Split equally"),
                            ("proportional_share", "Split by share ratio"),
                        ],
                        default="company",
                        help_text="Who absorbs campaign/discount-code discounts by default.",
                        max_length=30,
                    ),
                ),
                (
                    "extra_discount_policy",
                    models.CharField(
                        choices=[
                            ("company", "Company absorbs discount"),
                            ("technician", "Technician absorbs discount"),
                            ("half_half", "Split equally"),
                            ("proportional_share", "Split by share ratio"),
                        ],
                        default="technician",
                        help_text="Who absorbs extra/manual invoice discounts by default.",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="financial_policy",
                        to="tenants.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Company Financial Policy",
                "verbose_name_plural": "Company Financial Policies",
            },
        ),
        migrations.RunPython(
            create_default_financial_policies,
            delete_default_financial_policies,
        ),
    ]
