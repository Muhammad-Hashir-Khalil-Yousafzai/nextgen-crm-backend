from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from datetime import date, timedelta
import csv
from django.http import HttpResponse

from .models import Contract
from .serializers import ContractSerializer


class ContractViewSet(viewsets.ModelViewSet):
    queryset           = Contract.objects.all()
    serializer_class   = ContractSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(contract_number__icontains=search) |
                Q(customer_name__icontains=search)
            )

        status_f = self.request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)

        contract_type = self.request.query_params.get('contract_type')
        if contract_type:
            qs = qs.filter(contract_type=contract_type)

        sort = self.request.query_params.get('sort', 'newest')
        sort_map = {
            'newest':   '-created_at',
            'oldest':   'created_at',
            'endDate':  'end_date',
            'value':    '-total_value',
        }
        qs = qs.order_by(sort_map.get(sort, '-created_at'))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        today = date.today()
        qs    = Contract.objects.filter(created_by=request.user)
        active = qs.filter(status='active')
        return Response({
            'total':       qs.count(),
            'active':      active.count(),
            'expiring_30': active.filter(end_date__lte=today + timedelta(days=30), end_date__gte=today).count(),
            'expiring_60': active.filter(end_date__lte=today + timedelta(days=60), end_date__gte=today).count(),
            'pending':     qs.filter(status__in=['draft', 'pending_approval']).count(),
            'expired':     qs.filter(status__in=['expired', 'terminated']).count(),
            'total_value': float(active.aggregate(v=Sum('total_value'))['v'] or 0),
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        contracts = self.get_queryset()
        response  = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contracts.csv"'
        writer = csv.writer(response)
        writer.writerow(['Contract #', 'Title', 'Type', 'Status', 'Customer',
                         'Company', 'Value', 'Start Date', 'End Date'])
        for c in contracts:
            writer.writerow([c.contract_number, c.title, c.contract_type,
                             c.status, c.customer_name, c.customer_company,
                             c.total_value, c.start_date, c.end_date])
        return response