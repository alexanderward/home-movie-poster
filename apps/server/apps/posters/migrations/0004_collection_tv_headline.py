from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posters', '0003_collections'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='tv_headline',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='collection',
            name='show_headline',
            field=models.BooleanField(default=True),
        ),
    ]
