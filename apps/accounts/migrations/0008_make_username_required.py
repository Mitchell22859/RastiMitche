"""
Make username field non-nullable after data migration populated all rows.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_populate_usernames"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companyuser",
            name="username",
            field=models.CharField(
                db_index=True,
                help_text="Primary login identifier. Lowercase, letters/numbers/underscore/dash.",
                max_length=50,
                unique=True,
            ),
        ),
    ]
