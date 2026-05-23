from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="group",
            name="unique_group_per_owner",
        ),
        migrations.RemoveConstraint(
            model_name="tag",
            name="unique_tag_per_owner",
        ),
        migrations.AddConstraint(
            model_name="group",
            constraint=models.UniqueConstraint(
                Lower("name"),
                models.F("owner"),
                name="unique_group_per_owner_ci",
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                Lower("name"),
                models.F("owner"),
                name="unique_tag_per_owner_ci",
            ),
        ),
    ]
