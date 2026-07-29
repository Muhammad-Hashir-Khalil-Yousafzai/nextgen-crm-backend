import csv
from datetime import timedelta

from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FollowUp
from .serializers import FollowUpSerializer, FollowUpListSerializer


class FollowUpViewSet(viewsets.ModelViewSet):
    queryset = FollowUp.objects.select_related(
        'contact', 'deal', 'activity', 'created_by'
    ).all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return FollowUpListSerializer
        return FollowUpSerializer

    def get_queryset(self):
        qs  = super().get_queryset().filter(created_by=self.request.user)
        now = timezone.now()

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(contact__name__icontains=search)
            )

        type_ = self.request.query_params.get('type')
        if type_ and type_ != 'all':
            qs = qs.filter(type=type_)

        priority = self.request.query_params.get('priority')
        if priority and priority != 'all':
            qs = qs.filter(priority=priority)

        status_ = self.request.query_params.get('status')
        if status_ and status_ != 'all':
            qs = qs.filter(status=status_)

        tab = self.request.query_params.get('tab')
        if tab == 'overdue':
            qs = qs.filter(status=FollowUp.STATUS_PENDING, due_date__lt=now)
        elif tab == 'today':
            today_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0)
            today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            qs = qs.filter(status=FollowUp.STATUS_PENDING, due_date__range=(today_start, today_end))
        elif tab == 'upcoming':
            qs = qs.filter(status=FollowUp.STATUS_PENDING, due_date__gt=now)
        elif tab == 'completed':
            qs = qs.filter(status=FollowUp.STATUS_COMPLETED)

        contact_id  = self.request.query_params.get('contact')
        deal_id     = self.request.query_params.get('deal')
        activity_id = self.request.query_params.get('activity')
        if contact_id:  qs = qs.filter(contact_id=contact_id)
        if deal_id:     qs = qs.filter(deal_id=deal_id)
        if activity_id: qs = qs.filter(activity_id=activity_id)

        sort = self.request.query_params.get('sort', 'dueDate')
        sort_map = {
            'dueDate':  'due_date',
            'priority': 'priority',
            'contact':  'contact__name',
        }
        qs = qs.order_by(sort_map.get(sort, 'due_date'))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        all_qs = FollowUp.objects.filter(created_by=request.user)
        now    = timezone.now()
        today_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0)
        today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        total     = all_qs.count()
        overdue   = all_qs.filter(status=FollowUp.STATUS_PENDING, due_date__lt=now).count()
        today     = all_qs.filter(status=FollowUp.STATUS_PENDING, due_date__range=(today_start, today_end)).count()
        upcoming  = all_qs.filter(status=FollowUp.STATUS_PENDING, due_date__gt=now).count()
        completed = all_qs.filter(status=FollowUp.STATUS_COMPLETED).count()
        missed    = all_qs.filter(status=FollowUp.STATUS_MISSED).count()
        pending   = all_qs.filter(status=FollowUp.STATUS_PENDING).count()

        completed_pct = round((completed / total * 100)) if total else 0

        return Response({
            'total':          total,
            'overdue':        overdue,
            'today':          today,
            'upcoming':       upcoming,
            'completed':      completed,
            'missed':         missed,
            'pending':        pending,
            'completed_pct':  completed_pct,
        })

    @action(detail=True, methods=['patch'])
    def complete(self, request, pk=None):
        fu = self.get_object()
        fu.status = FollowUp.STATUS_COMPLETED
        fu.save(update_fields=['status', 'updated_at'])
        return Response(FollowUpSerializer(fu).data)

    @action(detail=True, methods=['patch'])
    def reschedule(self, request, pk=None):
        fu   = self.get_object()
        days = int(request.data.get('days', 3))
        fu.due_date = fu.due_date + timedelta(days=days)
        fu.status   = FollowUp.STATUS_PENDING
        fu.save(update_fields=['due_date', 'status', 'updated_at'])
        return Response(FollowUpSerializer(fu).data)

    @action(detail=True, methods=['patch'])
    def cancel(self, request, pk=None):
        fu = self.get_object()
        fu.status = FollowUp.STATUS_CANCELLED
        fu.save(update_fields=['status', 'updated_at'])
        return Response(FollowUpSerializer(fu).data)

    @action(detail=False, methods=['post'])
    def bulk_complete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        updated = FollowUp.objects.filter(id__in=ids, created_by=request.user).update(status=FollowUp.STATUS_COMPLETED)
        return Response({'success': True, 'updated': updated})

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = FollowUp.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'success': True, 'deleted': deleted})

    @action(detail=False, methods=['get'])
    def export(self, request):
        qs       = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="followups.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Title', 'Description', 'Type', 'Priority', 'Status',
            'Due Date', 'Reminder Time', 'Assigned To',
            'Recurring', 'Frequency', 'Interval',
            'Contact', 'Deal', 'Notes', 'Tags', 'Created At',
        ])
        for fu in qs:
            writer.writerow([
                fu.id, fu.title, fu.description, fu.type, fu.priority, fu.status,
                fu.due_date, fu.reminder_time, fu.assigned_to,
                fu.recurring_enabled, fu.recurring_frequency, fu.recurring_interval,
                fu.contact_name, fu.deal_title, fu.notes,
                ', '.join(fu.tags) if fu.tags else '',
                fu.created_at,
            ])
        return response

    @action(detail=False, methods=['get'])
    def contacts_dropdown(self, request):
        from crmapp.crm.contacts.models import Contact
        contacts = Contact.objects.filter(created_by=request.user, status='active').values(
            'id', 'name', 'avatar', 'email'
        ).order_by('name')
        return Response(list(contacts))

    @action(detail=False, methods=['get'])
    def deals_dropdown(self, request):
        from crmapp.crm.deals.models import Deal
        deals = Deal.objects.filter(created_by=request.user).values('id', 'title', 'stage').order_by('title')
        return Response(list(deals))