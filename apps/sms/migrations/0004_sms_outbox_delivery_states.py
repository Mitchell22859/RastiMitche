# Generated manually for SMS outbox delivery workflow hardening.
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("sms", "0003_alter_smsoutbox_template_key_alter_smstemplate_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="smsoutbox",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="smsoutbox",
            name="queued_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="smsoutbox",
            name="sending_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="smsoutbox",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="smsoutbox",
            name="failed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="smsoutbox",
            name="last_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="smsoutbox",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "در صف ارسال"),
                    ("sending", "در حال ارسال"),
                    ("sent", "ارسال شده"),
                    ("delivered", "ارسال موفق"),
                    ("failed", "ارسال ناموفق"),
                    ("cancelled", "لغو شده"),
                    ("pending", "در صف ارسال (قدیمی)"),
                ],
                db_index=True,
                default="queued",
                max_length=10,
            ),
        ),
        migrations.AddIndex(
            model_name="smsoutbox",
            index=models.Index(fields=["company", "status", "send_at"], name="sms_outbox_company_due_idx"),
        ),
        migrations.AddIndex(
            model_name="smsoutbox",
            index=models.Index(fields=["company", "phone_number", "template_key"], name="sms_outbox_company_phone_idx"),
        ),
    ]
