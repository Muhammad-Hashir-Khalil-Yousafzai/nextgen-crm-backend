# roles/permissions.py
from rest_framework.permissions import BasePermission
from django.core.cache import cache


def _full_access_perms(ACTION_CHOICES, MODULE_CHOICES):
    """Returns all modules with all actions set to True."""
    full = {a: True for a, _ in ACTION_CHOICES}
    return {m: dict(full) for m, _ in MODULE_CHOICES}


def _is_super(user) -> bool:
    """
    Returns True if the user should be treated as a super admin.
    Covers every possible pattern your backend might use.
    """
    if not user or not user.is_authenticated:
        return False

    # Pattern 1: Django built-in flags
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'is_staff', False):
        return True

    # Pattern 2: check via fresh DB lookup (bypasses any stale object state)
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        fresh = User.objects.values('is_superuser', 'is_staff').get(pk=user.pk)
        if fresh['is_superuser'] or fresh['is_staff']:
            return True
    except Exception:
        pass

    # Pattern 3: user has a role slug of "superadmin"
    try:
        from .models import UserRole
        roles = UserRole.objects.filter(
            user=user, is_active=True
        ).values_list('role__slug', flat=True)
        normalized = [r.lower().replace('_', '').replace(' ', '') for r in roles]
        if 'superadmin' in normalized or 'admin' in normalized:
            return True
    except Exception:
        pass

    return False


def get_user_permissions(user) -> dict:
    """
    Returns {module: {action: bool}} for an auth_user.
    Sources: UserRole + TemporaryAccess (union — any role granting = True).
    Cached per user for 5 minutes.

    Super Admin / Staff users get ALL permissions set to True automatically,
    without needing any roles assigned.
    """
    from .models import UserRole, TemporaryAccess, MODULE_CHOICES, ACTION_CHOICES
    import datetime

    # ── Super Admin / Staff → full access immediately ───────────────────────
    if _is_super(user):
        return _full_access_perms(ACTION_CHOICES, MODULE_CHOICES)

    # ── Regular user: check cache first ─────────────────────────────────────
    cache_key = f'user_perms_{user.pk}'
    cached    = cache.get(cache_key)
    if cached is not None:
        return cached

    # Init all False
    perms = {
        m: {a: False for a, _ in ACTION_CHOICES}
        for m, _ in MODULE_CHOICES
    }

    # From permanent roles
    role_ids = UserRole.objects.filter(
        user=user, is_active=True
    ).values_list('role_id', flat=True)
    _apply(perms, role_ids)

    # From temporary access
    today         = datetime.date.today()
    temp_role_ids = TemporaryAccess.objects.filter(
        user=user, is_active=True, expires_at__gte=today
    ).values_list('role_id', flat=True)
    _apply(perms, temp_role_ids)

    cache.set(cache_key, perms, timeout=300)
    return perms


def _apply(perms: dict, role_ids):
    from .models import RolePermission
    for rp in RolePermission.objects.filter(
        role_id__in=role_ids, granted=True
    ).select_related('permission'):
        m = rp.permission.module
        a = rp.permission.action
        if m in perms:
            perms[m][a] = True


def invalidate_perm_cache(user):
    cache.delete(f'user_perms_{user.pk}')


class HasModulePermission(BasePermission):
    module  = None
    action  = 'view'
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if _is_super(request.user):
            return True
        perms = get_user_permissions(request.user)
        return perms.get(self.module, {}).get(self.action, False)


def can(module: str, action: str) -> type:
    """
    Factory — returns a DRF permission class.
    Usage: permission_classes = [can('crm', 'edit')]
    """
    return type(
        f'Can_{module}_{action}',
        (HasModulePermission,),
        {'module': module, 'action': action}
    )