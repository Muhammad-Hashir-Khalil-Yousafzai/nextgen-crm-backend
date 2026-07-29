# usermanage/services.py
"""
All usermanage business logic.
Views stay thin — they call services only.
"""
from django.db import transaction
from django.contrib.auth.models import User as AuthUser
from django.utils import timezone
from .models import UserProfile, Department, UserSession, UserActivityLog


# ──────────────────────────────────────────────
# USER SERVICES
# ──────────────────────────────────────────────

def get_user_list(filters: dict = None):
    """
    Return filtered UserProfile queryset for table/grid.
    filters: {search, dept, status, role}
    """
    qs = UserProfile.objects.select_related(
        'user', 'department'
    ).prefetch_related(
        'user__user_roles__role',
        'user__mfa',
    )

    if not filters:
        return qs

    if filters.get('search'):
        s  = filters['search'].strip()
        qs = qs.filter(full_name__icontains=s) | \
             qs.filter(user__email__icontains=s) | \
             qs.filter(city__icontains=s)

    if filters.get('dept') and filters['dept'] != 'all':
        qs = qs.filter(department__slug=filters['dept'])

    if filters.get('status') and filters['status'] != 'all':
        qs = qs.filter(status=filters['status'])

    if filters.get('role') and filters['role'] != 'all':
        qs = qs.filter(
            user__user_roles__role__slug=filters['role'],
            user__user_roles__is_active=True,
        )

    return qs.distinct()


def get_profile_by_id(profile_id: int) -> UserProfile:
    try:
        return UserProfile.objects.select_related(
            'user', 'department'
        ).prefetch_related(
            'user__user_roles__role',
            'user__mfa',
            'user__sessions',
        ).get(pk=profile_id)
    except UserProfile.DoesNotExist:
        return None


@transaction.atomic
def create_user(data: dict, actor=None):
    from django.contrib.auth import get_user_model
    from crmapp.system.roles.models import UserRole
    from crmapp.system.roles.permissions import invalidate_perm_cache

    User = get_user_model()

    email     = str(data.get('email', '')).strip().lower()
    password  = data.get('password', '')
    full_name = data.get('full_name', '')
    phone     = data.get('phone', '')
    city      = data.get('city', '')
    status    = data.get('status', 'active')
    dept      = data.get('department_id')   # Department object or None
    role_obj  = data.get('role_id')         # Role object or None

    # Check duplicate email
    if User.objects.filter(email__iexact=email).exists():
        from rest_framework.exceptions import ValidationError
        raise ValidationError({'email': f'A user with email "{email}" already exists.'})

    # Create auth user
    user = User.objects.create_user(
    username=email,
    email=email,
    password=password,
    is_active=True,   # ← add this
)

    # Create UserProfile — use get_or_create to avoid duplicate key
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'full_name': full_name,
            'phone':     phone,
            'city':      city,
            'status':    status,
            'department': dept,
        }
    )

    # If profile already existed (orphan), update it
    if not created:
        profile.full_name  = full_name
        profile.phone      = phone
        profile.city       = city
        profile.status     = status
        profile.department = dept
        profile.save()

    # Assign role
    if role_obj:
        UserRole.objects.get_or_create(
            user=user,
            role=role_obj,
            defaults={
                'assigned_by': actor,
                'is_active':   True,
            }
        )
        invalidate_perm_cache(user)

    return profile

@transaction.atomic
def update_user_status(profile: UserProfile, new_status: str, actor=None) -> UserProfile:
    """Change user status. Kills sessions on suspend/delete."""
    old_status    = profile.status
    profile.status = new_status
    profile.save()

    if new_status in ('suspended', 'deleted'):
        terminate_all_sessions(profile.user)

    action = {'suspended': 'suspend', 'active': 'activate',
               'deleted': 'delete', 'inactive': 'update'}.get(new_status, 'update')
    _log(actor, profile.user, action, f'Status: {old_status} → {new_status}')
    return profile


@transaction.atomic
def update_user_profile(profile: UserProfile, data: dict, actor=None) -> UserProfile:
    """PATCH profile fields."""
    for field in ('full_name', 'phone', 'city', 'status'):
        if field in data:
            setattr(profile, field, data[field])
    if 'department' in data:
        profile.department = data['department']
    profile.save()
    _log(actor, profile.user, 'update', f'Profile updated: {profile.full_name}')
    return profile


