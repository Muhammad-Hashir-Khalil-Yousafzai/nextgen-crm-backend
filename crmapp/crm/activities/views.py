from datetime import date, timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
import csv
from django.http import HttpResponse

from .models import Activity
from .serializers import ActivitySerializer, ActivityListSerializer


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related(
        'contact', 'company', 'lead', 'deal', 'created_by'
    ).all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return ActivityListSerializer
        return ActivitySerializer

    def get_queryset(self):
        # Filter by logged-in user
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(owner__icontains=search) |
                Q(activity_type__icontains=search)
            )

        activity_type = self.request.query_params.get('activity_type')
        if activity_type:
            qs = qs.filter(activity_type=activity_type)

        date_start = self.request.query_params.get('date_start')
        if date_start:
            qs = qs.filter(due_date__gte=date_start)

        date_end = self.request.query_params.get('date_end')
        if date_end:
            qs = qs.filter(due_date__lte=date_end)

        today = date.today()
        overdue = self.request.query_params.get('overdue')
        if overdue == 'true':
            qs = qs.filter(due_date__lt=today)

        upcoming = self.request.query_params.get('upcoming')
        if upcoming == 'true':
            qs = qs.filter(due_date__gte=today)

        contact_id = self.request.query_params.get('contact')
        if contact_id:
            qs = qs.filter(contact_id=contact_id)

        company_id = self.request.query_params.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)

        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)

        deal_id = self.request.query_params.get('deal')
        if deal_id:
            qs = qs.filter(deal_id=deal_id)

        sort = self.request.query_params.get('sort', 'last7days')

        if sort == 'last7days':
            week_ago = today - timedelta(days=7)
            qs = qs.filter(created_date__gte=week_ago).order_by('-created_date', '-id')
        else:
            sort_map = {
                'newest':     ('-created_date', '-id'),
                'oldest':     ('created_date',  'id'),
                'due-soon':   ('due_date',       'id'),
                'due-later':  ('-due_date',      '-id'),
                'title-asc':  ('title',),
                'title-desc': ('-title',),
            }
            ordering = sort_map.get(sort, ('-created_date', '-id'))
            qs = qs.order_by(*ordering)

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        today = date.today()
        qs    = Activity.objects.filter(created_by=request.user)

        by_type = {}
        for type_key, _ in Activity.TYPE_CHOICES:
            by_type[type_key] = qs.filter(activity_type=type_key).count()

        return Response({
            'total':    qs.count(),
            'upcoming': qs.filter(due_date__gte=today).count(),
            'overdue':  qs.filter(due_date__lt=today).count(),
            'by_type':  by_type,
        })

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = Activity.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'success': True, 'deleted': deleted})

    @action(detail=True, methods=['get'])
    def image(self, request, pk=None):
        activity = self.get_object()
        return Response({
            'id':          activity.id,
            'has_image':   activity.has_image,
            'owner_image': activity.owner_image or None,
        })

    @action(detail=True, methods=['patch'])
    def upload_image(self, request, pk=None):
        activity   = self.get_object()
        serializer = ActivitySerializer(
            activity,
            data={'owner_image': request.data.get('owner_image', '')},
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'id':        activity.id,
            'has_image': activity.has_image,
            'message':   'Image updated successfully.' if activity.has_image else 'Image cleared.',
        })

    @action(detail=False, methods=['get'])
    def owners(self, request):
        owners = (
            Activity.objects.filter(created_by=request.user).exclude(owner='')
            .values_list('owner', flat=True)
            .distinct()
            .order_by('owner')
        )
        return Response(list(owners))

    @action(detail=False, methods=['get'])
    def export(self, request):
        activities = self.get_queryset()
        response   = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="activities.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Title', 'Activity Type', 'Due Date',
            'Owner', 'Has Image', 'Is Overdue',
            'Contact', 'Company', 'Lead', 'Deal',
            'Notes', 'Created Date',
        ])
        for a in activities:
            writer.writerow([
                a.id, a.title, a.activity_type, a.due_date,
                a.owner, a.has_image, a.is_overdue,
                a.contact.name  if a.contact  else '',
                a.company.name  if a.company  else '',
                a.lead.name     if a.lead     else '',
                a.deal.title    if a.deal     else '',
                a.notes, a.created_date,
            ])
        return response