from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count
import csv
from django.http import HttpResponse

from .models import Pipeline
from .serializers import PipelineSerializer


class PipelineViewSet(viewsets.ModelViewSet):
    queryset           = Pipeline.objects.all()
    serializer_class   = PipelineSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(stage__icontains=search))

        stage = self.request.query_params.get('stage')
        if stage: qs = qs.filter(stage=stage)

        status_f = self.request.query_params.get('status')
        if status_f: qs = qs.filter(status=status_f)

        min_value = self.request.query_params.get('min_value')
        if min_value: qs = qs.filter(total_value__gte=float(min_value))

        max_value = self.request.query_params.get('max_value')
        if max_value: qs = qs.filter(total_value__lte=float(max_value))

        sort = self.request.query_params.get('sort', 'newest')
        sort_map = {
            'newest': '-created_at', 'oldest': 'created_at',
            'value-high': '-total_value', 'value-low': 'total_value',
            'deals-high': '-no_of_deals', 'deals-low': 'no_of_deals',
            'name-asc': 'name', 'name-desc': '-name',
        }
        qs = qs.order_by(sort_map.get(sort, '-created_at'))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = Pipeline.objects.filter(created_by=request.user)
        total_value  = qs.aggregate(s=Sum('total_value'))['s'] or 0
        total_deals  = qs.aggregate(s=Sum('no_of_deals'))['s'] or 0
        active_count = qs.filter(status='Active').count()
        total_count  = qs.count()
        avg_deals    = round(total_deals / total_count) if total_count else 0
        return Response({
            'total_pipelines':      total_count,
            'total_value':          float(total_value),
            'total_deals':          total_deals,
            'active_pipelines':     active_count,
            'inactive_pipelines':   qs.filter(status='Inactive').count(),
            'avg_deals_per_pipeline': avg_deals,
        })

    @action(detail=False, methods=['get'])
    def stages(self, request):
        stages = Pipeline.objects.filter(created_by=request.user).values_list('stage', flat=True).distinct()
        return Response(list(stages))

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids: return Response({'error': 'No IDs'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = Pipeline.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'success': True, 'deleted': deleted})

    @action(detail=False, methods=['get'])
    def export(self, request):
        pipelines = self.get_queryset()
        response  = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pipelines.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Total Value', 'No of Deals', 'Stage', 'Status', 'Created At'])
        for p in pipelines:
            writer.writerow([p.name, p.total_value, p.no_of_deals, p.stage, p.status, p.created_at])
        return response