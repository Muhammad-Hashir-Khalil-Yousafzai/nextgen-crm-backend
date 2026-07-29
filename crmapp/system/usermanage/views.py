# usermanage/views.py
from urllib import request

from urllib import request
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import UserProfile, Department, UserSession, UserActivityLog
from .serializers import (
    UserListSerializer, UserDetailSerializer,
    UserCreateSerializer, UserStatusSerializer,
    UserPasswordSerializer, DepartmentSerializer,
    UserSessionSerializer, UserActivityLogSerializer,
)
from . import services
from crmapp.system.roles.permissions import can


# ──────────────────────────────────────────────
# USER VIEWSET
# ──────────────────────────────────────────────
class UserViewSet(ModelViewSet):
    """
    GET    /api/users/                        → list (table/grid)
    POST   /api/users/                        → create user
    GET    /api/users/{id}/                   → profile viewer
    PATCH  /api/users/{id}/                   → update profile
    DELETE /api/users/{id}/                   → soft delete

    PATCH  /api/users/{id}/status/            → change status
    POST   /api/users/{id}/reset-password/    → force reset password
    POST   /api/users/{id}/toggle-mfa/        → enable/disable MFA
    DELETE /api/users/{id}/sessions/          → force logout all
    POST   /api/users/bulk-status/            → bulk status change
    POST   /api/users/bulk-import/            → CSV import
    """
    filter_backends  = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'department__slug']
    search_fields    = ['full_name', 'user__email', 'city', 'phone']
    ordering_fields  = ['full_name', 'login_count', 'action_count']
    ordering         = ['full_name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [can('crm', 'view')()]
        elif self.action == 'create':
            return [can('crm', 'create')()]
        elif self.action in ['update', 'partial_update', 'change_status',
                             'toggle_mfa', 'reset_password']:
            return [can('crm', 'edit')()]
        elif self.action == 'destroy':
            return [can('crm', 'delete')()]
        elif self.action == 'bulk_import':
            return [can('crm', 'import')()]
        elif self.action == 'bulk_status':
            return [can('crm', 'edit')()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'change_status':
            return UserStatusSerializer
        elif self.action == 'reset_password':
            return UserPasswordSerializer
        return UserDetailSerializer

    
    def get_queryset(self):
        from crmapp.system.usermanage.models import UserProfile
        
        user = self.request.user
        
        # Base queryset from services
        qs = services.get_user_list({
            'search': self.request.query_params.get('search'),
            'dept':   self.request.query_params.get('dept'),
            'status': self.request.query_params.get('status'),
            'role':   self.request.query_params.get('role'),
        })
        
        # ✅ Multi-Tenancy Logic
        if user.is_superuser:
            # Jo users is admin ne banaye hain, ya jo uske sub-users ne banaye hain
            sub_user_ids = UserProfile.objects.filter(created_by=user).values_list('user_id', flat=True)
            
            qs = qs.filter(
                Q(user=user) | 
                Q(created_by=user) | 
                Q(created_by_id__in=sub_user_ids)
            ).distinct()
        else:
            # Sub-users (jaise HR) sirf khud ko aur apne banaye users ko dekhenge
            qs = qs.filter(
                Q(user=user) | Q(created_by=user)
            ).distinct()
            
        return qs
def create(self, request, *args, **kwargs):
    s = UserCreateSerializer(data=request.data, context={'request': request})
    s.is_valid(raise_exception=True)
    try:
        profile = s.save()
        # ✅ Tenant link — jo superadmin user bana raha hai usse link karo
        if not profile.created_by:
            profile.created_by = request.user
            profile.save(update_fields=['created_by'])
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(UserDetailSerializer(profile).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        profile = self.get_object()
        s = UserDetailSerializer(profile, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = services.update_user_profile(profile, s.validated_data, actor=request.user)
        return Response(UserDetailSerializer(updated).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        profile = self.get_object()
        services.update_user_status(profile, 'deleted', actor=request.user)
        return Response({'detail': 'User deleted.'})

    @action(detail=True, methods=['patch'], url_path='status')
    def change_status(self, request, pk=None):
        profile    = self.get_object()
        new_status = request.data.get('status')
        if new_status not in dict(UserProfile.STATUS_CHOICES):
            return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        updated = services.update_user_status(profile, new_status, actor=request.user)
        return Response(UserDetailSerializer(updated).data)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        profile = self.get_object()
        s       = UserPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.reset_password(profile, s.validated_data['new_password'], actor=request.user)
        return Response({'detail': 'Password reset successfully.'})

    @action(detail=True, methods=['post'], url_path='toggle-mfa')
    def toggle_mfa(self, request, pk=None):
        from auth_security.services import toggle_mfa_for_user
        profile = self.get_object()
        result  = toggle_mfa_for_user(profile.user, actor=request.user)
        return Response({'mfa_enabled': result})

    @action(detail=True, methods=['delete'], url_path='sessions')
    def force_logout(self, request, pk=None):
        profile = self.get_object()
        services.terminate_all_sessions(profile.user)
        return Response({'detail': 'All sessions terminated.'})

    @action(detail=False, methods=['post'], url_path='bulk-status')
    def bulk_status(self, request):
        ids        = request.data.get('ids', [])
        new_status = request.data.get('status')
        if not ids or not new_status:
            return Response({'detail': 'ids and status required.'}, status=400)
        count = services.bulk_update_status(ids, new_status, actor=request.user)
        return Response({'updated': count})

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'No file uploaded.'}, status=400)
        import csv, io
        rows   = list(csv.DictReader(io.StringIO(file.read().decode('utf-8'))))
        result = services.bulk_import_users(rows, actor=request.user)
        return Response(result)


# ──────────────────────────────────────────────
# DEPARTMENT VIEWSET
# ──────────────────────────────────────────────
class DepartmentViewSet(ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [can('hr', 'view')()]
        return [can('hr', 'edit')()]

    def get_queryset(self):
        return services.get_departments_with_stats()


# ──────────────────────────────────────────────
# SESSION VIEWSET
# ──────────────────────────────────────────────
class UserSessionViewSet(ReadOnlyModelViewSet):
    serializer_class   = UserSessionSerializer
    permission_classes = [can('crm', 'view')]

    def get_queryset(self):
        return services.get_active_sessions()

    def destroy(self, request, *args, **kwargs):
        session = self.get_object()
        services.terminate_session(session, actor=request.user)
        return Response({'detail': 'Session terminated.'})


# ──────────────────────────────────────────────
# ACTIVITY LOG VIEWSET
# ──────────────────────────────────────────────
class UserActivityLogViewSet(ReadOnlyModelViewSet):
    serializer_class   = UserActivityLogSerializer
    permission_classes = [can('crm', 'view')]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_fields   = ['action', 'actor']
    ordering           = ['-timestamp']

    def get_queryset(self):
        return services.get_activity_logs({
            'action':   self.request.query_params.get('action'),
            'actor_id': self.request.query_params.get('actor_id'),
        })