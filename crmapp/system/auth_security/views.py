# auth_security/views.py
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from crmapp.system.auth_security.models import LoginLog, MFAUser, APIToken, SSOProvider, SecurityPolicy, BlockedIP
from .serializers import (
    LoginLogSerializer, MFAUserSerializer, APITokenSerializer,
    SSOProviderSerializer, SecurityPolicySerializer, BlockedIPSerializer,
)
from . import services
from crmapp.system.roles.permissions import can


# ──────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────

def _get_client_ip(request) -> str:
    """
    Return the real client IP.
    Trusts X-Forwarded-For only when set (reverse-proxy / load-balancer env).
    """
    x_fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_fwd:
        return x_fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _get_primary_role(is_superuser: bool, is_staff: bool, roles: list) -> str:
    """
    Returns the highest-priority role slug for frontend permission checks.
    """
    if is_superuser:
        return 'superadmin'
    if is_staff:
        return 'admin'
    return roles[0] if roles else 'employee'


# ──────────────────────────────────────────────
# LOGIN / LOGOUT
# ──────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/system/auth/login/
    """
    import datetime
    from django.contrib.auth import authenticate
    from django.db.models import F
    from rest_framework_simplejwt.tokens import RefreshToken
    from django.contrib.auth.models import User

    from crmapp.system.usermanage.services import create_session
    from crmapp.system.usermanage.models import UserProfile, UserSession, UserActivityLog
    from crmapp.system.roles.permissions import get_user_permissions

    email    = request.data.get('email', '').lower().strip()
    password = request.data.get('password', '')
    ip       = _get_client_ip(request)
    device   = request.META.get('HTTP_USER_AGENT', '')[:200]
    city     = request.data.get('city', '')

    # ── 1. IP blocked? ──
    if services.is_ip_blocked(ip):
        services.record_login_attempt(email, 'failed', ip, device, city)
        return Response(
            {'detail': 'Access denied from your IP address.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ── 2. Account locked? ──
    if services.is_account_locked(email):
        services.record_login_attempt(email, 'locked', ip, device, city)
        return Response(
            {'detail': 'Account temporarily locked. Try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # ── 3. Find user by email FIRST ──
    try:
        user_obj = User.objects.get(email=email)
        user     = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            services.record_login_attempt(email, 'failed', ip, device, city)
            return Response(
                {'detail': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    except User.DoesNotExist:
        services.record_login_attempt(email, 'failed', ip, device, city)
        return Response(
            {'detail': 'Invalid email or password.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # ── 3a. Check CRM profile status ──
    profile = getattr(user, 'profile', None)
    if profile and profile.status in ('suspended', 'deleted'):
        return Response(
            {'detail': 'Your account has been suspended.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ── 4. MFA check ──
    mfa      = getattr(user, 'mfa', None)
    mfa_used = False
    if mfa and mfa.mfa_enabled:
        mfa_code = request.data.get('mfa_code')
        if not mfa_code:
            return Response(
                {'detail': 'MFA code required.', 'mfa_required': True},
                status=status.HTTP_200_OK,
            )
        mfa_used = True

    # ── 5. Issue JWT ──
    refresh    = RefreshToken.for_user(user)
    access_str = str(refresh.access_token)

    # ── 6. Create session ──
    session_timeout_minutes = 60  # safe default

    try:
        if hasattr(SecurityPolicy, 'get_solo'):
            policy = SecurityPolicy.get_solo()
            session_timeout_minutes = policy.session_timeout
        elif hasattr(SecurityPolicy, 'objects'):
            policy = SecurityPolicy.objects.first()
            if policy and hasattr(policy, 'session_timeout'):
                session_timeout_minutes = policy.session_timeout
    except Exception:
        pass

    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=session_timeout_minutes
    )

    create_session(
        user=user,
        ip_address=ip,
        device_info=device,
        city=city,
        session_key=str(refresh['jti']),
        expires_at=expires,
    )

    # ── 7. Record login log ──
    services.record_login_attempt(
        email, 'success', ip, device, city,
        user=user, mfa_used=mfa_used,
    )

    # ✅ ADDED: Record Activity Log for Login
    UserActivityLog.objects.create(
        actor=user,
        action='security',
        description="User logged in successfully"
    )

    # ── 8. Increment login count ──
    if profile:
        UserProfile.objects.filter(pk=profile.pk).update(
            login_count=F('login_count') + 1
        )

    # ── 9. Fetch roles & permissions ──
    perms = get_user_permissions(user)
    roles = list(
        user.user_roles.filter(is_active=True)
        .values_list('role__slug', flat=True)
    )

    # ── 10. Resolve primary role ──
    primary_role = _get_primary_role(
        is_superuser=user.is_superuser,
        is_staff=user.is_staff,
        roles=roles,
    )

    return Response({
        'access':  access_str,
        'refresh': str(refresh),
        'user': {
            'id':           user.id,
            'name':         profile.full_name       if profile else user.get_full_name(),
            'email':        user.email,
            'initials':     profile.avatar_initials  if profile else '',
            'status':       profile.status           if profile else 'active',
            'department':   (
                profile.department.name
                if profile and profile.department else None
            ),
            'is_superuser': user.is_superuser,
            'is_staff':     user.is_staff,
            'primary_role': primary_role,
            'role':         primary_role,
        },
        'roles':       roles,
        'permissions': perms,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/system/auth/logout/"""
    try:
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken(request.data.get('refresh', ''))
        token.blacklist()
    except Exception:
        pass

    jti = request.data.get('jti')
    if jti:
        from crmapp.system.usermanage.models import UserSession
        UserSession.objects.filter(session_key=jti, is_active=True).update(
            is_active=False
        )

    # ✅ ADDED: Record Activity Log for Logout
    from crmapp.system.usermanage.models import UserActivityLog
    UserActivityLog.objects.create(
        actor=request.user,
        action='security',
        description="User logged out"
    )

    return Response({'detail': 'Logged out successfully.'})


