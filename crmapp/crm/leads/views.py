from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Avg, Count
import csv
from django.http import HttpResponse

from .models import Lead, LeadNote
from .serializers import LeadSerializer, LeadListSerializer, LeadNoteSerializer


class LeadViewSet(viewsets.ModelViewSet):
    queryset           = Lead.objects.all()
    serializer_class   = LeadSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return LeadListSerializer
        return LeadSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(company_name__icontains=search) |
                Q(company__name__icontains=search) |
                Q(assigned_to__icontains=search)
            )

        status_f = self.request.query_params.get('status')
        if status_f: qs = qs.filter(status=status_f)

        priority = self.request.query_params.get('priority')
        if priority: qs = qs.filter(priority=priority)

        source = self.request.query_params.get('source')
        if source: qs = qs.filter(source=source)

        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to: qs = qs.filter(assigned_to=assigned_to)

        min_value = self.request.query_params.get('min_value')
        if min_value: qs = qs.filter(value__gte=float(min_value))

        max_value = self.request.query_params.get('max_value')
        if max_value: qs = qs.filter(value__lte=float(max_value))

        min_prob = self.request.query_params.get('min_probability')
        if min_prob: qs = qs.filter(probability__gte=int(min_prob))

        company_id = self.request.query_params.get('company_id')
        if company_id: qs = qs.filter(company_id=company_id)

        contact_id = self.request.query_params.get('contact_id')
        if contact_id: qs = qs.filter(contact_id=contact_id)

        sort = self.request.query_params.get('sort', 'newest')
        sort_map = {
            'newest': '-created_at', 'oldest': 'created_at',
            'value-high': '-value', 'value-low': 'value',
            'probability-high': '-probability', 'probability-low': 'probability',
            'score-high': '-score', 'name-asc': 'name', 'name-desc': '-name',
        }
        qs = qs.order_by(sort_map.get(sort, '-created_at'))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs    = Lead.objects.filter(created_by=request.user)
        total = qs.count()
        total_value    = qs.aggregate(s=Sum('value'))['s'] or 0
        weighted_value = sum(l.weighted_value for l in qs)
        closed  = qs.filter(status='closed')
        lost    = qs.filter(status='lost')
        conv    = round((closed.count() / total * 100), 1) if total else 0
        avg_prob= qs.aggregate(a=Avg('probability'))['a'] or 0

        return Response({
            'total':           total,
            'total_value':     float(total_value),
            'weighted_value':  round(weighted_value, 2),
            'closed':          closed.count(),
            'closed_value':    float(closed.aggregate(s=Sum('value'))['s'] or 0),
            'lost':            lost.count(),
            'not_contacted':   qs.filter(status='not-contacted').count(),
            'contacted':       qs.filter(status='contacted').count(),
            'conversion_rate': conv,
            'avg_probability': round(float(avg_prob), 1),
        })

    @action(detail=False, methods=['get'])
    def by_status(self, request):
        results = []
        for s, label in Lead.STATUS_CHOICES:
            leads = Lead.objects.filter(status=s, created_by=request.user)
            total_val = leads.aggregate(s=Sum('value'))['s'] or 0
            avg_prob  = leads.aggregate(a=Avg('probability'))['a'] or 0
            results.append({
                'status':        s,
                'label':         label,
                'count':         leads.count(),
                'total_value':   float(total_val),
                'avg_probability': round(float(avg_prob), 1),
            })
        return Response(results)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids: return Response({'error': 'No IDs'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = Lead.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'success': True, 'deleted': deleted})

    @action(detail=False, methods=['post'])
    def bulk_status(self, request):
        ids        = request.data.get('ids', [])
        new_status = request.data.get('status')
        if not ids or not new_status: return Response({'error': 'ids and status required'}, status=status.HTTP_400_BAD_REQUEST)
        updated = Lead.objects.filter(id__in=ids, created_by=request.user).update(status=new_status)
        return Response({'success': True, 'updated': updated})

    @action(detail=False, methods=['post'])
    def bulk_assign(self, request):
        ids         = request.data.get('ids', [])
        assigned_to = request.data.get('assigned_to')
        if not ids or not assigned_to: return Response({'error': 'ids and assigned_to required'}, status=status.HTTP_400_BAD_REQUEST)
        updated = Lead.objects.filter(id__in=ids, created_by=request.user).update(assigned_to=assigned_to)
        return Response({'success': True, 'updated': updated})

    @action(detail=False, methods=['post'])
    def bulk_priority(self, request):
        ids      = request.data.get('ids', [])
        priority = request.data.get('priority')
        if not ids or not priority: return Response({'error': 'ids and priority required'}, status=status.HTTP_400_BAD_REQUEST)
        updated = Lead.objects.filter(id__in=ids, created_by=request.user).update(priority=priority)
        return Response({'success': True, 'updated': updated})

    @action(detail=True, methods=['get', 'post'])
    def notes(self, request, pk=None):
        lead = self.get_object()
        if request.method == 'GET':
            notes = lead.lead_notes.all()
            return Response(LeadNoteSerializer(notes, many=True).data)
        serializer = LeadNoteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(lead=lead)
            lead.notes_count += 1
            lead.activity_log = [{
                'type':        'note',
                'description': request.data.get('content', ''),
                'time':        'Just now',
                'user':        request.data.get('created_by', 'User'),
            }] + (lead.activity_log or [])
            lead.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def assignees(self, request):
        assignees = Lead.objects.filter(created_by=request.user).exclude(assigned_to='').values_list('assigned_to', flat=True).distinct()
        return Response(list(assignees))

    @action(detail=False, methods=['get'])
    def export(self, request):
        leads    = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="leads.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Email', 'Phone', 'Company', 'Location',
            'Value', 'Probability', 'Status', 'Priority',
            'Source', 'Stage', 'Assigned To', 'Score', 'Tags',
        ])
        for l in leads:
            writer.writerow([
                l.name, l.email, l.phone, l.company_name, l.location,
                l.value, l.probability, l.status, l.priority,
                l.source, l.deal_stage, l.assigned_to, l.score,
                ', '.join(l.tags),
            ])
        return response


class LeadNoteViewSet(viewsets.ModelViewSet):
    queryset           = LeadNote.objects.all()
    serializer_class   = LeadNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(lead__created_by=self.request.user)