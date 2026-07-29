from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Asset
from .serializers import AssetSerializer, AssetDetailSerializer, AssetAssignmentSerializer, AssetMaintenanceSerializer
from . import services
from crmapp.models import Employee

# ── Multi-Tenancy Helper ──────────────────────────────────────────────────────
def get_owner_ids(user):
    if user.is_superuser:
        from crmapp.system.usermanage.models import UserProfile
        sub_user_ids = UserProfile.objects.filter(created_by=user).values_list('user_id', flat=True)
        return list(sub_user_ids) + [user.id]
    try:
        from crmapp.system.usermanage.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        if profile.created_by:
            sub_ids = list(UserProfile.objects.filter(created_by=profile.created_by).values_list('user_id', flat=True))
            sub_ids.append(profile.created_by_id)
            return sub_ids
    except Exception:
        pass
    return [user.id]

class AssetListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Asset.objects.filter(created_by_id__in=owner_ids)
        if c := request.query_params.get('category'): qs = qs.filter(category=c)
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        if q := request.query_params.get('search'): qs = qs.filter(Q(name__icontains=q) | Q(asset_tag__icontains=q))
        return Response({'count': qs.count(), 'results': AssetSerializer(qs, many=True).data})

    def post(self, request):
        s = AssetSerializer(data=request.data)
        if s.is_valid():
            return Response(AssetSerializer(services.create_asset(s.validated_data, user=request.user)).data, status=201)
        return Response(s.errors, status=400)

class AssetDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: a = Asset.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Asset.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        return Response(AssetDetailSerializer(a).data)

    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: a = Asset.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Asset.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        s = AssetSerializer(a, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(AssetSerializer(a).data)
        return Response(s.errors, status=400)

class AssetAssignView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: a = Asset.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Asset.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        employee_id = request.data.get('employee')
        date = request.data.get('assigned_date')
        if not employee_id or not date: return Response({'error': 'employee and assigned_date required.'}, status=400)
        
        # ✅ FIX: Employee ko bhi owner_ids se filter karein
        try: employee = Employee.objects.get(pk=employee_id, created_by_id__in=owner_ids)
        except (Employee.DoesNotExist, ValueError): return Response({'error': 'Employee not found.'}, status=404)
        return Response(AssetAssignmentSerializer(services.assign_asset(a, employee, date)).data, status=201)

class AssetReturnView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: a = Asset.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Asset.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        date = request.data.get('returned_date')
        if not date: return Response({'error': 'returned_date required.'}, status=400)
        services.return_asset(a, date)
        return Response({'message': 'Asset returned.', 'status': a.status})

class AssetMaintenanceView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: a = Asset.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Asset.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        m = services.log_maintenance(a, request.data.get('type'), float(request.data.get('cost', 0)), request.data.get('performed_by', ''), request.data.get('date'), request.data.get('next_due'), request.data.get('notes', ''))
        return Response(AssetMaintenanceSerializer(m).data, status=201)