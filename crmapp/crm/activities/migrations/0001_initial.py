from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth',          '0012_alter_user_first_name_max_length'),
        ('crm_contacts',  '0001_initial'),
        ('crm_companies', '0001_initial'),
        ('crm_leads',     '0001_initial'),
        ('crm_deals',     '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title',         models.CharField(max_length=500)),
                ('activity_type', models.CharField(
                    choices=[
                        ('Meeting', 'Meeting'),
                        ('Calls',   'Calls'),
                        ('Tasks',   'Tasks'),
                        ('Email',   'Email'),
                    ],
                    default='Meeting',
                    max_length=20
                )),
                ('due_date',      models.DateField()),
                ('created_date',  models.DateField(auto_now_add=True)),
                ('owner',         models.CharField(max_length=255)),
                ('owner_image',   models.TextField(
                    blank=True,
                    help_text=(
                        'Base64-encoded image (e.g. data:image/png;base64,…). '
                        'Leave empty to display the activity-type icon instead.'
                    )
                )),
                ('notes',         models.TextField(blank=True)),
                ('updated_at',    models.DateTimeField(auto_now=True)),
                ('contact',  models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activities',
                    to='crm_contacts.contact'
                )),
                ('company',  models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activities',
                    to='crm_companies.company'
                )),
                ('lead',     models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activities',
                    to='crm_leads.lead'
                )),
                ('deal',     models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activities',
                    to='crm_deals.deal'
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activities_created',
                    to='auth.user'
                )),
            ],
            options={
                'db_table': 'activities',
                'ordering': ['-created_date', '-id'],
            },
        ),
    ]
