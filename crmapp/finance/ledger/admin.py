from django.contrib import admin
from .models import JournalEntry, JournalLine


class JournalLineInline(admin.TabularInline):
    model = JournalLine; extra = 2; raw_id_fields = ('account',)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display  = ('id','date','reference','description','source','status','locked','created_at')
    list_filter   = ('status','source','locked'); search_fields = ('reference','description')
    readonly_fields = ('locked','created_at','updated_at'); inlines = [JournalLineInline]

    def has_change_permission(self, request, obj=None):
        if obj and obj.locked: return False
        return super().has_change_permission(request, obj)


@admin.register(JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    list_display  = ('entry','account','debit','credit','description')
    list_filter   = ('entry__status','entry__source')
    search_fields = ('account__code','account__name','description')
    raw_id_fields = ('entry','account')