""" Migrations for the contacts app. """

import uuid

from django.db import migrations, models


def populate_contact_uuids(apps, schema_editor):
    Contact = apps.get_model("contacts", "Contact")
    for contact in Contact.objects.all().iterator():
        contact.uuid = uuid.uuid4()
        contact.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0003_scalar_sync_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_contact_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contact",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
