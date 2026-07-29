from django.core.management.base import BaseCommand
from crmapp.crm.pipeline.models import Pipeline


class Command(BaseCommand):
    help = 'Seed pipelines with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding pipelines...')

        data = [
            {'name':'Sales',         'total_value':4500,  'no_of_deals':315, 'stage':'Won',              'status':'Active',   'color':'#22c55e'},
            {'name':'Marketing',     'total_value':3150,  'no_of_deals':447, 'stage':'In Pipeline',      'status':'Active',   'color':'#a855f7'},
            {'name':'Calls',         'total_value':8400,  'no_of_deals':654, 'stage':'Won',              'status':'Active',   'color':'#22c55e'},
            {'name':'Email',         'total_value':6100,  'no_of_deals':545, 'stage':'Conversation',     'status':'Active',   'color':'#06b6d4'},
            {'name':'Chats',         'total_value':4700,  'no_of_deals':787, 'stage':'Won',              'status':'Active',   'color':'#22c55e'},
            {'name':'Operational',   'total_value':5500,  'no_of_deals':787, 'stage':'Follow Up',        'status':'Active',   'color':'#f59e0b'},
            {'name':'Collaborative', 'total_value':5000,  'no_of_deals':315, 'stage':'Won',              'status':'Inactive', 'color':'#22c55e'},
            {'name':'Differentiate', 'total_value':4500,  'no_of_deals':478, 'stage':'Schedule Service', 'status':'Active',   'color':'#ec4899'},
            {'name':'Interact',      'total_value':6200,  'no_of_deals':664, 'stage':'Won',              'status':'Active',   'color':'#22c55e'},
            {'name':'Identify',      'total_value':7400,  'no_of_deals':128, 'stage':'Lost',             'status':'Active',   'color':'#ef4444'},
        ]

        for d in data:
            Pipeline.objects.update_or_create(name=d['name'], defaults=d)

        self.stdout.write(self.style.SUCCESS(f'  Seeded {len(data)} pipelines ✅'))
