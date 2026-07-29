# audit/views.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from . import services
from crmapp.system.roles.permissions import can


class AuditLogViewSet(ViewSet):
    """
    GET /api/system/audit/logs/        → All Logs (merged from all sources)
    GET /api/system/audit/logs/{id}/   → Single log detail
    GET /api/system/audit/logs/stats/  → Today severity counts
    """
    permission_classes = [can('settings', 'view')]

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_filters(self, request):
        p = request.query_params
        return {
            'action':    p.get('action'),
            'module':    p.get('module'),
            'severity':  p.get('severity'),
            'user_id':   p.get('user_id'),
            'date_from': p.get('date_from'),
            'date_to':   p.get('date_to'),
            'search':    p.get('search'),
            # ✅ ADDED: Pass current user for multi-tenancy filtering in services.py
            'request_user': request.user 
        }

    def _paginate(self, request, data: list) -> Response:
        """
        Manual pagination over a plain list.
        Returns { count, results } — same shape as DRF PageNumberPagination.
        """
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, int(request.query_params.get('page_size', 15)))
        except (TypeError, ValueError):
            page, page_size = 1, 15

        total   = len(data)
        start   = (page - 1) * page_size
        end     = start + page_size
        results = data[start:end]

        return Response({
            'count':   total,
            'results': results,
        })

    # ── list ─────────────────────────────────────────────────────────────────

    def list(self, request):
        """GET /api/system/audit/logs/"""
        filters = self._get_filters(request)
        data    = services.get_audit_logs(filters)
        return self._paginate(request, data)

    # ── retrieve ──────────────────────────────────────────────────────────────

    def retrieve(self, request, pk=None):
        """GET /api/system/audit/logs/{id}/"""
        all_logs = services.get_audit_logs(self._get_filters(request))
        for log in all_logs:
            if str(log['id']) == str(pk):
                return Response(log)
        return Response({'detail': 'Not found.'}, status=404)

    # ── stats ────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """GET /api/system/audit/logs/stats/"""
        return Response(services.get_audit_stats())