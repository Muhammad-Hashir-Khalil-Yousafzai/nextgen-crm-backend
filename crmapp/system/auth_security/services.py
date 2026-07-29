# auth_security/services.py
import hashlib
import secrets
import datetime
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.contrib.auth.models import User as AuthUser
from .models import LoginLog, MFAUser, APIToken, SSOProvider, SecurityPolicy, BlockedIP


# ──────────────────────────────────────────────
# LOGIN SERVICES
# ──────────────────────────────────────────────

def record_login_attempt(email: str, status: str, ip_address: str,
                         device_info: str = '', city: str = '',
                         user=None, mfa_used: bool = False) -> LoginLog:
    """Called after every login attempt — success or fail."""
    log = LoginLog.objects.create(
        user=user,
        email_attempted=email,
        status=status,
        ip_address=ip_address,
        device_info=device_info,
        city=city,
        mfa_used=mfa_used,
    )
    if status == 'failed':
        _increment_failed_attempts(email)
    elif status == 'success':
        _clear_failed_attempts(email)
    return log


def is_ip_blocked(ip_address: str) -> bool:
    return BlockedIP.objects.filter(ip_address=ip_address, is_active=True).exists()


def is_account_locked(email: str) -> bool:
    policy = SecurityPolicy.get()
    count  = cache.get(f'login_attempts_{email}', 0)
    return count >= policy.max_attempts


def _increment_failed_attempts(email: str):
    policy  = SecurityPolicy.get()
    timeout = policy.lockout_duration * 60
    key     = f'login_attempts_{email}'
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)


def _clear_failed_attempts(email: str):
    cache.delete(f'login_attempts_{email}')


def get_login_logs(filters: dict = None):
    qs = LoginLog.objects.select_related('user', 'user__profile').order_by('-timestamp')
    if not filters:
        return qs
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])
    if filters.get('user_id'):
        qs = qs.filter(user_id=filters['user_id'])
    if filters.get('date_from'):
        qs = qs.filter(timestamp__date__gte=filters['date_from'])
    if filters.get('date_to'):
        qs = qs.filter(timestamp__date__lte=filters['date_to'])
    return qs


# ──────────────────────────────────────────────
# MFA SERVICES
# ──────────────────────────────────────────────

def get_or_create_mfa(user) -> MFAUser:
    mfa, _ = MFAUser.objects.get_or_create(user=user)
    return mfa


def toggle_mfa_for_user(user, actor=None) -> bool:
    mfa             = get_or_create_mfa(user)
    mfa.mfa_enabled = not mfa.mfa_enabled
    mfa.save(update_fields=['mfa_enabled'])
    _log_auth(actor or user, f'MFA {"enabled" if mfa.mfa_enabled else "disabled"} for {user.email}')
    return mfa.mfa_enabled


def enable_mfa(user, method: str, totp_secret: str = '', actor=None) -> MFAUser:
    mfa             = get_or_create_mfa(user)
    mfa.mfa_enabled = True
    mfa.method      = method
    if totp_secret:
        mfa.totp_secret = totp_secret
    mfa.backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    mfa.save()
    _log_auth(actor or user, f'MFA enabled ({method}) for {user.email}')
    return mfa


def disable_mfa(user, actor=None) -> MFAUser:
    mfa              = get_or_create_mfa(user)
    mfa.mfa_enabled  = False
    mfa.totp_secret  = ''
    mfa.backup_codes = []
    mfa.save()
    _log_auth(actor or user, f'MFA disabled for {user.email}')
    return mfa


def regenerate_backup_codes(user) -> list:
    mfa              = get_or_create_mfa(user)
    mfa.backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    mfa.save(update_fields=['backup_codes'])
    return mfa.backup_codes


def verify_backup_code(user, code: str) -> bool:
    mfa = get_or_create_mfa(user)
    if code in mfa.backup_codes:
        mfa.backup_codes.remove(code)
        mfa.last_verified = timezone.now()
        mfa.save(update_fields=['backup_codes', 'last_verified'])
        return True
    return False