# ──────────────────────────────────────────────
# LOGIN LOGS
# ──────────────────────────────────────────────

class LoginLogViewSet(ReadOnlyModelViewSet):
    """GET /api/system/auth/login-logs/ — Login History tab"""
    serializer_class   = LoginLogSerializer
    permission_classes = [can('settings', 'view')]

    def get_queryset(self):
        params = self.request.query_params
        return services.get_login_logs({
            'status':    params.get('status'),
            'user_id':   params.get('user_id'),
            'date_from': params.get('date_from'),
            'date_to':   params.get('date_to'),
        })


# ──────────────────────────────────────────────
# MFA
# ──────────────────────────────────────────────

class MFAUserViewSet(ReadOnlyModelViewSet):
    """GET /api/system/auth/mfa/ — MFA Management tab"""
    serializer_class   = MFAUserSerializer
    permission_classes = [can('settings', 'view')]

    def get_queryset(self):
        return services.get_all_mfa_users()

    @action(detail=True, methods=['post'], url_path='enable')
    def enable(self, request, pk=None):
        mfa    = self.get_object()
        method = request.data.get('method', 'totp')
        result = services.enable_mfa(mfa.user, method, actor=request.user)
        return Response(MFAUserSerializer(result).data)

    @action(detail=True, methods=['post'], url_path='disable')
    def disable(self, request, pk=None):
        mfa    = self.get_object()
        result = services.disable_mfa(mfa.user, actor=request.user)
        return Response(MFAUserSerializer(result).data)

    @action(detail=True, methods=['post'], url_path='regen-codes')
    def regen_codes(self, request, pk=None):
        mfa   = self.get_object()
        codes = services.regenerate_backup_codes(mfa.user)
        return Response({'backup_codes': codes})


