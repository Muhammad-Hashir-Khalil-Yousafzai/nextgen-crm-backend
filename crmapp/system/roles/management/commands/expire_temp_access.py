# roles/management/commands/expire_temp_access.py
from django.core.management.base import BaseCommand
from crmapp.system.roles.services import expire_temp_access


class Command(BaseCommand):
    help = 'Expire temporary access grants past their expiry date'

    def handle(self, *args, **options):
        count = expire_temp_access()
        self.stdout.write(self.style.SUCCESS(f'Expired {count} temporary access grants.'))