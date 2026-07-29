from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ExpenseCategory, ExpenseClaim
from .serializers import (ExpenseCategorySerializer, ExpenseCategoryTreeSerializer, ExpenseClaimSerializer)
from . import services

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

class CategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = ExpenseCategory.objects.filter(created_by_id__in=owner_ids)
        if l := request.query_params.get('level'): qs = qs.filter(level=l)
        return Response({'count':qs.count(),'results':ExpenseCategorySerializer(qs,many=True).data})
    def post(self, request):
        s = ExpenseCategorySerializer(data=request.data)
        if s.is_valid(): return Response(ExpenseCategorySerializer(services.create_category(s.validated_data, user=request.user)).data, status=201)
        return Response(s.errors, status=400)

class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: cat = ExpenseCategory.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        return Response(ExpenseCategorySerializer(cat).data)
    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: cat = ExpenseCategory.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        s = ExpenseCategorySerializer(cat, data=request.data, partial=True)
        if s.is_valid(): s.save(); return Response(ExpenseCategorySerializer(cat).data)
        return Response(s.errors, status=400)

class CategoryTreeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        roots = ExpenseCategory.objects.filter(parent__isnull=True, created_by_id__in=owner_ids).prefetch_related('children__children')
        return Response(ExpenseCategoryTreeSerializer(roots, many=True).data)

class ClaimListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = ExpenseClaim.objects.filter(created_by_id__in=owner_ids).select_related('employee','category')
        if s := request.query_params.get('status'):   qs = qs.filter(status=s)
        if e := request.query_params.get('employee'): qs = qs.filter(employee_id=e)
        if c := request.query_params.get('category'): qs = qs.filter(category_id=c)
        if q := request.query_params.get('search'):   qs = qs.filter(Q(employee__name__icontains=q)|Q(notes__icontains=q))
        return Response({'count':qs.count(),'results':ExpenseClaimSerializer(qs,many=True).data})
    def post(self, request):
        s = ExpenseClaimSerializer(data=request.data)
        if s.is_valid(): return Response(ExpenseClaimSerializer(services.create_claim(s.validated_data, user=request.user)).data, status=201)
        return Response(s.errors, status=400)

class ClaimDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: c = ExpenseClaim.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        return Response(ExpenseClaimSerializer(c).data)
    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: c = ExpenseClaim.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        s = ExpenseClaimSerializer(c, data=request.data, partial=True)
        if s.is_valid(): s.save(); return Response(ExpenseClaimSerializer(c).data)
        return Response(s.errors, status=400)

class ClaimActionView(APIView):
    permission_classes = [IsAuthenticated]
    ACTION_MAP = { 'submit': services.submit_claim, 'approve': services.approve_claim, 'pay': services.pay_claim, 'flag': services.flag_claim }
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: claim = ExpenseClaim.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        action = request.data.get('action')
        if action not in self.ACTION_MAP: return Response({'error':f"Invalid action. Use: {list(self.ACTION_MAP.keys())}"}, status=400)
        try:
            fn = self.ACTION_MAP[action]
            updated = fn(claim, note=request.data.get('note','')) if action == 'flag' else fn(claim)
            return Response(ExpenseClaimSerializer(updated).data)
        except ValueError as e: return Response({'error':str(e)}, status=400)