from django.core.management.base import BaseCommand
from crmapp.crm.contact.models import Contact


class Command(BaseCommand):
    help = 'Seed contacts with sample data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding contacts...')

        contacts_data = [
            {
                "name": "Darlee Robertson", "title": "Facility Manager",
                "email": "darlee@example.com", "phone": "(163) 2459 315",
                "location": "Germany", "rating": 4.2, "company": "Tech Solutions Inc",
                "status": "active", "tags": ["VIP", "Manager"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Darlee",
                "last_contact": "2024-01-28"
            },
            {
                "name": "Sharon Roy", "title": "Installer",
                "email": "sharon@example.com", "phone": "(146) 1249 296",
                "location": "USA", "rating": 5.0, "company": "BuildRight Co",
                "status": "active", "tags": ["Technical"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Sharon",
                "last_contact": "2024-02-01"
            },
            {
                "name": "Vaughan Lewis", "title": "Senior Manager",
                "email": "vaughan@example.com", "phone": "(135) 3489 516",
                "location": "Canada", "rating": 3.5, "company": "Global Enterprises",
                "status": "active", "tags": ["Manager", "VIP"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Vaughan",
                "last_contact": "2024-01-25"
            },
            {
                "name": "Jessica Louise", "title": "Test Engineer",
                "email": "jessica@example.com", "phone": "(158) 3459 596",
                "location": "India", "rating": 4.5, "company": "QA Masters",
                "status": "active", "tags": ["Technical"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Jessica",
                "last_contact": "2024-02-02"
            },
            {
                "name": "Carol Thomas", "title": "UI/UX Designer",
                "email": "carol@example.com", "phone": "(196) 4862 196",
                "location": "China", "rating": 3.5, "company": "Design Studio",
                "status": "inactive", "tags": ["Design"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Carol",
                "last_contact": "2024-01-15"
            },
            {
                "name": "Dawn Mercha", "title": "UI/UX Designer",
                "email": "dawn@example.com", "phone": "(163) 6498 256",
                "location": "Japan", "rating": 3.5, "company": "Creative Labs",
                "status": "active", "tags": ["Design"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Dawn",
                "last_contact": "2024-01-30"
            },
            {
                "name": "Rachel Hampton", "title": "Software Developer",
                "email": "rachel@example.com", "phone": "(154) 6481 075",
                "location": "Indonesia", "rating": 3.1, "company": "DevCorp",
                "status": "active", "tags": ["Technical", "Developer"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Rachel",
                "last_contact": "2024-01-22"
            },
            {
                "name": "Jonelle Curtiss", "title": "Supervisor",
                "email": "jonella@example.com", "phone": "(184) 6348 195",
                "location": "Cuba", "rating": 5.0, "company": "Operations Plus",
                "status": "active", "tags": ["Manager"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Jonelle",
                "last_contact": "2024-02-01"
            },
            {
                "name": "Marcus Chen", "title": "Product Manager",
                "email": "marcus@example.com", "phone": "(192) 5567 234",
                "location": "USA", "rating": 4.8, "company": "Product Inc",
                "status": "active", "tags": ["Manager", "Product"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Marcus",
                "last_contact": "2024-01-29"
            },
            {
                "name": "Sophia Martinez", "title": "Data Analyst",
                "email": "sophia@example.com", "phone": "(175) 3421 098",
                "location": "Germany", "rating": 4.3, "company": "Analytics Pro",
                "status": "active", "tags": ["Technical", "Analytics"],
                "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=Sophia",
                "last_contact": "2024-01-27"
            },
        ]

        for data in contacts_data:
            Contact.objects.update_or_create(
                email=data['email'],
                defaults=data
            )

        self.stdout.write(
            self.style.SUCCESS(f'  Created {len(contacts_data)} contacts')
        )
