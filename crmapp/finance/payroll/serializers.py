from rest_framework import serializers
from .models import PayrollRun, PayrollLine

# ✅ FIXED: ab fake Employee serializer nahi banta yahan.
#    HRM ka asli EmployeeListSerializer import karo.
from crmapp.serializers import EmployeeListSerializer
from crmapp.models import Employee


class PayrollLineSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_dept = serializers.SerializerMethodField()

    # Frontend "employee" field mein UUID bhejega
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())

    class Meta:
        model  = PayrollLine
        fields = ['id', 'run', 'employee', 'employee_name', 'employee_dept',
                  'basic', 'allowances', 'deductions', 'tax', 'net_pay']

    def get_employee_name(self, obj):
        return obj.employee.full_name or obj.employee.name

    def get_employee_dept(self, obj):
        return obj.employee.department.name if obj.employee.department else None


class PayrollRunSerializer(serializers.ModelSerializer):
    lines_count = serializers.SerializerMethodField()

    class Meta:
        model  = PayrollRun
        fields = ['id', 'month', 'status', 'total_gross', 'total_net', 'total_tax',
                  'created_at', 'updated_at', 'lines_count']
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def get_lines_count(self, obj):
        return obj.lines.count()


class PayrollRunDetailSerializer(PayrollRunSerializer):
    lines = PayrollLineSerializer(many=True, read_only=True)

    class Meta(PayrollRunSerializer.Meta):
        fields = PayrollRunSerializer.Meta.fields + ['lines']


# ─────────────────────────────────────────────────────────────────────────
# NOTE: Agar payroll module mein abhi bhi "employees/" list endpoint chahiye
# (taaki frontend dropdown bana sake), woh HRM ka EmployeeListSerializer
# directly reuse karega — alag se nahi banana.
# views.py mein EmployeeListCreateView /EmployeeDetailView hata diye gaye hain,
# kyunke HRM mein already /api/employees/ maujood hai.
# ─────────────────────────────────────────────────────────────────────────