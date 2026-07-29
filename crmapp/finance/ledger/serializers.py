from rest_framework import serializers
from .models import JournalEntry, JournalLine

class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()
    date         = serializers.SerializerMethodField()
    reference    = serializers.SerializerMethodField()

    class Meta:
        model  = JournalLine
        fields = ['id', 'entry', 'account', 'account_code', 'account_name',
                  'debit', 'credit', 'description', 'date', 'reference']
        read_only_fields = ['entry']

    def get_account_code(self, obj): return obj.account.code
    def get_account_name(self, obj): return obj.account.name
    def get_date(self, obj): return obj.entry.date
    def get_reference(self, obj): return obj.entry.reference

    def validate(self, data):
        debit  = data.get('debit',  0)
        credit = data.get('credit', 0)
        if debit > 0 and credit > 0:
            raise serializers.ValidationError("A line cannot have both debit and credit.")
        return data
class JournalEntrySerializer(serializers.ModelSerializer):
    total_debit  = serializers.ReadOnlyField()
    total_credit = serializers.ReadOnlyField()
    is_balanced  = serializers.ReadOnlyField()
    lines_count  = serializers.SerializerMethodField()

    class Meta:
        model  = JournalEntry
        fields = ['id', 'date', 'description', 'reference', 'status', 'source',
                  'locked', 'total_debit', 'total_credit', 'is_balanced',
                  'created_at', 'updated_at', 'lines_count']
        read_only_fields = ['created_at', 'updated_at', 'locked']

    def get_lines_count(self, obj): return obj.lines.count()


class JournalEntryDetailSerializer(JournalEntrySerializer):
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta(JournalEntrySerializer.Meta):
        fields = JournalEntrySerializer.Meta.fields + ['lines']


class JournalEntryCreateSerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True)

    class Meta:
        model  = JournalEntry
        fields = ['date', 'description', 'reference', 'source', 'status', 'lines']

    def validate_lines(self, lines):
        if len(lines) < 2:
            raise serializers.ValidationError("A journal entry needs at least 2 lines.")
        return lines

    def validate(self, data):
        status = data.get('status', 'draft')
        if status == 'posted':
            lines        = data.get('lines', [])
            total_debit  = sum(l.get('debit',  0) for l in lines)
            total_credit = sum(l.get('credit', 0) for l in lines)
            if total_debit != total_credit:
                raise serializers.ValidationError(
                    f"Cannot post an unbalanced entry. Dr {total_debit} ≠ Cr {total_credit}."
                )
        return data

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        target_status = validated_data.get('status', 'draft')
        
        # Pehle entry draft mein create karein
        validated_data['status'] = 'draft'
        entry = JournalEntry.objects.create(**validated_data)
        
        # Lines create karein
        for line in lines_data:
            JournalLine.objects.create(entry=entry, **line)
            
        # ✅ FIX: Agar status posted tha, toh post_entry function call karein taake balances update hon
        if target_status == 'posted':
            from . import services
            services.post_entry(entry)
            entry.refresh_from_db()
            
        return entry