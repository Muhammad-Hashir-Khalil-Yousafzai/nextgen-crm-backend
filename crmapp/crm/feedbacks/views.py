from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Avg, Count
from django.utils import timezone
import csv
from django.http import HttpResponse

from .models import Survey, SurveyResponse
from .serializers import SurveySerializer, SurveyResponseSerializer


class SurveyViewSet(viewsets.ModelViewSet):
    queryset           = Survey.objects.all()
    serializer_class   = SurveySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(created_by__username__icontains=search)
            )

        status_f = self.request.query_params.get('status')
        if status_f and status_f != 'all':
            qs = qs.filter(status=status_f)

        is_template = self.request.query_params.get('is_template')
        if is_template is not None:
            qs = qs.filter(is_template=is_template in ['true', '1', 'True'])

        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs      = Survey.objects.filter(created_by=request.user)
        active  = qs.filter(status='active')
        all_res = SurveyResponse.objects.filter(survey__created_by=request.user)

        total_resp   = all_res.count()
        positive     = all_res.filter(sentiment_score__gt=0.3).count()
        negative     = all_res.filter(sentiment_score__lt=-0.3).count()
        neutral      = total_resp - positive - negative

        avg_csat = all_res.aggregate(a=Avg('csat_score'))['a']
        avg_nps  = all_res.aggregate(a=Avg('nps_score'))['a']

        return Response({
            'total_surveys':   qs.count(),
            'active_surveys':  active.count(),
            'draft_surveys':   qs.filter(status='draft').count(),
            'closed_surveys':  qs.filter(status='closed').count(),
            'total_responses': total_resp,
            'avg_csat':        round(avg_csat, 1) if avg_csat else None,
            'avg_nps':         round(avg_nps, 1)  if avg_nps  else None,
            'sentiment': {
                'positive': positive,
                'neutral':  neutral,
                'negative': negative,
            },
        })

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        survey   = self.get_object()
        responses = survey.responses.all()
        http_response = HttpResponse(content_type='text/csv')
        http_response['Content-Disposition'] = (
            f'attachment; filename="survey_{survey.id}_responses.csv"'
        )
        writer = csv.writer(http_response)
        writer.writerow([
            'Customer', 'Email', 'CSAT Score', 'NPS Score',
            'Sentiment', 'Tags', 'Submitted At'
        ])
        for r in responses:
            writer.writerow([
                r.customer_name, r.customer_email,
                r.csat_score, r.nps_score,
                r.sentiment_label,
                ', '.join(r.tags),
                r.submitted_at.strftime('%Y-%m-%d %H:%M'),
            ])
        return http_response


class SurveyResponseViewSet(viewsets.ModelViewSet):
    queryset           = SurveyResponse.objects.all()
    serializer_class   = SurveyResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().filter(survey__created_by=self.request.user)

        survey_id = self.kwargs.get('survey_pk') or self.request.query_params.get('survey')
        if survey_id:
            qs = qs.filter(survey_id=survey_id)

        sentiment = self.request.query_params.get('sentiment')
        if sentiment == 'positive': qs = qs.filter(sentiment_score__gt=0.3)
        elif sentiment == 'negative': qs = qs.filter(sentiment_score__lt=-0.3)
        elif sentiment == 'neutral':
            qs = qs.filter(sentiment_score__gte=-0.3, sentiment_score__lte=0.3)

        sort = self.request.query_params.get('sort', 'newest')
        sort_map = {
            'newest':    '-submitted_at',
            'oldest':    'submitted_at',
            'csat_high': '-csat_score',
            'csat_low':  'csat_score',
        }
        return qs.order_by(sort_map.get(sort, '-submitted_at'))

    @action(detail=True, methods=['post'])
    def create_ticket(self, request, pk=None):
        response = self.get_object()
        if response.sentiment_score is None or response.sentiment_score >= -0.3:
            return Response(
                {'detail': 'Ticket creation is intended for negative responses only.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from crmapp.crm.tickets.models import Ticket
        except ImportError:
            return Response(
                {'detail': 'Tickets module not available.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        subject = (
            f"[Feedback] Negative response from {response.customer_name or 'customer'} "
            f"— {response.survey.name}"
        )

        text_answer = next(
            (a['a'] for a in response.answers if len(a.get('a', '')) > 20),
            ', '.join(response.tags) or 'No additional detail provided.'
        )

        ticket = Ticket.objects.create(
            subject        = subject[:500],
            description    = text_answer,
            category       = 'Complaint',
            priority       = 'high',
            status         = 'open',
            source         = 'web',
            contact        = response.contact,
            customer_name  = response.customer_name,
            customer_email = response.customer_email,
            customer_avatar= response.customer_avatar,
            created_by     = request.user
        )

        return Response(
            {'detail': 'Ticket created.', 'ticket_number': ticket.ticket_number},
            status=status.HTTP_201_CREATED
        )