@transaction.atomic
def reset_password(profile: UserProfile, new_password: str, actor=None):
    """Force-reset password + kill all sessions."""
    profile.user.set_password(new_password)
    profile.user.save(update_fields=['password'])
    terminate_all_sessions(profile.user)
    _log(actor, profile.user, 'password', f'Password reset: {profile.user.email}')


@transaction.atomic
def bulk_update_status(profile_ids: list, new_status: str, actor=None) -> int:
    """Bulk status change from user IDs."""
    profiles = UserProfile.objects.filter(pk__in=profile_ids)
    count    = profiles.update(status=new_status)
    if new_status in ('suspended', 'deleted'):
        user_ids = profiles.values_list('user_id', flat=True)
        UserSession.objects.filter(user_id__in=user_ids, is_active=True).update(is_active=False)
        AuthUser.objects.filter(pk__in=user_ids).update(is_active=False)
    _log(actor, None, 'update', f'Bulk {new_status}: {count} users')
    return count


def bulk_import_users(rows: list, actor=None) -> dict:
    """Import users from CSV rows: {full_name, email, phone, department (slug)}"""
    created = 0
    skipped = 0
    errors  = []
    for i, row in enumerate(rows, 1):
        email = row.get('email', '').strip().lower()
        if not email or AuthUser.objects.filter(email=email).exists():
            skipped += 1
            continue
        try:
            import secrets
            dept = Department.objects.filter(slug=row.get('department', '')).first()
            create_user({
                'full_name': row.get('full_name', ''),
                'email':     email,
                'password':  secrets.token_urlsafe(12),
                'phone':     row.get('phone', ''),
                'department_id': dept,
            }, actor=actor)
            created += 1
        except Exception as e:
            errors.append({'row': i, 'email': email, 'error': str(e)})
    _log(actor, None, 'import', f'Import: {created} created, {skipped} skipped, {len(errors)} errors')
    return {'created': created, 'skipped': skipped, 'errors': errors}


# ──────────────────────────────────────────────
# DEPARTMENT SERVICES
# ──────────────────────────────────────────────

def get_departments_with_stats():
    from django.db.models import Count, Q
    return Department.objects.annotate(
        active_count=Count('users', filter=Q(users__status='active')),
        total_count=Count('users'),
    ).select_related('head', 'head__profile')


# ──────────────────────────────────────────────
# SESSION SERVICES
# ──────────────────────────────────────────────

def get_active_sessions():
    return UserSession.objects.filter(is_active=True).select_related(
        'user', 'user__profile', 'user__profile__department'
    ).order_by('-last_activity')


def create_session(user, ip_address, device_info, city, session_key, expires_at=None):
    return UserSession.objects.create(
        user=user, ip_address=ip_address,
        device_info=device_info, city=city,
        session_key=session_key, expires_at=expires_at,
        is_active=True,
    )


def terminate_session(session: UserSession, actor=None):
    session.is_active = False
    session.save(update_fields=['is_active'])


def terminate_all_sessions(user):
    UserSession.objects.filter(user=user, is_active=True).update(is_active=False)


def expire_old_sessions():
    expired = UserSession.objects.filter(
        is_active=True, expires_at__lt=timezone.now()
    ).update(is_active=False)
    return expired


# ──────────────────────────────────────────────
# ACTIVITY LOG SERVICES
# ──────────────────────────────────────────────

def get_activity_logs(filters: dict = None):
    qs = UserActivityLog.objects.select_related(
        'actor', 'actor__profile', 'target_user', 'target_user__profile'
    ).order_by('-timestamp')
    if filters:
        if filters.get('action'):
            qs = qs.filter(action=filters['action'])
        if filters.get('actor_id'):
            qs = qs.filter(actor_id=filters['actor_id'])
    return qs


# ── Internal helper ──
def _log(actor, target_user, action, description):
    UserActivityLog.objects.create(
        actor=actor,
        target_user=target_user,
        action=action,
        description=description,
    )