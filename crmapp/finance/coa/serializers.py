from rest_framework import serializers
from .models import Account, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    by_username = serializers.SerializerMethodField()

    class Meta:
        model  = AuditLog
        fields = ['id','account','action','field','old_value','new_value','by','by_username','at']
        read_only_fields = ['at']

    def get_by_username(self, obj):
        return obj.by.username if obj.by else None


class AccountSerializer(serializers.ModelSerializer):
    parent_name         = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    budget_utilization  = serializers.SerializerMethodField()
    children_count      = serializers.SerializerMethodField()
    balance              = serializers.SerializerMethodField()   # ✅ FIX: ab live-computed hai, stored field pe depend nahi

    class Meta:
        model  = Account
        fields = ['id','code','name','type','parent','parent_name','level',
                  'balance','budget','budget_utilization','currency','status',
                  'linked_module','note','created_by','created_by_username',
                  'created_at','updated_at','children_count']
        # ✅ FIX: 'created_by' ko read_only kar diya taake koi hack na kar sake
        read_only_fields = ['created_at','updated_at','level', 'created_by']

    def get_parent_name(self, obj):        return str(obj.parent) if obj.parent else None
    def get_created_by_username(self, obj):return obj.created_by.username if obj.created_by else None
    def get_budget_utilization(self, obj): return obj.budget_utilization_pct
    def get_children_count(self, obj):     return obj.children.count()
    def get_balance(self, obj):            return obj.get_computed_balance()   # ✅ FIX: live-computed balance

    def validate_code(self, value):
        qs = Account.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Account code already exists.")
        return value

    def create(self, validated_data):
        parent = validated_data.get('parent')
        validated_data['level'] = (parent.level + 1) if parent else 0
        return super().create(validated_data)

    def update(self, instance, validated_data):
        parent = validated_data.get('parent', instance.parent)
        validated_data['level'] = (parent.level + 1) if parent else 0
        return super().update(instance, validated_data)


class AccountDetailSerializer(AccountSerializer):
    audit_logs = AuditLogSerializer(many=True, read_only=True)
    children   = serializers.SerializerMethodField()

    class Meta(AccountSerializer.Meta):
        fields = AccountSerializer.Meta.fields + ['audit_logs','children']

    def get_children(self, obj):
        return AccountSerializer(obj.children.all(), many=True).data


class AccountTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    balance  = serializers.SerializerMethodField()   # ✅ FIX: live-computed, Trial Balance/COA tree yehi use karte hain

    class Meta:
        model  = Account
        fields = ['id','code','name','type','level','balance','budget','currency','status','linked_module','children']

    def get_balance(self, obj):
        return obj.get_computed_balance()

    def get_children(self, obj):
        return AccountTreeSerializer(obj.children.all(), many=True).data