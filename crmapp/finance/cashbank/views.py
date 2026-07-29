from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import BankAccount, CashAccount, Transaction, Cheque, BankReconciliation
from .serializers import (BankAccountSerializer, CashAccountSerializer, TransactionSerializer, ChequeSerializer, BankReconciliationSerializer)
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


class BankAccountListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = BankAccount.objects.filter(created_by_id__in=owner_ids)
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        return Response({'count':qs.count(),'results':BankAccountSerializer(qs,many=True).data})
    def post(self, request):
        s = BankAccountSerializer(data=request.data)
        if s.is_valid(): return Response(BankAccountSerializer(services.create_bank_account(s.validated_data, user=request.user)).data, status=201)
        return Response(s.errors, status=400)

class BankAccountDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: bank = BankAccount.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        return Response(BankAccountSerializer(bank).data)
    def patch(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: bank = BankAccount.objects.get(pk=pk, created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        s = BankAccountSerializer(bank, data=request.data, partial=True)
        if s.is_valid(): s.save(); return Response(BankAccountSerializer(bank).data)
        return Response(s.errors, status=400)

class TransactionListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Transaction.objects.filter(bank_account__created_by_id__in=owner_ids).select_related('bank_account')
        if b := request.query_params.get('bank'):    qs = qs.filter(bank_account_id=b)
        if t := request.query_params.get('type'):    qs = qs.filter(type=t)
        if q := request.query_params.get('search'):  qs = qs.filter(Q(description__icontains=q)|Q(reference__icontains=q))
        return Response({'count':qs.count(),'results':TransactionSerializer(qs,many=True).data})
    def post(self, request):
        owner_ids = get_owner_ids(request.user)
        s = TransactionSerializer(data=request.data)
        if s.is_valid():
            try: bank = BankAccount.objects.get(pk=request.data['bank_account'], created_by_id__in=owner_ids)
            except: return Response({'error':'Bank not found.'}, status=404)
            tx = services.record_transaction(bank, s.validated_data['type'], s.validated_data['amount'], s.validated_data['date'], s.validated_data['description'], s.validated_data.get('method',''), s.validated_data.get('reference',''), s.validated_data.get('category',''))
            return Response(TransactionSerializer(tx).data, status=201)
        return Response(s.errors, status=400)

class ChequeListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = Cheque.objects.filter(bank_account__created_by_id__in=owner_ids).select_related('bank_account')
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        return Response({'count':qs.count(),'results':ChequeSerializer(qs,many=True).data})
    def post(self, request):
        s = ChequeSerializer(data=request.data)
        if s.is_valid(): s.save(); return Response(s.data, status=201)
        return Response(s.errors, status=400)

class ChequeStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        owner_ids = get_owner_ids(request.user)
        try: cheque = Cheque.objects.get(pk=pk, bank_account__created_by_id__in=owner_ids)
        except: return Response({'error':'Not found.'}, status=404)
        new_status = request.data.get('status')
        if not new_status: return Response({'error':'status required.'}, status=400)
        return Response(ChequeSerializer(services.update_cheque_status(cheque, new_status)).data)

class ReconciliationListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = BankReconciliation.objects.filter(bank_account__created_by_id__in=owner_ids)
        if b := request.query_params.get('bank'):   qs = qs.filter(bank_account_id=b)
        if s := request.query_params.get('status'): qs = qs.filter(status=s)
        return Response({'count':qs.count(),'results':BankReconciliationSerializer(qs,many=True).data})
    def post(self, request):
        s = BankReconciliationSerializer(data=request.data)
        if s.is_valid(): s.save(); return Response(s.data, status=201)
        return Response(s.errors, status=400)

class CashAccountListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        owner_ids = get_owner_ids(request.user)
        qs = CashAccount.objects.filter(created_by_id__in=owner_ids)
        return Response({'count':qs.count(),'results':CashAccountSerializer(qs,many=True).data})
    def post(self, request):
        s = CashAccountSerializer(data=request.data)
        if s.is_valid(): s.save(created_by=request.user); return Response(s.data, status=201)
        return Response(s.errors, status=400)