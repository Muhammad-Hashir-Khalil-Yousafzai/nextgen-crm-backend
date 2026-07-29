from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Account, AuditLog
from .serializers import AccountSerializer, AccountDetailSerializer, AccountTreeSerializer, AuditLogSerializer
from . import services

# ── Multi-Tenancy Helper ──────────────────────────────────────────────────────
def get_owner_ids(user):
    """Returns list of user IDs jinke created_by se data filter hoga."""
    if user.is_superuser:
        from crmapp.system.usermanage.models import UserProfile
        sub_user_ids = UserProfile.objects.filter(created_by=user).values_list('user_id', flat=True)
        return list(sub_user_ids) + [user.id]
    try:
        from crmapp.system.usermanage.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        if profile.created_by:
            sub_ids = list(
                UserProfile.objects.filter(
                    created_by=profile.created_by
                ).values_list('user_id', flat=True)
            )
            sub_ids.append(profile.created_by_id)
            return sub_ids
    except Exception:
        pass
    return [user.id]

def get_or_404(pk, owner_ids):
    try:    return Account.objects.get(pk=pk, created_by_id__in=owner_ids)
    except: return None

class AccountListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Account.objects.filter(created_by_id__in=owner_ids).select_related('parent','created_by')
        if t := request.query_params.get('type'):           qs = qs.filter(type=t)
        if s := request.query_params.get('status'):         qs = qs.filter(status=s)
        if m := request.query_params.get('linked_module'):  qs = qs.filter(linked_module=m)
        if q := request.query_params.get('search'):         qs = qs.filter(Q(name__icontains=q)|Q(code__icontains=q))
        qs = qs.order_by('code')
        return Response({'count': qs.count(), 'results': AccountSerializer(qs, many=True).data})

    def post(self, request):
        s = AccountSerializer(data=request.data)
        if s.is_valid():
            acct = services.create_account(s.validated_data, user=request.user)
            return Response(AccountSerializer(acct).data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=400)

class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        acct = get_or_404(pk, owner_ids)
        if not acct: return Response({'error':'Not found.'}, status=404)
        return Response(AccountDetailSerializer(acct).data)

    def put(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        acct = get_or_404(pk, owner_ids)
        if not acct: return Response({'error':'Not found.'}, status=404)
        s = AccountSerializer(acct, data=request.data)
        if s.is_valid(): return Response(AccountSerializer(services.update_account(acct, s.validated_data, user=request.user)).data)
        return Response(s.errors, status=400)

    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        acct = get_or_404(pk, owner_ids)
        if not acct: return Response({'error':'Not found.'}, status=404)
        s = AccountSerializer(acct, data=request.data, partial=True)
        if s.is_valid(): return Response(AccountSerializer(services.update_account(acct, s.validated_data, user=request.user)).data)
        return Response(s.errors, status=400)

    def delete(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        acct = get_or_404(pk, owner_ids)
        if not acct: return Response({'error':'Not found.'}, status=404)
        try:
            services.delete_account(acct)
            return Response({'message':'Deleted.'}, status=204)
        except ValueError as e:
            return Response({'error':str(e)}, status=400)

class AccountToggleStatusView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        acct = get_or_404(pk, owner_ids)
        if not acct: return Response({'error':'Not found.'}, status=404)
        updated = services.toggle_status(acct, user=request.user)
        return Response({'message': f"Account is now {updated.status}.", 'status': updated.status})

class AccountTreeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        roots = Account.objects.filter(parent__isnull=True, created_by_id__in=owner_ids).prefetch_related('children__children')
        return Response(AccountTreeSerializer(roots, many=True).data)

class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = AuditLog.objects.filter(account__created_by_id__in=owner_ids).select_related('account','by').order_by('-at')
        if a := request.query_params.get('account'): qs = qs.filter(account_id=a)
        return Response({'count': qs.count(), 'results': AuditLogSerializer(qs, many=True).data})