# Generated by Django 3.0 on 2020-05-15 01:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('prospector', '0015_auto_20200515_0101'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tasktype',
            name='typical_next_task',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='prospector.TaskType', verbose_name='Type de tâche suivante typique'),
        ),
    ]