def get_all_mfa_users():
    return MFAUser.objects.select_related(
        'user', 'user__profile', 'user__profile__department'
    ).prefetch_related('user__user_roles__role')


# ──────────────────────────────────────────────
# API TOKEN SERVICES
# ──────────────────────────────────────────────

def generate_api_token(name: str, scopes: list,
                       expires_at, created_by=None) -> tuple:
    """Returns (APIToken, raw_token). Show raw token ONCE only."""
    raw_token    = f'nxt_live_{secrets.token_urlsafe(32)}'
    token_hash   = hashlib.sha256(raw_token.encode()).hexdigest()
    token_prefix = raw_token[:16] + '••••••' + raw_token[-4:]

    token = APIToken.objects.create(
        name=name, token_hash=token_hash,
        token_prefix=token_prefix, scopes=scopes,
        expires_at=expires_at, created_by=created_by, status='active',
    )
    _log_auth(created_by, f'API token created: {name}')
    return token, raw_token


def revoke_api_token(token: APIToken, actor=None):
    token.status = 'revoked'
    token.save(update_fields=['status'])
    _log_auth(actor, f'API token revoked: {token.name}')


def get_api_tokens(filters: dict = None):
    qs = APIToken.objects.select_related('created_by', 'created_by__profile').order_by('-created_at')
    if filters and filters.get('status'):
        qs = qs.filter(status=filters['status'])
    return qs


def expire_api_tokens() -> int:
    return APIToken.objects.filter(
        status='active', expires_at__lt=datetime.date.today()
    ).update(status='revoked')


# ──────────────────────────────────────────────
# SSO SERVICES
# ──────────────────────────────────────────────

def get_sso_providers():
    return SSOProvider.objects.all().order_by('name')


@transaction.atomic
def create_sso_provider(data: dict, actor=None) -> SSOProvider:
    provider = SSOProvider.objects.create(**data)
    _log_auth(actor, f'SSO provider added: {provider.name}')
    return provider


def toggle_sso_provider(provider: SSOProvider, actor=None) -> SSOProvider:
    provider.is_enabled = not provider.is_enabled
    provider.save(update_fields=['is_enabled'])
    state = 'enabled' if provider.is_enabled else 'disabled'
    _log_auth(actor, f'SSO provider {state}: {provider.name}')
    return provider


# ──────────────────────────────────────────────
# SECURITY POLICY SERVICES
# ──────────────────────────────────────────────

def get_security_policy() -> SecurityPolicy:
    return SecurityPolicy.get()


def update_security_policy(data: dict, actor=None) -> SecurityPolicy:
    policy   = SecurityPolicy.get()
    old_data = {k: getattr(policy, k) for k in data if hasattr(policy, k)}
    for k, v in data.items():
        if hasattr(policy, k):
            setattr(policy, k, v)
    policy.save()
    _log_auth(actor, 'Security policy updated', before=old_data, after=data)
    return policy


# ──────────────────────────────────────────────
# BLOCKED IP SERVICES
# ──────────────────────────────────────────────

def get_blocked_ips():
    return BlockedIP.objects.filter(is_active=True).select_related(
        'blocked_by', 'blocked_by__profile'
    ).order_by('-blocked_at')


def block_ip(ip_address: str, reason: str, city: str = '', actor=None) -> BlockedIP:
    blocked, _ = BlockedIP.objects.update_or_create(
        ip_address=ip_address,
        defaults={'reason': reason, 'city': city,
                  'blocked_by': actor, 'is_active': True}
    )
    _log_auth(actor, f'IP blocked: {ip_address} — {reason}')
    return blocked


def unblock_ip(blocked: BlockedIP, actor=None):
    blocked.is_active = False
    blocked.save(update_fields=['is_active'])
    _log_auth(actor, f'IP unblocked: {blocked.ip_address}')


# ──────────────────────────────────────────────
# INTERNAL AUDIT HELPER
# ──────────────────────────────────────────────

def _log_auth(actor, description: str, before=None, after=None):
    try:
        from audit.services import log_event
        log_event(
            user=actor, action='security', module='Auth',
            entity=description, before_data=before,
            after_data=after, severity='medium',
        )
    except Exception:
        pass