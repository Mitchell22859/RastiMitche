# Generated for Phase 21A: company settings fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_companysettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="economic_code",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="company",
            name="website",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
