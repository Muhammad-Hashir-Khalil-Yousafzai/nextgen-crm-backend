"""
Management command: seed_activities

Creates sample Activity records that match the dummy data used
in the ActivityList.jsx frontend component.

Usage:
    python manage.py seed_activities
    python manage.py seed_activities --clear   # wipe first
"""

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from crmapp.crm.activities.models import Activity


SEED_DATA = [
    {
        'title':         'We scheduled a meeting for next week',
        'activity_type': 'Meeting',
        'due_date':      '2024-01-16',
        'owner':         'Hendry Milner',
    },
    {
        'title':         'Had conversation with Fred regarding task',
        'activity_type': 'Calls',
        'due_date':      '2024-01-24',
        'owner':         'Gullory Berggren',
    },
    {
        'title':         'Analysing latest time estimation for new project',
        'activity_type': 'Tasks',
        'due_date':      '2024-02-23',
        'owner':         'Jami Carlile',
    },
    {
        'title':         'Store and manage contact data',
        'activity_type': 'Email',
        'due_date':      '2024-03-18',
        'owner':         'Theresa Nelson',
    },
    {
        'title':         'Call John and discuss about project',
        'activity_type': 'Calls',
        'due_date':      '2024-04-14',
        'owner':         'Smith Cooper',
    },
    {
        'title':         'Will have a meeting before project start',
        'activity_type': 'Meeting',
        'due_date':      '2024-04-22',
        'owner':         'Martin Lewis',
    },
    {
        'title':         'Built landing pages',
        'activity_type': 'Email',
        'due_date':      '2024-07-08',
        'owner':         'Newell Egan',
    },
    {
        'title':         'Discussed budget proposal with Edwin',
        'activity_type': 'Calls',
        'due_date':      '2024-09-05',
        'owner':         'Janet Carlson',
    },
    {
        'title':         'Attach final proposal for upcoming project',
        'activity_type': 'Tasks',
        'due_date':      '2024-11-18',
        'owner':         'Craig Byrne',
    },
    {
        'title':         'Review quarterly performance metrics',
        'activity_type': 'Meeting',
        'due_date':      '2024-12-10',
        'owner':         'Sarah Johnson',
    },
]


class Command(BaseCommand):
    help = 'Seed the activities table with sample data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing activities before seeding.',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted, _ = Activity.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} activities.'))

        created = 0
        for item in SEED_DATA:
            Activity.objects.get_or_create(
                title=item['title'],
                owner=item['owner'],
                defaults={
                    'activity_type': item['activity_type'],
                    'due_date':      parse_date(item['due_date']),
                }
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f'Seeded {created} activities successfully.')
        )
