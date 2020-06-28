# Generated by Django 3.0 on 2020-06-28 13:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('prospector', '0021_auto_20200626_0842'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fanzine',
            name='num_ratings',
        ),
        migrations.AlterField(
            model_name='fanzine',
            name='prev_editions',
            field=models.IntegerField(default=0, verbose_name='Participation aux précédentes éditions'),
        ),
        migrations.CreateModel(
            name='Rating',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(max_length=128)),
                ('score', models.IntegerField()),
                ('comment', models.CharField(max_length=1024)),
                ('fanzine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='prospector.Fanzine')),
            ],
        ),
    ]