from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q, Sum, Count, Avg
import csv
from django.http import HttpResponse

from .models import Deal
from .serializers import DealSerializer, DealListSerializer


class DealViewSet(viewsets.ModelViewSet):
    queryset           = Deal.objects.select_related(
        'company', 'contact', 'lead', 'pipeline', 'created_by'
    ).all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'list':
            return DealListSerializer
        return DealSerializer

    # ── Filtering & sorting ────────────────────────────────────────
    def get_queryset(self):
        qs = super().get_queryset()

        # Search — matches frontend: title, code, email, company, assignee
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)       |
                Q(code__icontains=search)        |
                Q(email__icontains=search)       |
                Q(company_name__icontains=search)|
                Q(assigned_to__icontains=search)
            )

        # Stage filter (comma-separated for multi-select)
        stages = self.request.query_params.get('stage')
        if stages:
            qs = qs.filter(stage__in=stages.split(','))

        # Assignee filter
        assignee = self.request.query_params.get('assignee')
        if assignee:
            qs = qs.filter(assigned_to=assignee)

        # Value filter
        min_value = self.request.query_params.get('min_value')
        if min_value:
            qs = qs.filter(value__gte=float(min_value))

        # Probability range
        prob_min = self.request.query_params.get('probability_min')
        prob_max = self.request.query_params.get('probability_max')
        if prob_min:
            qs = qs.filter(probability__gte=int(prob_min))
        if prob_max:
            qs = qs.filter(probability__lte=int(prob_max))

        # FK filters
        company_id  = self.request.query_params.get('company')
        contact_id  = self.request.query_params.get('contact')
        pipeline_id = self.request.query_params.get('pipeline')
        lead_id     = self.request.query_params.get('lead')
        if company_id:  qs = qs.filter(company_id=company_id)
        if contact_id:  qs = qs.filter(contact_id=contact_id)
        if pipeline_id: qs = qs.filter(pipeline_id=pipeline_id)
        if lead_id:     qs = qs.filter(lead_id=lead_id)

        # Sorting — matches frontend SORT_OPTIONS
        sort = self.request.query_params.get('sort', 'date-desc')
        sort_map = {
            'date-desc':        '-created_at',
            'date-asc':         'created_at',
            'value-high':       '-value',
            'value-low':        'value',
            'probability-high': '-probability',
            'probability-low':  'probability',
        }
        qs = qs.order_by(sort_map.get(sort, '-created_at'))
        return qs

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    # ── PATCH stage only (drag & drop) ────────────────────────────
    @action(detail=True, methods=['patch'])
    def move(self, request, pk=None):
        """Move a deal to a different stage — used by kanban drag & drop."""
        deal  = self.get_object()
        stage = request.data.get('stage')
        if stage not in dict(Deal.STAGE_CHOICES):
            return Response({'error': 'Invalid stage'}, status=status.HTTP_400_BAD_REQUEST)
        deal.stage = stage
        deal.save(update_fields=['stage', 'updated_at'])
        return Response(DealListSerializer(deal).data)

    # ── Stats ──────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = Deal.objects.all()
        total_value     = qs.aggregate(s=Sum('value'))['s'] or 0
        forecasted      = sum(d.weighted_value for d in qs)
        by_stage        = {}
        for stage_key, stage_label in Deal.STAGE_CHOICES:
            stage_qs = qs.filter(stage=stage_key)
            by_stage[stage_key] = {
                'count': stage_qs.count(),
                'value': float(stage_qs.aggregate(s=Sum('value'))['s'] or 0),
            }
        return Response({
            'total_deals':      qs.count(),
            'total_value':      float(total_value),
            'forecasted_value': float(forecasted),
            'avg_probability':  qs.aggregate(a=Avg('probability'))['a'] or 0,
            'by_stage':         by_stage,
        })

    # ── Distinct assignees (for filter dropdown) ───────────────────
    @action(detail=False, methods=['get'])
    def assignees(self, request):
        assignees = (
            Deal.objects.exclude(assigned_to='')
            .values_list('assigned_to', flat=True)
            .distinct()
        )
        return Response(list(assignees))

    # ── Distinct stages present in DB ─────────────────────────────
    @action(detail=False, methods=['get'])
    def stages(self, request):
        return Response([
            {'id': k, 'name': v} for k, v in Deal.STAGE_CHOICES
        ])

    # ── Bulk delete ────────────────────────────────────────────────
    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = Deal.objects.filter(id__in=ids).delete()
        return Response({'success': True, 'deleted': deleted})

    # ── Bulk stage update ──────────────────────────────────────────
    @action(detail=False, methods=['patch'])
    def bulk_move(self, request):
        ids   = request.data.get('ids', [])
        stage = request.data.get('stage')
        if not ids or not stage:
            return Response({'error': 'ids and stage required'}, status=status.HTTP_400_BAD_REQUEST)
        if stage not in dict(Deal.STAGE_CHOICES):
            return Response({'error': 'Invalid stage'}, status=status.HTTP_400_BAD_REQUEST)
        updated = Deal.objects.filter(id__in=ids).update(stage=stage)
        return Response({'success': True, 'updated': updated})

    # ── CSV Export ─────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def export(self, request):
        deals    = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="deals.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Title', 'Code', 'Value', 'Probability', 'Weighted Value',
            'Stage', 'Company', 'Assigned To', 'Email', 'Phone',
            'Location', 'Tags', 'Close Date', 'Created At',
        ])
        for d in deals:
            writer.writerow([
                d.title, d.code, d.value, d.probability, round(d.weighted_value, 2),
                d.stage, d.company_display, d.assigned_to, d.email, d.phone,
                d.location, ','.join(d.tags), d.close_date, d.created_at,
            ])
        return response
