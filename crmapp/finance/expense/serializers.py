from rest_framework import serializers
from .models import ExpenseCategory, ExpenseClaim


class ExpenseCategorySerializer(serializers.ModelSerializer):
    remaining_budget = serializers.ReadOnlyField()
    utilization_pct  = serializers.ReadOnlyField()
    children_count   = serializers.SerializerMethodField()
    gl_account_name  = serializers.SerializerMethodField()

    class Meta:
        model  = ExpenseCategory
        fields = ['id','name','code','parent','level','gl_account','gl_account_name',
                  'budget','spent','remaining_budget','utilization_pct','children_count']

    def get_children_count(self, obj): return obj.children.count()
    def get_gl_account_name(self, obj): return str(obj.gl_account) if obj.gl_account else None

    def create(self, validated_data):
        parent = validated_data.get('parent')
        validated_data['level'] = (parent.level + 1) if parent else 0
        return super().create(validated_data)


class ExpenseCategoryTreeSerializer(ExpenseCategorySerializer):
    children = serializers.SerializerMethodField()

    class Meta(ExpenseCategorySerializer.Meta):
        fields = ExpenseCategorySerializer.Meta.fields + ['children']

    def get_children(self, obj):
        return ExpenseCategoryTreeSerializer(obj.children.all(), many=True).data


class ExpenseClaimSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    category_code = serializers.SerializerMethodField()

    class Meta:
        model  = ExpenseClaim
        fields = ['id','employee','employee_name','category','category_name','category_code',
                  'amount','date','status','receipt','notes','created_at','updated_at']
        read_only_fields = ['created_at','updated_at']

    def get_employee_name(self, obj): return obj.employee.name
    def get_category_name(self, obj): return obj.category.name
    def get_category_code(self, obj): return obj.category.code