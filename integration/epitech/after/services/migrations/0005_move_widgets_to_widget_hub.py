"""Copy widget instances and service tokens to django-widget-hub's tables."""

import logging

from cryptography.fernet import InvalidToken
from django.db import migrations

from services.legacy import convert_instance
from services.models import decrypt_token
from widget_hub.credentials import encrypt

logger = logging.getLogger(__name__)


def forwards(apps, schema_editor):
    """Copy every legacy row; rows that cannot be kept are logged by id, never by content."""
    OldInstance = apps.get_model("services", "WidgetInstance")
    OldCredential = apps.get_model("services", "ServiceCredential")
    NewInstance = apps.get_model("widget_hub", "WidgetInstance")
    NewCredential = apps.get_model("widget_hub", "Credential")

    for old in OldInstance.objects.all():
        fields = convert_instance(
            old.service_name, old.widget_name, old.params, old.refresh_rate, old.position
        )
        if fields is None:
            logger.warning("Widget instance %s could not be migrated; skipped.", old.pk)
            continue
        new = NewInstance.objects.create(owner_id=old.user_id, **fields)
        # keep the original creation date (auto_now_add sets "now" on create)
        NewInstance.objects.filter(pk=new.pk).update(created_at=old.created_at)

    for old in OldCredential.objects.all():
        try:
            secret = decrypt_token(old.token)
        except InvalidToken:
            logger.warning("Credential %s is unreadable (SECRET_KEY changed); skipped.", old.pk)
            continue
        NewCredential.objects.update_or_create(
            owner_id=old.user_id,
            service=old.service_name,
            defaults={"encrypted_secret": encrypt(secret)},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0004_encrypt_service_credential_token"),
        ("widget_hub", "0002_credential"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
