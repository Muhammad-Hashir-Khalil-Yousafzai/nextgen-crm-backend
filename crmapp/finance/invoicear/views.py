from decimal import Decimal
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Customer, Invoice
from .serializers import (CustomerSerializer, CustomerDetailSerializer, InvoiceSerializer, InvoiceDetailSerializer, ARPaymentSerializer)
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


class CustomerListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Customer.objects.filter(created_by_id__in=owner_ids)
        if q := request.query_params.get('search'): qs = qs.filter(Q(name__icontains=q)|Q(company__icontains=q))
        if r := request.query_params.get('risk'): qs = qs.filter(risk=r)
        return Response({'count': qs.count(), 'results': CustomerSerializer(qs, many=True).data})

    def post(self, request):
        s = CustomerSerializer(data=request.data)
        if s.is_valid(): return Response(CustomerSerializer(services.create_customer(s.validated_data, user=request.user)).data, status=201)
        return Response(s.errors, status=400)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: c = Customer.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Customer.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        return Response(CustomerDetailSerializer(c).data)

    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: c = Customer.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Customer.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        s = CustomerSerializer(c, data=request.data, partial=True)
        if s.is_valid(): return Response(CustomerSerializer(services.update_customer(c, s.validated_data)).data)
        return Response(s.errors, status=400)


class InvoiceListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Invoice.objects.filter(created_by_id__in=owner_ids).select_related('customer').prefetch_related('items', 'payments', 'disputes')
        if s := request.query_params.get('status'):   qs = qs.filter(status=s)
        if c := request.query_params.get('customer'): qs = qs.filter(customer_id=c)
        if q := request.query_params.get('search'): qs = qs.filter(Q(invoice_no__icontains=q)|Q(customer__name__icontains=q))
        return Response({'count': qs.count(), 'results': InvoiceDetailSerializer(qs, many=True).data})

    def post(self, request):
        items_data = request.data.get('items', [])
        s = InvoiceSerializer(data=request.data)
        if s.is_valid():
            inv = services.create_invoice(s.validated_data, items_data=items_data, user=request.user)
            fresh_inv = Invoice.objects.prefetch_related('items', 'payments', 'disputes').get(pk=inv.pk)
            return Response(InvoiceDetailSerializer(fresh_inv).data, status=201)
        return Response(s.errors, status=400)


class InvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: inv = Invoice.objects.filter(created_by_id__in=owner_ids).prefetch_related('items', 'payments', 'disputes').get(pk=pk)
        except Invoice.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        return Response(InvoiceDetailSerializer(inv).data)

    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: inv = Invoice.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Invoice.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        s = InvoiceSerializer(inv, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            fresh_inv = Invoice.objects.prefetch_related('items', 'payments', 'disputes').get(pk=pk)
            return Response(InvoiceDetailSerializer(fresh_inv).data)
        return Response(s.errors, status=400)


class RecordPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: inv = Invoice.objects.get(pk=pk, created_by_id__in=owner_ids)
        except Invoice.DoesNotExist: return Response({'error': 'Not found.'}, status=404)
        amount = request.data.get('amount')
        date   = request.data.get('date')
        method = request.data.get('method', 'Bank Transfer')
        if not amount or not date: return Response({'error': 'amount and date required.'}, status=400)
        dec_amount = Decimal(str(amount))
        services.record_payment(inv, dec_amount, date, method)
        fresh_inv = Invoice.objects.prefetch_related('items', 'payments', 'disputes').get(pk=pk)
        return Response(InvoiceDetailSerializer(fresh_inv).data, status=201)