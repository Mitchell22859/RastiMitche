from django.db import migrations, models
from django.utils import timezone
import math


def backfill_smsoutbox_pricing_snapshot(apps, schema_editor):
    SMSOutbox = apps.get_model('sms', 'SMSOutbox')
    try:
        GlobalSMSPricingSetting = apps.get_model('platform_core', 'GlobalSMSPricingSetting')
        pricing = GlobalSMSPricingSetting.objects.first()
        characters_per_sms = int(getattr(pricing, 'characters_per_sms', 0) or 0) if pricing else 0
        price_per_sms_rial = int(getattr(pricing, 'price_per_sms_rial', 0) or 0) if pricing else 0
    except Exception:
        characters_per_sms = 0
        price_per_sms_rial = 0

    now = timezone.now()
    for sms in SMSOutbox.objects.all().only('id', 'message', 'created_at').iterator():
        text = getattr(sms, 'message', '') or ''
        length = len(text)
        parts = int(math.ceil(length / characters_per_sms)) if length > 0 and characters_per_sms > 0 else 0
        cost = int(parts * price_per_sms_rial)
        SMSOutbox.objects.filter(pk=sms.pk).update(
            message_length_snapshot=length,
            sms_parts_snapshot=parts,
            sms_cost_rial_snapshot=cost,
            pricing_characters_per_sms_snapshot=characters_per_sms,
            pricing_price_per_sms_rial_snapshot=price_per_sms_rial,
            pricing_snapshot_at=getattr(sms, 'created_at', None) or now,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('sms', '0008_expand_sms_template_event_keys'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsoutbox',
            name='message_length_snapshot',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='smsoutbox',
            name='sms_parts_snapshot',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='smsoutbox',
            name='sms_cost_rial_snapshot',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='smsoutbox',
            name='pricing_characters_per_sms_snapshot',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='smsoutbox',
            name='pricing_price_per_sms_rial_snapshot',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='smsoutbox',
            name='pricing_snapshot_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_smsoutbox_pricing_snapshot, migrations.RunPython.noop),
    ]
