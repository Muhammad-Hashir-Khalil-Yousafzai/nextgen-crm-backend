from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import JournalEntry, JournalLine
from .serializers import (JournalEntrySerializer, JournalEntryDetailSerializer, JournalEntryCreateSerializer, JournalLineSerializer)
from . import services

# ── Multi-Tenancy Helper ──────────────────────────────────────────────────────
def get_owner_ids(user):
    if user.is_superuser:
        from crmapp.system.usermanage.models import UserProfile
        sub_user_ids = UserProfile.objects.filter(created_by=user).values_list('user_id', flat=True)
        return list(sub_user_ids) + [user.id]
    try:
        from crmapp.system.usermanage.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        if profile.created_by:
            sub_ids = list(UserProfile.objects.filter(created_by=profile.created_by).values_list('user_id', flat=True))
            sub_ids.append(profile.created_by_id)
            return sub_ids
    except Exception:
        pass
    return [user.id]

class JournalEntryListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = JournalEntry.objects.filter(created_by_id__in=owner_ids)
        if s   := request.query_params.get('status'):    qs = qs.filter(status=s)
        if src := request.query_params.get('source'):    qs = qs.filter(source=src)
        if df  := request.query_params.get('date_from'): qs = qs.filter(date__gte=df)
        if dt  := request.query_params.get('date_to'):   qs = qs.filter(date__lte=dt)
        if q   := request.query_params.get('search'):    qs = qs.filter(Q(description__icontains=q) | Q(reference__icontains=q))
        return Response({'count': qs.count(), 'results': JournalEntrySerializer(qs, many=True).data})

    def post(self, request):
        s = JournalEntryCreateSerializer(data=request.data)
        if s.is_valid():
            entry = s.save(created_by=request.user)
            return Response(JournalEntryDetailSerializer(entry).data, status=201)
        return Response(s.errors, status=400)

class JournalEntryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: entry = JournalEntry.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error': 'Not found.'}, status=404)
        return Response(JournalEntryDetailSerializer(entry).data)

class PostJournalEntryView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: entry = JournalEntry.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error': 'Not found.'}, status=404)
        try:
            updated = services.post_entry(entry)
            return Response(JournalEntryDetailSerializer(updated).data)
        except ValueError as e: return Response({'error': str(e)}, status=400)

class ReverseJournalEntryView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: entry = JournalEntry.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error': 'Not found.'}, status=404)
        date = request.data.get('date')
        if not date: return Response({'error': 'date required for reversal.'}, status=400)
        try:
            reversal = services.reverse_entry(entry, reversal_date=date, description=request.data.get('description', 'Reversal'))
            return Response(JournalEntryDetailSerializer(reversal).data, status=201)
        except ValueError as e: return Response({'error': str(e)}, status=400)

class AccountLedgerView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, account_pk):
        owner_ids = get_owner_ids(request.user)
        from crmapp.finance.coa.models import Account
        try: account = Account.objects.get(pk=account_pk, created_by_id__in=owner_ids)
        except: return Response({'error': 'Account not found.'}, status=404)
        lines = services.get_account_ledger(account, date_from=request.query_params.get('date_from'), date_to=request.query_params.get('date_to'))
        return Response({'account': f"{account.code} - {account.name}", 'count': lines.count(), 'results': JournalLineSerializer(lines, many=True).data})