# roles/services.py
import re
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Role, Permission, RolePermission, UserRole, TemporaryAccess, MODULE_CHOICES, ACTION_CHOICES
from .permissions import invalidate_perm_cache
from django.db import models as django_models

def get_all_roles(actor=None):
    qs = Role.objects.prefetch_related('permissions__permission').order_by('level', 'name')
    if actor:
        from django.db.models import Q
        return qs.filter(Q(created_by=actor) | Q(is_system=True))
    return qs


def get_role_permission_matrix(role: Role) -> dict:
    
    matrix = {m: {a: False for a, _ in ACTION_CHOICES} for m, _ in MODULE_CHOICES}
    for rp in role.permissions.filter(granted=True).select_related('permission'):
        m = rp.permission.module
        a = rp.permission.action
        if m in matrix:
            matrix[m][a] = True
    return matrix


def seed_all_permissions() -> int:
    created = 0
    for module, _ in MODULE_CHOICES:
        for action, _ in ACTION_CHOICES:
            _, was_created = Permission.objects.get_or_create(module=module, action=action)
            if was_created:
                created += 1
    return created


@transaction.atomic
def create_role(name, description='', color_hex='#3a9aab', level=5, actor=None) -> Role:
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    base = slug
    i    = 1
    while Role.objects.filter(slug=slug).exists():
        slug = f'{base}_{i}'; i += 1
    role = Role.objects.create(slug=slug, name=name, description=description,
                               color_hex=color_hex, level=level, is_system=False,
                               created_by=actor)
    _log(actor, 'create', f'Role created: {role.name}')
    return role


@transaction.atomic
def update_role_permissions(role: Role, perm_matrix: dict, actor=None):
    for module, _ in MODULE_CHOICES:
        for action, _ in ACTION_CHOICES:
            granted = bool(perm_matrix.get(module, {}).get(action, False))
            try:
                perm = Permission.objects.get(module=module, action=action)
            except Permission.DoesNotExist:
                continue
            RolePermission.objects.update_or_create(
                role=role, permission=perm, defaults={'granted': granted}
            )
    from django.contrib.auth.models import User as AuthUser
    user_ids = role.user_assignments.filter(is_active=True).values_list('user_id', flat=True)
    for u in AuthUser.objects.filter(pk__in=user_ids):
        invalidate_perm_cache(u)
    _log(actor, 'permission', f'Permissions updated for role: {role.name}')


@transaction.atomic
def clone_role(source: Role, actor=None) -> Role:
    new_role = create_role(
        name=f'{source.name} (Copy)', description=source.description,
        color_hex=source.color_hex, level=source.level, actor=actor
    )
    for rp in source.permissions.all():
        RolePermission.objects.create(role=new_role, permission=rp.permission, granted=rp.granted)
    return new_role


@transaction.atomic
def delete_role(role: Role, actor=None):
    if role.is_system:
        raise ValidationError('System roles cannot be deleted.')
    
    # No user check — CASCADE handles cleanup automatically
    name = role.name
    role.delete()
    _log(actor, 'delete', f'Role deleted: {name}')

@transaction.atomic
def assign_role_to_user(user, role_id, assigned_by=None) -> UserRole:
    role = Role.objects.get(pk=role_id)
    ur, _ = UserRole.objects.update_or_create(
        user=user, role=role,
        defaults={'assigned_by': assigned_by, 'is_active': True}
    )
    invalidate_perm_cache(user)
    _log(assigned_by, 'assign', f'Role "{role.name}" assigned to user {user.pk}')
    return ur


def revoke_role_from_user(user, role_id, actor=None):
    UserRole.objects.filter(user=user, role_id=role_id, is_active=True).update(is_active=False)
    invalidate_perm_cache(user)
    _log(actor, 'revoke', f'Role revoked from user {user.pk}')


@transaction.atomic
def grant_temporary_access(user, role_id, reason, expires_at, granted_by=None) -> TemporaryAccess:
    role = Role.objects.get(pk=role_id)
    ta   = TemporaryAccess.objects.create(
        user=user, role=role, reason=reason,
        expires_at=expires_at, granted_by=granted_by, is_active=True
    )
    invalidate_perm_cache(user)
    _log(granted_by, 'temp_grant', f'Temp "{role.name}" → user {user.pk} until {expires_at}')
    return ta


def revoke_temporary_access(ta: TemporaryAccess, actor=None):
    ta.is_active = False
    ta.save(update_fields=['is_active'])
    invalidate_perm_cache(ta.user)


def expire_temp_access() -> int:
    import datetime
    from django.contrib.auth.models import User as AuthUser
    expired  = TemporaryAccess.objects.filter(is_active=True, expires_at__lt=datetime.date.today())
    user_ids = list(expired.values_list('user_id', flat=True))
    count    = expired.update(is_active=False)
    for u in AuthUser.objects.filter(pk__in=user_ids):
        invalidate_perm_cache(u)
    return count


def _log(actor, action, description):
    try:
        from audit.services import log_event
        log_event(user=actor, action='permission', module='Settings',
                  entity=description, severity='medium')
    except Exception:
        pass