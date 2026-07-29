from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import PayrollRun
from .serializers import (PayrollRunSerializer, PayrollRunDetailSerializer, PayrollLineSerializer)
from . import services
from crmapp.models import Employee
from crmapp.serializers import EmployeeListSerializer

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


class PayrollEmployeesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Employee.objects.filter(created_by_id__in=owner_ids).select_related('department', 'designation')
        if d := request.query_params.get('department'): qs = qs.filter(department_id=d)
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        if q := request.query_params.get('search'): qs = qs.filter(Q(name__icontains=q) | Q(employee_id__icontains=q) | Q(email__icontains=q))
        return Response({'count': qs.count(), 'results': EmployeeListSerializer(qs, many=True, context={'request': request}).data})

class PayrollRunListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = PayrollRun.objects.filter(created_by_id__in=owner_ids).order_by('-created_at')
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        return Response({'count': qs.count(), 'results': PayrollRunSerializer(qs, many=True).data})

    def post(self, request):
        month = request.data.get('month')
        if not month: return Response({'error': 'month required.'}, status=400)
        return Response(PayrollRunSerializer(services.create_payroll_run(month, user=request.user)).data, status=201)

class PayrollRunDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: run = PayrollRun.objects.get(pk=pk, created_by_id__in=owner_ids)
        except PayrollRun.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        return Response(PayrollRunDetailSerializer(run).data)

class AddPayrollLineView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: run = PayrollRun.objects.get(pk=pk, created_by_id__in=owner_ids)
        except PayrollRun.DoesNotExist: return Response({'error': 'Run not found.'}, status=404)
        employee_id = request.data.get('employee')
        try: emp = Employee.objects.get(pk=employee_id, created_by_id__in=owner_ids)
        except (Employee.DoesNotExist, ValueError, TypeError): return Response({'error': 'Employee not found.'}, status=404)
        line = services.add_payroll_line(run=run, employee=emp, basic=float(request.data.get('basic', 0)), allowances=float(request.data.get('allowances', 0)), deductions=float(request.data.get('deductions', 0)), tax=float(request.data.get('tax', 0)))
        return Response(PayrollLineSerializer(line).data, status=201)

class PayrollRunApproveView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: run = PayrollRun.objects.get(pk=pk, created_by_id__in=owner_ids)
        except PayrollRun.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        try:
            updated = services.approve_run(run)
            return Response({'message': f'Payroll {updated.month} approved.', 'status': updated.status})
        except ValueError as e: return Response({'error': str(e)}, status=400)

class PayrollRunMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: run = PayrollRun.objects.get(pk=pk, created_by_id__in=owner_ids)
        except PayrollRun.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        try:
            updated = services.mark_paid(run)
            return Response({'message': f'Payroll {updated.month} marked as paid.', 'status': updated.status})
        except ValueError as e: return Response({'error': str(e)}, status=400)