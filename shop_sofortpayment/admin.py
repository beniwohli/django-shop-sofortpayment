#-*- coding: utf-8 -*-
from django.contrib import admin
from models import TransactionStatus, SofortTransaction


class TransactionStatusInline(admin.TabularInline):
    model = TransactionStatus
    readonly_fields = ('status', 'reason', 'created_at')
    can_delete = False
    extra = 0


class TransactionAdmin(admin.ModelAdmin):
    date_hierarchy = 'created_at'
    search_fields = ('order__pk', 'transaction_number')
    readonly_fields = ('order', 'transaction_number', 'created_at', 'payment_method', 'status', 'status_reason', 'sender_html', 'recipient_html')
    list_display = ('order', 'transaction_number', 'created_at')
    inlines = [TransactionStatusInline]

    fields = ('order', 'transaction_number', ('status', 'status_reason'), 'payment_method', 'sender_html', 'recipient_html', 'created_at')

    def sender_html(self, obj):
        return '<br>'.join(obj.sender.split('\n'))
    sender_html.allow_tags = True

    def recipient_html(self, obj):
        return '<br>'.join(obj.recipient.split('\n'))
    recipient_html.allow_tags = True

admin.site.register(SofortTransaction, TransactionAdmin)
