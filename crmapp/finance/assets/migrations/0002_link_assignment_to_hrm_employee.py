from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
        ('crmapp', '0007_terminationreinstatement'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assetassignment',
            name='employee_name',
        ),
        migrations.RemoveField(
            model_name='assetassignment',
            name='department',
        ),
        migrations.AddField(
            model_name='assetassignment',
            name='employee',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='asset_assignments',
                to='crmapp.employee',
                null=True,
            ),
        ),
    ]