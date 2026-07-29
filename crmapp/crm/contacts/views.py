from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
import csv
import io
from django.http import HttpResponse

from .models import Contact
from .serializers import ContactSerializer


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset().filter(created_by=self.request.user)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(title__icontains=search) |
                Q(company__name__icontains=search) |  # Updated to use FK
                Q(location__icontains=search)
            )

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        location = self.request.query_params.get('location')
        if location:
            queryset = queryset.filter(location=location)

        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(rating__gte=float(min_rating))

        sort_by = self.request.query_params.get('sort', 'recent')
        if sort_by == 'name-asc':
            queryset = queryset.order_by('name')
        elif sort_by == 'name-desc':
            queryset = queryset.order_by('-name')
        elif sort_by == 'rating-high':
            queryset = queryset.order_by('-rating')
        elif sort_by == 'rating-low':
            queryset = queryset.order_by('rating')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def perform_create(self, serializer):
        name = serializer.validated_data.get('name', 'User')
        avatar = serializer.validated_data.get('avatar', '')
        if not avatar:
            seed = name.replace(' ', '')
            avatar = f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}"
        serializer.save(created_by=self.request.user, avatar=avatar)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided'}, status=status.HTTP_400_BAD_REQUEST)
        deleted_count, _ = Contact.objects.filter(id__in=ids, created_by=request.user).delete()
        return Response({'success': True, 'deleted': deleted_count})

    @action(detail=False, methods=['get'])
    def locations(self, request):
        locs = Contact.objects.filter(created_by=request.user).exclude(location='').values_list('location', flat=True).distinct()
        return Response(list(locs))

    @action(detail=False, methods=['get'])
    def export(self, request):
        contacts = self.get_queryset()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contacts.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Title', 'Company', 'Email',
            'Phone', 'Location', 'Rating', 'Status',
            'Tags', 'Last Contact'
        ])

        for c in contacts:
            writer.writerow([
                c.name, c.title, c.company.name if c.company else c.company_name, c.email,
                c.phone, c.location, c.rating, c.status,
                ', '.join(c.tags), c.last_contact or ''
            ])

        return response

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = Contact.objects.filter(created_by=request.user)
        return Response({
            'total': qs.count(),
            'active': qs.filter(status='active').count(),
            'inactive': qs.filter(status='inactive').count(),
        })