"""
crmapp/agentic/tasks/views.py

FIXES APPLIED:
  Bug 3  — GoalViewSet.execute() now wraps execute_goal_tasks.delay() inside
            transaction.on_commit(). Previously the Celery worker could wake
            up before Django committed goal.status="ready" to the DB, read
            the old status ("completed" / "failed"), hit the atomic duplicate
            guard (updated=0), and immediately abort with "Goal already X".
            on_commit() guarantees the worker only starts after the transaction
            is fully visible in the DB.

  Bug 10 — ResourceViewSet.create_agent() was calling AgentBuilderService
            (tasks app) which stores role/goal only in metadata, not in the
            Resource model fields. The frontend Agent Builder form POSTs to
            /api/agentic/tasks/resources/create_agent/ (this endpoint), but
            it needs the same logic as the agents-app endpoint so that
            build_crewai_agent() finds non-empty role/goal at model-field
            level 1. Fix: delegate to AgentBuilderService.create_agent() but
            now that service sets model fields correctly (see tasks/services.py
            Bug 7 fix). The metadata_extra dict from the request body is also
            now forwarded so color (Bug 15) is respected.

  Bug 2  — GoalViewSet.tasks() action was filtering with metadata__goal_id=goal.id
            (UUID object) instead of metadata__goal_id=str(goal.id). JSON key
            lookups in Django require the value to be a string; using the UUID
            object produces no results. Fixed to str(goal.id) — consistent
            with every other filter in this file and in services.py.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import transaction
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
import logging

from .models import (
    Task, TaskDependency, Goal, GoalTemplate,
    TaskExecutionHistory, Resource, BottleneckAlert, MonthlyPerformance
)
from .serializers import (
    TaskSerializer, TaskDependencySerializer, GoalSerializer,
    GoalParseRequestSerializer, GoalParseResponseSerializer,
    GoalTemplateSerializer, TaskExecutionHistorySerializer,
    ResourceSerializer, BottleneckAlertSerializer, MonthlyPerformanceSerializer
)
from .services import TaskPlanningService, GroqGoalParserService, AgentBuilderService

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Task ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().order_by('-updated_at')
    serializer_class = TaskSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        dept_filter = self.request.query_params.get('dept')
        if dept_filter:
            queryset = queryset.filter(dept=dept_filter)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(assignee__icontains=search)
            )
        return queryset

    @action(detail=False, methods=['get'])
    def stats(self, request):
        total       = Task.objects.count()
        by_status   = Task.objects.values('status').annotate(count=Count('status'))
        by_priority = Task.objects.values('priority').annotate(count=Count('priority'))
        by_dept     = Task.objects.values('dept').annotate(count=Count('dept'))
        return Response({
            'total':       total,
            'by_status':   {item['status']:   item['count'] for item in by_status},
            'by_priority': {item['priority']: item['count'] for item in by_priority},
            'by_dept':     {item['dept']:     item['count'] for item in by_dept},
        })

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a single task using CrewAI."""
        service = TaskPlanningService()
        result  = service.execute_task(pk)
        return Response(result)


