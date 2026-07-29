from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
import csv
from django.http import HttpResponse

from .models import Company
from .serializers import CompanySerializer, CompanyListSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    queryset           = Company.objects.all()
    serializer_class   = CompanySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(industry__icontains=search) |
                Q(headquarters__icontains=search) |
                Q(account_owner__icontains=search) |
                Q(email__icontains=search)
            )

        type_filter = self.request.query_params.get('type')
        if type_filter:
            qs = qs.filter(type=type_filter)

        industry = self.request.query_params.get('industry')
        if industry:
            qs = qs.filter(industry=industry)

        min_revenue = self.request.query_params.get('min_revenue')
        if min_revenue:
            qs = qs.filter(annual_revenue__gte=int(min_revenue))

        health = self.request.query_params.get('health')
        if health:
            qs = qs.filter(health=health)

        sort = self.request.query_params.get('sort', 'name-asc')
        sort_map = {
            'name-asc':     'name',
            'name-desc':    '-name',
            'revenue-high': '-annual_revenue',
            'revenue-low':  'annual_revenue',
            'date-desc':    '-created_at',
            'date-asc':     'created_at',
        }
        qs = qs.order_by(sort_map.get(sort, 'name'))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        company = self.get_object()
        from crmapp.crm.contacts.serializers import ContactSerializer
        contacts = company.contacts.all()
        return Response(ContactSerializer(contacts, many=True).data)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = Company.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'success': True, 'deleted': deleted})

    @action(detail=False, methods=['get'])
    def industries(self, request):
        inds = Company.objects.filter(created_by=request.user).exclude(industry='').values_list('industry', flat=True).distinct()
        return Response(list(inds))

    @action(detail=False, methods=['get'])
    def dropdown(self, request):
        companies = Company.objects.filter(created_by=request.user).order_by('name')
        return Response(CompanyListSerializer(companies, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = Company.objects.filter(created_by=request.user)
        return Response({
            'total':     qs.count(),
            'clients':   qs.filter(type='client').count(),
            'vendors':   qs.filter(type='vendor').count(),
            'partners':  qs.filter(type='partner').count(),
            'prospects': qs.filter(type='prospect').count(),
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        companies = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="companies.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Code', 'Industry', 'Type', 'Health',
            'Email', 'Phone', 'Headquarters',
            'Employees', 'Annual Revenue', 'Account Owner', 'Tags'
        ])
        for c in companies:
            writer.writerow([
                c.name, c.code, c.industry, c.type, c.health,
                c.email, c.phone, c.headquarters,
                c.number_of_employees, c.annual_revenue,
                c.account_owner, ', '.join(c.tags)
            ])
        return response