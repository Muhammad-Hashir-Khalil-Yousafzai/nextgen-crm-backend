from django.core.management.base import BaseCommand
from crmapp.crm.companies.models import Company


class Command(BaseCommand):
    help = 'Seed companies with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding companies...')

        data = [
            {
                'name': 'Global Bank', 'code': 'GB', 'industry': 'Finance',
                'type': 'client', 'health': 'healthy',
                'website': 'https://globalbank.com', 'email': 'info@globalbank.com',
                'phone': '(555) 123 4567', 'headquarters': 'London, UK',
                'branches': ['New York', 'Tokyo', 'Dubai'],
                'number_of_employees': 12500, 'annual_revenue': 4200000000,
                'total_revenue': 87500,
                'account_owner': 'Michael Chen',
                'account_owner_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Michael',
                'social_links': {'linkedin': '#', 'twitter': '#'},
                'tags': ['Enterprise', 'VIP', 'Cloud'],
                'notes': 'Strategic global banking partner.',
                'rating': 5, 'last_contact': '2024-01-18',
            },
            {
                'name': 'TechCorp Inc', 'code': 'TC', 'industry': 'Technology',
                'type': 'client', 'health': 'healthy',
                'website': 'https://techcorp.io', 'email': 'darlee@gmail.com',
                'phone': '(163) 2459 315', 'headquarters': 'New York, USA',
                'branches': ['Austin', 'San Francisco'],
                'number_of_employees': 3200, 'annual_revenue': 580000000,
                'total_revenue': 54500,
                'account_owner': 'Sharon Roy',
                'account_owner_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Sharon',
                'social_links': {'linkedin': '#', 'twitter': '#', 'facebook': '#'},
                'tags': ['VIP', 'Enterprise'],
                'notes': 'Website redesign project underway.',
                'rating': 4, 'last_contact': '2024-01-10',
            },
            {
                'name': 'Innovate Tech', 'code': 'IT', 'industry': 'Technology',
                'type': 'prospect', 'health': 'at-risk',
                'website': 'https://innovate.com', 'email': 'client@innovate.com',
                'phone': '(987) 654 3210', 'headquarters': 'San Francisco, CA',
                'branches': [],
                'number_of_employees': 420, 'annual_revenue': 45000000,
                'total_revenue': 32500,
                'account_owner': 'Alex Johnson',
                'account_owner_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Alex',
                'social_links': {'linkedin': '#'},
                'tags': ['Mobile', 'Startup'],
                'notes': 'Mobile app development prospect.',
                'rating': 3, 'last_contact': '2024-01-15',
            },
            {
                'name': 'RetailCo', 'code': 'RC', 'industry': 'Retail',
                'type': 'client', 'health': 'healthy',
                'website': 'https://retailco.com', 'email': 'sales@retailco.com',
                'phone': '(321) 987 6543', 'headquarters': 'Chicago, IL',
                'branches': ['Dallas', 'Miami'],
                'number_of_employees': 1800, 'annual_revenue': 320000000,
                'total_revenue': 42500,
                'account_owner': 'Sarah Wilson',
                'account_owner_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah',
                'social_links': {'linkedin': '#', 'facebook': '#'},
                'tags': ['E-commerce', 'Mid-Market'],
                'notes': 'E-commerce platform deal in proposal stage.',
                'rating': 4, 'last_contact': '2024-01-08',
            },
            {
                'name': 'DataCorp', 'code': 'DC', 'industry': 'Technology',
                'type': 'client', 'health': 'healthy',
                'website': 'https://datacorp.com', 'email': 'contact@datacorp.com',
                'phone': '(777) 888 9999', 'headquarters': 'Boston, MA',
                'branches': ['Seattle', 'Denver'],
                'number_of_employees': 2100, 'annual_revenue': 410000000,
                'total_revenue': 67500,
                'account_owner': 'Emma Garcia',
                'account_owner_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=Emma',
                'social_links': {'linkedin': '#', 'twitter': '#'},
                'tags': ['Analytics', 'Enterprise'],
                'notes': 'Won data analytics suite.',
                'rating': 5, 'last_contact': '2024-01-18',
            },
        ]

        for d in data:
            Company.objects.update_or_create(name=d['name'], defaults=d)

        self.stdout.write(self.style.SUCCESS(f'  Created {len(data)} companies ✅'))