# ─────────────────────────────────────────────────────────────────────────────
# Goal ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class GoalViewSet(viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def parse(self, request):
        """Parse a goal using Groq API."""
        serializer = GoalParseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            service = TaskPlanningService()
            goal    = service.create_goal_from_input(
                goal_text   = serializer.validated_data['goal_text'],
                user        = request.user if request.user.is_authenticated else None,
                template_id = serializer.validated_data.get('template_id'),
            )
            response_serializer = GoalParseResponseSerializer({
                'goal_id':        goal.id,
                'parsed_goal':    goal.parsed_goal,
                'tasks':          goal.structured_tasks,
                'parsing_time_ms': goal.parsing_time_ms,
                'generated_at':   goal.created_at,
            })
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Goal parsing failed: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        """
        POST /api/agentic/tasks/goals/{id}/execute/
        Resets goal + tasks then triggers Celery execution.

        BUG 3 FIX — transaction.on_commit:
        ------------------------------------
        Old code:
            goal.status = "ready"
            goal.save()                          # commits transaction
            execute_goal_tasks.delay(str(goal.id))  # dispatches Celery

        The problem: on_commit hasn't fired yet when .delay() is called,
        but more critically the worker can start and hit the DB *before*
        the Django request transaction commits (connection pooling, async
        worker startup on Windows solo pool). The atomic guard in
        _run_goal_execution sees the old status and aborts.

        Fix: wrap .delay() in transaction.on_commit() so the worker is
        only queued after the DB transaction containing the status="ready"
        write is fully committed and visible to all connections.

        Also: _dispatched_by_view flag is set BEFORE goal.save() so the
        post_save signal (which fires synchronously inside save()) reads
        it and skips its own dispatch, leaving exactly one dispatch path.
        """
        try:
            goal = self.get_object()

            if goal.status not in ["ready", "parsed", "completed", "failed", "executing"]:
                return Response(
                    {"error": f"Goal is currently '{goal.status}'. Wait for parsing to complete."},
                    status=400,
                )

            if not goal.structured_tasks:
                return Response(
                    {"error": "No tasks found in this goal. Parse it first."},
                    status=400,
                )

            # Set flag BEFORE save() — signal fires synchronously inside
            # save() so the flag must already be in metadata when it fires.
            goal.metadata["_dispatched_by_view"] = True
            goal.metadata.pop("execution_summary", None)
            goal.status = "ready"

            # Both the flag write and status change commit in one transaction.
            goal.save(update_fields=["status", "metadata"])
            # ↑ post_save signal fires here but sees _dispatched_by_view=True
            #   and skips its own execute_goal_tasks.delay() call.

            # Reset all tasks to clean state for re-execution
            tasks = Task.objects.filter(metadata__goal_id=str(goal.id))
            for task in tasks:
                task.status   = "ready" if not task.depends_on_id else "blocked"
                task.progress = 0
                task.metadata.pop("failure_reason", None)
                task.metadata.pop("agent_result", None)
                task.metadata.pop("fallback_note", None)
                task.save(update_fields=["status", "progress", "metadata"])

            # BUG 3 FIX: capture goal.id in a local variable so the lambda
            # closure doesn't hold a reference to `goal` (which might be
            # garbage-collected or have stale state by commit time).
            goal_id_str = str(goal.id)

            # Dispatch AFTER the transaction commits — worker is guaranteed
            # to see status="ready" when it reads the DB.
            from crmapp.agentic.agents.tasks import execute_goal_tasks
            transaction.on_commit(
                lambda: execute_goal_tasks.delay(goal_id_str)
            )

            return Response({
                "success":    True,
                "goal_id":    goal_id_str,
                "message":    f"Execution started for '{goal.parsed_goal or goal.user_input[:50]}'.",
                "task_count": len(goal.structured_tasks),
            })

        except Exception as e:
            logger.error(f"Goal execute failed: {e}")
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='progress')
    def progress(self, request, pk=None):
        """
        GET /api/agentic/tasks/goals/{id}/progress/
        Returns real-time execution progress.
        """
        try:
            goal  = self.get_object()
            tasks = Task.objects.filter(metadata__goal_id=str(goal.id))

            total     = tasks.count()
            completed = tasks.filter(status="completed").count()
            failed    = tasks.filter(status="failed").count()
            running   = tasks.filter(status="running").count()
            blocked   = tasks.filter(status="blocked").count()
            ready     = tasks.filter(status="ready").count()
            pending   = tasks.filter(status="pending").count()

            progress_pct = int((completed / total) * 100) if total > 0 else 0

            task_statuses = list(tasks.values(
                "id", "name", "status", "progress",
                "assignee", "dept", "actual_duration_ms", "metadata",
            ))

            return Response({
                "goal_id":     str(goal.id),
                "goal_status": goal.status,
                "progress":    progress_pct,
                "total":       total,
                "completed":   completed,
                "failed":      failed,
                "running":     running,
                "blocked":     blocked,
                "ready":       ready,
                "pending":     pending,
                "tasks":       task_statuses,
                "summary":     goal.metadata.get("execution_summary", {}),
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """
        Get all tasks generated from a goal.

        BUG 2 FIX: was metadata__goal_id=goal.id (UUID object).
        JSON key lookups require a string — the UUID object doesn't match
        the stored string value, returning an empty queryset every time.
        """
        goal  = self.get_object()
        # BUG 2 FIX: str(goal.id) — consistent with all other filters
        tasks = Task.objects.filter(metadata__goal_id=str(goal.id))
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Goal Template ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class GoalTemplateViewSet(viewsets.ModelViewSet):
    queryset = GoalTemplate.objects.filter(is_active=True)
    serializer_class = GoalTemplateSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def categories(self, request):
        categories = GoalTemplate.objects.filter(
            is_active=True
        ).exclude(
            category__isnull=True
        ).values_list('category', flat=True).distinct()
        return Response(list(categories))


# ─────────────────────────────────────────────────────────────────────────────
# Task Dependency ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TaskDependencyViewSet(viewsets.ModelViewSet):
    queryset = TaskDependency.objects.all()
    serializer_class = TaskDependencySerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def graph(self, request):
        deps  = TaskDependency.objects.select_related('from_task', 'to_task').all().order_by('-from_task__updated_at')
        nodes = set()
        edges = []
        for dep in deps:
            nodes.add(dep.from_task.id)
            nodes.add(dep.to_task.id)
            edges.append({
                'from':  dep.from_task.id,
                'to':    dep.to_task.id,
                'type':  dep.dependency_type,
                'label': dep.label,
            })
        tasks     = Task.objects.filter(id__in=nodes)
        node_data = [
            {
                'id':       task.id,
                'name':     task.name,
                'status':   task.status,
                'priority': task.priority,
            }
            for task in tasks
        ]
        return Response({'nodes': node_data, 'edges': edges})


# ─────────────────────────────────────────────────────────────────────────────
# Resource ViewSet  (tasks-app agent builder)
# ─────────────────────────────────────────────────────────────────────────────

class ResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Resource model — includes Agent Builder endpoints.

    BUG 10 FIX — create_agent action:
    -----------------------------------
    The frontend Agent Builder form POSTs here
    (POST /api/agentic/tasks/resources/create_agent/). The old code called
    AgentBuilderService which stored role/goal ONLY in metadata, not in
    Resource model fields. build_crewai_agent() in agents/services.py reads
    model fields first, so it got empty strings and silently fell back to
    a generic Groq call.

    Fix: AgentBuilderService.create_agent() now sets the model fields
    explicitly (see tasks/services.py Bug 7 fix). Additionally,
    metadata_extra from the request body is forwarded so color (Bug 15)
    and any extra LLM config the form sends are stored correctly.
    """
    queryset           = Resource.objects.all()
    serializer_class   = ResourceSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def create_agent(self, request):
        """
        POST /api/agentic/tasks/resources/create_agent/
        Creates a custom agent from the Agent Builder form.
        """
        try:
            service  = AgentBuilderService()
            resource = service.create_agent(
                name           = request.data.get('name'),
                role           = request.data.get('role'),
                goal           = request.data.get('goal'),
                backstory      = request.data.get('backstory', ''),
                tools          = request.data.get('tools', []),
                dept           = request.data.get('dept', 'CRM'),
                user           = request.user if request.user.is_authenticated else None,
                # BUG 10 / BUG 15 FIX: forward metadata_extra so color and
                # LLM config from the form are passed through to the service
                metadata_extra = request.data.get('metadata_extra', {}),
            )
            serializer = ResourceSerializer(resource)
            return Response(
                {
                    'success': True,
                    'message': f"Agent '{resource.name}' created successfully",
                    'agent':   serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Agent creation failed: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'])
    def test_agent(self, request, pk=None):
        try:
            service = AgentBuilderService()
            result  = service.test_agent(
                resource_id = pk,
                test_prompt = request.data.get(
                    'prompt', 'Introduce yourself and describe your capabilities'
                ),
            )
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['get'])
    def available_tools(self, request):
        tools = [
            {'name': 'Web Search',    'description': 'Search the web for information using Tavily API', 'requires': 'TAVILY_API_KEY'},
            {'name': 'Email Send',    'description': 'Send emails via Gmail SMTP',                      'requires': 'Gmail credentials'},
            {'name': 'CRM Read',      'description': 'Read data from CRM database',                     'requires': 'None'},
            {'name': 'CRM Write',     'description': 'Write data to CRM database',                      'requires': 'None'},
            {'name': 'Slack Notify',  'description': 'Send Slack notifications via webhook',            'requires': 'SLACK_WEBHOOK_URL'},
            {'name': 'Analytics API', 'description': 'Fetch analytics from CRM database',               'requires': 'None'},
        ]
        return Response(tools)

    @action(detail=True, methods=['post'])
    def heartbeat(self, request, pk=None):
        resource = self.get_object()
        resource.last_heartbeat = timezone.now()
        resource.save()
        return Response({'status': 'ok'})

    @action(detail=False, methods=['get'])
    def custom_agents(self, request):
        custom = Resource.objects.filter(
            type="AI Agent",
            metadata__is_custom=True,
        )
        serializer = ResourceSerializer(custom, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_agent(self, request, pk=None):
        """
        Update an existing agent and clear its cache so it gets rebuilt.
        POST /api/agentic/tasks/resources/{id}/update_agent/
        """
        try:
            resource = self.get_object()
            for field in ['role', 'goal', 'backstory', 'tools', 'color']:
                if field in request.data:
                    setattr(resource, field, request.data[field])
            resource.save()

            # Clear agent cache so next execution rebuilds with new values
            from crmapp.agentic.agents.services import clear_agent_cache
            clear_agent_cache(str(resource.id))

            serializer = ResourceSerializer(resource)
            return Response({'success': True, 'agent': serializer.data})

        except Exception as e:
            logger.error(f"Agent update failed: {e}")
            return Response({'success': False, 'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# Execution History ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = TaskExecutionHistory.objects.all()
    serializer_class   = TaskExecutionHistorySerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def recent(self, request):
        recent     = self.get_queryset()[:50]
        serializer = self.get_serializer(recent, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        last_24h = timezone.now() - timedelta(hours=24)
        recent   = TaskExecutionHistory.objects.filter(started_at__gte=last_24h)
        return Response({
            'total_24h':       recent.count(),
            'success_rate':    recent.filter(status='success').count() / max(recent.count(), 1) * 100,
            'avg_duration_ms': recent.filter(
                duration_ms__isnull=False
            ).aggregate(Avg('duration_ms'))['duration_ms__avg'],
        })


# ─────────────────────────────────────────────────────────────────────────────
# Bottleneck Alert ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class BottleneckAlertViewSet(viewsets.ModelViewSet):
    queryset           = BottleneckAlert.objects.all()
    serializer_class   = BottleneckAlertSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def active(self, request):
        active_alerts = self.get_queryset().filter(resolved_at__isnull=True)
        serializer    = self.get_serializer(active_alerts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.resolved_at     = timezone.now()
        alert.resolution_note = request.data.get('note', '')
        alert.save()
        return Response({'status': 'resolved'})


# ─────────────────────────────────────────────────────────────────────────────
# Monthly Performance ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class MonthlyPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = MonthlyPerformance.objects.all()
    serializer_class   = MonthlyPerformanceSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def current_year(self, request):
        current_year = timezone.now().year
        performance  = self.get_queryset().filter(year=current_year)
        serializer   = self.get_serializer(performance, many=True)
        return Response(serializer.data)