# ──────────────────────────────────────────────
# API TOKENS
# ──────────────────────────────────────────────

class APITokenViewSet(ModelViewSet):
    """
    GET    /api/system/auth/tokens/      → API Tokens tab
    POST   /api/system/auth/tokens/      → Generate token  (raw shown once)
    DELETE /api/system/auth/tokens/{id}/ → Revoke token
    """
    serializer_class   = APITokenSerializer
    permission_classes = [can('settings', 'edit')]

    def get_queryset(self):
        return services.get_api_tokens({
            'status': self.request.query_params.get('status'),
        })

    def create(self, request, *args, **kwargs):
        name       = request.data.get('name')
        scopes     = request.data.get('scopes', [])
        expires_at = request.data.get('expires_at')
        if not name or not expires_at:
            return Response(
                {'detail': 'name and expires_at are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token, raw = services.generate_api_token(
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            created_by=request.user,
        )
        data          = APITokenSerializer(token).data
        data['token'] = raw
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        token = self.get_object()
        services.revoke_api_token(token, actor=request.user)
        return Response({'detail': 'Token revoked.'}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Tokens are immutable. Revoke and create a new one.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


# ──────────────────────────────────────────────
# SSO PROVIDERS
# ──────────────────────────────────────────────

class SSOProviderViewSet(ModelViewSet):
    """
    GET  /api/system/auth/sso/              → SSO Providers tab
    POST /api/system/auth/sso/              → Add provider
    POST /api/system/auth/sso/{id}/toggle/  → Enable / disable
    """
    serializer_class   = SSOProviderSerializer
    permission_classes = [can('settings', 'edit')]

    def get_queryset(self):
        return services.get_sso_providers()

    def create(self, request, *args, **kwargs):
        s = SSOProviderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        provider = services.create_sso_provider(s.validated_data, actor=request.user)
        return Response(
            SSOProviderSerializer(provider).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, pk=None):
        provider = self.get_object()
        result   = services.toggle_sso_provider(provider, actor=request.user)
        return Response(SSOProviderSerializer(result).data)


# ──────────────────────────────────────────────
# SECURITY POLICY  (singleton)
# ──────────────────────────────────────────────

class SecurityPolicyView(APIView):
    """
    GET   /api/system/auth/policy/ → current policy
    PATCH /api/system/auth/policy/ → update (Security Policy tab)
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [can('settings', 'view')()]
        return [can('settings', 'edit')()]

    def get(self, request):
        policy = services.get_security_policy()
        return Response(SecurityPolicySerializer(policy).data)

    def patch(self, request):
        policy = services.get_security_policy()
        s      = SecurityPolicySerializer(policy, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = services.update_security_policy(s.validated_data, actor=request.user)
        return Response(SecurityPolicySerializer(updated).data)


# ──────────────────────────────────────────────
# BLOCKED IPs
# ──────────────────────────────────────────────

class BlockedIPViewSet(ModelViewSet):
    """
    GET    /api/system/auth/blocked-ips/      → Blocked IPs tab
    POST   /api/system/auth/blocked-ips/      → Block an IP
    DELETE /api/system/auth/blocked-ips/{id}/ → Unblock
    """
    serializer_class   = BlockedIPSerializer
    permission_classes = [can('settings', 'edit')]

    def get_queryset(self):
        return services.get_blocked_ips()

    def create(self, request, *args, **kwargs):
        ip     = request.data.get('ip_address')
        reason = request.data.get('reason', '')
        city   = request.data.get('city', '')
        if not ip:
            return Response(
                {'detail': 'ip_address is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        blocked = services.block_ip(ip, reason, city, actor=request.user)
        return Response(
            BlockedIPSerializer(blocked).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        blocked = self.get_object()
        services.unblock_ip(blocked, actor=request.user)
        return Response({'detail': 'IP unblocked.'}, status=status.HTTP_200_OK)