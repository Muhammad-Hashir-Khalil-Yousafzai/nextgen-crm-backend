from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0001_initial'),
        ('crmapp', '0007_terminationreinstatement'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payrollline',
            name='employee',
        ),
        migrations.DeleteModel(
            name='Employee',
        ),
        migrations.AddField(
            model_name='payrollline',
            name='employee',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='payroll_lines',
                to='crmapp.employee',
                null=True,
            ),
        ),
    ]