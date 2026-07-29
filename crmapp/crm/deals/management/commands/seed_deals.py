"""
python manage.py seed_deals

Seeds the deals table with the same sample data used in the frontend.
Safe to run multiple times — clears existing deals first.
"""
from django.core.management.base import BaseCommand
from crmapp.crm.deals.models import Deal


SAMPLE_DEALS = [
    {
        'title': 'Website Redesign',
        'code': 'WR',
        'value': 54500.00,
        'email': 'darlee@gmail.com',
        'phone': '(163) 2459 315',
        'location': 'New York, United States',
        'assigned_to': 'Sharon Roy',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Sharon',
        'probability': 85,
        'stage': 'new',
        'company_name': 'TechCorp Inc',
        'tags': ['VIP', 'Enterprise'],
    },
    {
        'title': 'Mobile App Development',
        'code': 'MA',
        'value': 32500.00,
        'email': 'client@innovate.com',
        'phone': '(987) 654 3210',
        'location': 'San Francisco, CA',
        'assigned_to': 'Alex Johnson',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Alex',
        'probability': 70,
        'stage': 'prospect',
        'company_name': 'Innovate Tech',
        'tags': ['Mobile', 'Startup'],
    },
    {
        'title': 'Cloud Migration',
        'code': 'CM',
        'value': 87500.00,
        'email': 'info@globalbank.com',
        'phone': '(555) 123 4567',
        'location': 'London, UK',
        'assigned_to': 'Michael Chen',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Michael',
        'probability': 95,
        'stage': 'proposal',
        'company_name': 'Global Bank',
        'tags': ['Enterprise', 'Cloud'],
    },
    {
        'title': 'E-commerce Platform',
        'code': 'EC',
        'value': 42500.00,
        'email': 'sales@retailco.com',
        'phone': '(321) 987 6543',
        'location': 'Chicago, IL',
        'assigned_to': 'Sarah Wilson',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah',
        'probability': 60,
        'stage': 'new',
        'company_name': 'RetailCo',
        'tags': ['E-commerce', 'Mid-Market'],
    },
    {
        'title': 'CRM Implementation',
        'code': 'CRM',
        'value': 28500.00,
        'email': 'ceo@startup.io',
        'phone': '(444) 555 6666',
        'location': 'Austin, TX',
        'assigned_to': 'David Lee',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=David',
        'probability': 40,
        'stage': 'prospect',
        'company_name': 'Startup.io',
        'tags': ['SaaS', 'CRM'],
    },
    {
        'title': 'Data Analytics Suite',
        'code': 'DA',
        'value': 67500.00,
        'email': 'contact@datacorp.com',
        'phone': '(777) 888 9999',
        'location': 'Boston, MA',
        'assigned_to': 'Emma Garcia',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Emma',
        'probability': 90,
        'stage': 'won',
        'company_name': 'DataCorp',
        'tags': ['Analytics', 'Enterprise'],
    },
    {
        'title': 'AI Chatbot Integration',
        'code': 'AI',
        'value': 18500.00,
        'email': 'hello@techstart.com',
        'phone': '(222) 333 4444',
        'location': 'Seattle, WA',
        'assigned_to': 'Robert Kim',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Robert',
        'probability': 75,
        'stage': 'proposal',
        'company_name': 'TechStart',
        'tags': ['AI', 'Startup'],
    },
    {
        'title': 'Cybersecurity Audit',
        'code': 'CS',
        'value': 52500.00,
        'email': 'security@finance.com',
        'phone': '(666) 777 8888',
        'location': 'Toronto, Canada',
        'assigned_to': 'Lisa Wong',
        'assignee_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Lisa',
        'probability': 55,
        'stage': 'new',
        'company_name': 'SecureFinance',
        'tags': ['Security', 'Enterprise'],
    },
]


class Command(BaseCommand):
    help = 'Seed the deals table with sample data'

    def handle(self, *args, **options):
        Deal.objects.all().delete()
        self.stdout.write('Cleared existing deals.')

        for data in SAMPLE_DEALS:
            Deal.objects.create(**data)

        self.stdout.write(self.style.SUCCESS(
            f'✅  Seeded {len(SAMPLE_DEALS)} deals successfully.'
        ))
