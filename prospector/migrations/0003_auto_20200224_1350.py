# Generated by Django 3.0.2 on 2020-02-24 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prospector', '0002_auto_20200210_2350'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='deal',
            name='floating',
        ),
        migrations.AddField(
            model_name='task',
            name='comment',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='todo_state',
            field=models.CharField(choices=[('0_done', 'Tâche terminée'), ('1_doing', 'Tâche en cours'), ('2_pro_waits_contact', 'Pro attend sur contact'), ('3_pro_waits_presidence', 'Pro attend sur présidence'), ('4_pro_waits_treasury', 'Pro attend sur trésorerie'), ('5_contact_waits_pro', 'Contact attend sur pro')], max_length=32),
        ),
        migrations.AlterField(
            model_name='tasktype',
            name='description',
            field=models.TextField(blank=True),
        ),
    ]
