"""Drop the legacy tables once their rows live in django-widget-hub."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("services", "0005_move_widgets_to_widget_hub")]

    operations = [
        migrations.DeleteModel(name="ServiceCredential"),
        migrations.DeleteModel(name="WidgetInstance"),
    ]
