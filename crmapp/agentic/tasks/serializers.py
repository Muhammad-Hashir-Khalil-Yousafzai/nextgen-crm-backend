from rest_framework import serializers
from .models import (
    Task, TaskDependency, Goal, GoalTemplate, 
    TaskExecutionHistory, Resource, BottleneckAlert, MonthlyPerformance
)

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaskDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskDependency
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class GoalSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Goal
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'parsing_time_ms']


class GoalParseRequestSerializer(serializers.Serializer):
    goal_text = serializers.CharField(max_length=1000)
    use_template = serializers.BooleanField(default=False)
    template_id = serializers.CharField(max_length=50, required=False, allow_blank=True)


class GoalParseResponseSerializer(serializers.Serializer):
    goal_id = serializers.CharField()
    parsed_goal = serializers.CharField()
    tasks = serializers.ListField()
    parsing_time_ms = serializers.IntegerField()
    generated_at = serializers.DateTimeField()


class GoalTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalTemplate
        fields = '__all__'
        read_only_fields = ['id', 'usage_count', 'created_at', 'updated_at']


class TaskExecutionHistorySerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source='task.name', read_only=True)
    
    class Meta:
        model = TaskExecutionHistory
        fields = '__all__'
        read_only_fields = ['id']


class ResourceSerializer(serializers.ModelSerializer):
    current_tasks_count = serializers.IntegerField(source='current_tasks.count', read_only=True)
    
    class Meta:
        model = Resource
        fields = '__all__'
        read_only_fields = ['id', 'last_heartbeat']


class BottleneckAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = BottleneckAlert
        fields = '__all__'
        read_only_fields = ['id', 'detected_at']


class MonthlyPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyPerformance
        fields = '__all__'
        read_only_fields = ['id']