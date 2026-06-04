"""
Data migration: populate username from phone for existing users.

Existing demo users (platform_owner, n54_admin, etc.) will have their
phone values used as usernames. This preserves backward compatibility.
"""
from django.db import migrations


def populate_usernames(apps, schema_editor):
    CompanyUser = apps.get_model("accounts", "CompanyUser")
    for user in CompanyUser.objects.filter(username__isnull=True):
        # Use phone as username (e.g. "platform_owner", "n54_admin")
        # These are the existing demo user phone values
        user.username = user.phone.lower()
        user.save(update_fields=["username"])


def reverse_populate(apps, schema_editor):
    # No reverse needed — username field will be dropped if migration is reversed
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_add_username_field"),
    ]

    operations = [
        migrations.RunPython(populate_usernames, reverse_populate),
    ]
