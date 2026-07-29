from decimal import Decimal
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Vendor, Bill, PurchaseOrder
from .serializers import (
    VendorSerializer, BillSerializer, BillDetailSerializer,
    APPaymentSerializer, PurchaseOrderSerializer,
)
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

class VendorListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Vendor.objects.filter(created_by_id__in=owner_ids)
        if q := request.query_params.get('search'):
            qs = qs.filter(Q(name__icontains=q) | Q(company__icontains=q))
        return Response({'count': qs.count(), 'results': VendorSerializer(qs, many=True).data})

    def post(self, request):
        s = VendorSerializer(data=request.data)
        if s.is_valid():
            vendor = services.create_vendor(s.validated_data, user=request.user)
            return Response(VendorSerializer(vendor).data, status=201)
        return Response(s.errors, status=400)


class BillListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Bill.objects.filter(created_by_id__in=owner_ids).select_related('vendor').prefetch_related('items', 'payments', 'approvals')
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        if v := request.query_params.get('vendor'): qs = qs.filter(vendor_id=v)
        return Response({'count': qs.count(), 'results': BillDetailSerializer(qs, many=True).data})

    def post(self, request):
        items_data = request.data.get('items', [])
        s = BillSerializer(data=request.data)
        if s.is_valid():
            bill = services.create_bill(s.validated_data, items_data=items_data, user=request.user)
            fresh_bill = Bill.objects.prefetch_related('items', 'payments', 'approvals').get(pk=bill.pk)
            return Response(BillDetailSerializer(fresh_bill).data, status=201)
        return Response(s.errors, status=400)


class BillDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: bill = Bill.objects.filter(created_by_id__in=owner_ids).prefetch_related('items', 'payments', 'approvals').get(pk=pk)
        except Bill.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        return Response(BillDetailSerializer(bill).data)

    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: bill = Bill.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Bill.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        s = BillSerializer(bill, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            updated_bill = Bill.objects.prefetch_related('items', 'payments', 'approvals').get(pk=pk)
            return Response(BillDetailSerializer(updated_bill).data)
        return Response(s.errors, status=400)


class BillPayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: bill = Bill.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Bill.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        amount = request.data.get('amount')
        date = request.data.get('date')
        method = request.data.get('method', 'Bank Transfer')
        if not amount or not date: return Response({'error': 'amount and date required.'}, status=400)
        dec_amount = Decimal(str(amount))
        services.record_payment(bill, dec_amount, date, method)
        fresh_bill = Bill.objects.prefetch_related('items', 'payments', 'approvals').get(pk=pk)
        return Response(BillDetailSerializer(fresh_bill).data, status=201)


class BillApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: bill = Bill.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Bill.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        role = request.data.get('role', 'Finance Manager')
        name = request.data.get('name', 'Admin User')
        note = request.data.get('note', '')
        services.approve_bill(bill, role, name, note)
        fresh_bill = Bill.objects.prefetch_related('items', 'payments', 'approvals').get(pk=pk)
        return Response(BillDetailSerializer(fresh_bill).data, status=201)


class PurchaseOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = PurchaseOrder.objects.filter(created_by_id__in=owner_ids).select_related('vendor', 'bill')
        return Response({'count': qs.count(), 'results': PurchaseOrderSerializer(qs, many=True).data})

    def post(self, request):
        s = PurchaseOrderSerializer(data=request.data)
        if s.is_valid():
            s.save(created_by=request.user)
            return Response(s.data, status=201)
        return Response(s.errors, status=400)