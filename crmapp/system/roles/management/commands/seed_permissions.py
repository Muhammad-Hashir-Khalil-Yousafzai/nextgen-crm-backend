# roles/management/commands/seed_permissions.py
from django.core.management.base import BaseCommand
from crmapp.system.roles.models import Permission, Role, RolePermission
from crmapp.system.roles.services import seed_all_permissions

ROLES_META = [
    {'slug': 'super_admin',     'name': 'Super Admin',     'level': 1, 'is_system': True,  'color_hex': '#E74C3C'},
    {'slug': 'admin',           'name': 'Admin',            'level': 2, 'is_system': True,  'color_hex': '#8E44AD'},
    {'slug': 'hr_manager',      'name': 'HR Manager',       'level': 3, 'is_system': False, 'color_hex': '#3498DB'},
    {'slug': 'sales_manager',   'name': 'Sales Manager',    'level': 3, 'is_system': False, 'color_hex': '#27AE60'},
    {'slug': 'finance_officer', 'name': 'Finance Officer',  'level': 3, 'is_system': False, 'color_hex': '#F39C12'},
    {'slug': 'employee',        'name': 'Employee',         'level': 5, 'is_system': False, 'color_hex': '#95A5A6'},
]

ROLE_PERM_MAP = {
    'super_admin':     {m: ['view','create','edit','delete','approve','export','import']
                        for m in ['crm','hr','finance','marketing','analytics','ai','settings']},
    'admin':           {
        'crm':       ['view','create','edit','delete','approve','export','import'],
        'hr':        ['view','create','edit','approve','export','import'],
        'finance':   ['view','create','edit','approve','export','import'],
        'marketing': ['view','create','edit','approve','export','import'],
        'analytics': ['view','create','edit','export'],
        'ai':        ['view','create','edit'],
        'settings':  ['view','create','edit','approve'],
    },
    'hr_manager':      {
        'crm': ['view'], 'hr': ['view','create','edit','delete','approve','export','import'],
        'finance': [], 'marketing': [], 'analytics': ['view'], 'ai': [], 'settings': [],
    },
    'sales_manager':   {
        'crm': ['view','create','edit','approve','export','import'],
        'hr': ['view'], 'finance': [],
        'marketing': ['view','create','edit'],
        'analytics': ['view','export'], 'ai': ['view'], 'settings': [],
    },
    'finance_officer': {
        'crm': ['view'], 'hr': [],
        'finance': ['view','create','edit','approve','export','import'],
        'marketing': [], 'analytics': ['view','export'], 'ai': [], 'settings': [],
    },
    'employee': {
        'crm': ['view'], 'hr': ['view'],
        'finance': [], 'marketing': [], 'analytics': [], 'ai': [], 'settings': [],
    },
}

ALL_ACTIONS = ['view','create','edit','delete','approve','export','import']


class Command(BaseCommand):
    help = 'Seed all 49 permissions and 6 default roles'

    def handle(self, *args, **options):
        self.stdout.write('Seeding permissions...')
        count = seed_all_permissions()
        self.stdout.write(self.style.SUCCESS(f'  {count} new permission pairs created'))

        for meta in ROLES_META:
            role, created = Role.objects.get_or_create(slug=meta['slug'], defaults=meta)
            verb = 'Created' if created else 'Exists '
            self.stdout.write(f'  {verb}: {role.name}')
            granted_map = ROLE_PERM_MAP.get(role.slug, {})
            for module, actions in granted_map.items():
                for action in ALL_ACTIONS:
                    perm    = Permission.objects.get(module=module, action=action)
                    granted = action in actions
                    RolePermission.objects.update_or_create(
                        role=role, permission=perm, defaults={'granted': granted}
                    )

        self.stdout.write(self.style.SUCCESS('\n✓ Done. Run: python manage.py createsuperuser'))