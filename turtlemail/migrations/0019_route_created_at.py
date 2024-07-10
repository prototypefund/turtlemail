# Generated by Django 4.2.13 on 2024-07-09 13:45

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("turtlemail", "0018_alter_routestep_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="route",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="Datetime",
            ),
            preserve_default=False,
        ),
    ]
