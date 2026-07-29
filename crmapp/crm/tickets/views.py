from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.utils import timezone
import csv
from django.http import HttpResponse

from .models import Ticket, TicketReply
from .serializers import TicketSerializer, TicketReplySerializer


class TicketViewSet(viewsets.ModelViewSet):
    queryset           = Ticket.objects.prefetch_related('replies').all()
    serializer_class   = TicketSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("VALIDATION ERRORS:", serializer.errors)
            return Response(serializer.errors, status=400)
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(subject__icontains=search)       |
                Q(ticket_number__icontains=search) |
                Q(customer_name__icontains=search)
            )

        status_f   = self.request.query_params.get('status')
        priority_f = self.request.query_params.get('priority')
        category_f = self.request.query_params.get('category')
        agent_f    = self.request.query_params.get('assigned_to')

        if status_f:   qs = qs.filter(status=status_f)
        if priority_f: qs = qs.filter(priority=priority_f)
        if category_f: qs = qs.filter(category=category_f)
        if agent_f:    qs = qs.filter(assigned_to=agent_f)

        sort = self.request.query_params.get('sort', 'createdAt')
        sort_map = {
            'createdAt': '-created_at',
            'oldest':    'created_at',
            'priority':  'priority',
        }
        if sort != 'sla':
            qs = qs.order_by(sort_map.get(sort, '-created_at'))

        return qs

    def _priority_order(self, ticket):
        return {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}.get(ticket.priority, 9)

    def _sla_order(self, ticket):
        return {'breached': 0, 'at_risk': 1, 'ok': 2, 'met': 3}.get(ticket.sla_status, 9)

    def list(self, request, *args, **kwargs):
        qs   = self.get_queryset()
        sort = request.query_params.get('sort', 'createdAt')

        tickets = list(qs)
        if sort == 'priority':
            tickets.sort(key=self._priority_order)
        elif sort == 'sla':
            tickets.sort(key=self._sla_order)

        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['patch'])
    def change_status(self, request, pk=None):
        ticket     = self.get_object()
        new_status = request.data.get('status')
        if new_status not in dict(Ticket.STATUS_CHOICES):
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)

        ticket.status = new_status
        if new_status == 'resolved' and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save()
        return Response(TicketSerializer(ticket).data)

    @action(detail=False, methods=['post'])
    def bulk_resolve(self, request):
        ids = request.data.get('ids', [])
        tickets = Ticket.objects.filter(id__in=ids, created_by=request.user)
        tickets.update(status='resolved', resolved_at=timezone.now(), updated_at=timezone.now())
        return Response({'updated': tickets.count()})

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        deleted, _ = Ticket.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'deleted': deleted})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs      = Ticket.objects.filter(created_by=request.user)
        tickets = list(qs)

        open_qs = qs.filter(status='open')
        return Response({
            'total':        qs.count(),
            'open':         open_qs.count(),
            'in_progress':  qs.filter(status='in_progress').count(),
            'resolved':     qs.filter(status__in=['resolved', 'closed']).count(),
            'unresponded':  open_qs.filter(first_response_at__isnull=True).count(),
            'sla_breached': sum(1 for t in tickets if t.sla_status == 'breached'),
            'sla_at_risk':  sum(1 for t in tickets if t.sla_status == 'at_risk'),
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        tickets  = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tickets.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Ticket #', 'Subject', 'Category', 'Priority', 'Status',
            'Source', 'Customer', 'Email', 'Assigned To',
            'SLA Status', 'First Response', 'Resolved At', 'Created At',
        ])
        for t in tickets:
            writer.writerow([
                t.ticket_number, t.subject, t.category, t.priority, t.status,
                t.source, t.customer_name, t.customer_email, t.assigned_name,
                t.sla_status, t.first_response_at, t.resolved_at, t.created_at,
            ])
        return response


class TicketReplyViewSet(viewsets.ModelViewSet):
    queryset           = TicketReply.objects.all()
    serializer_class   = TicketReplySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs        = super().get_queryset().filter(ticket__created_by=self.request.user)
        ticket_id = self.request.query_params.get('ticket')
        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)