#-*- coding: utf-8 -*-

from django.db import models
from django.utils.formats import date_format
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from shop.models import Order


class SofortTransaction(models.Model):
    order = models.ForeignKey(Order, verbose_name=_('Order'), unique=True)
    transaction_number = models.CharField(_('Transaction number'), max_length=255)
    status = models.CharField(_('Status'), max_length=100, default='')
    status_reason = models.CharField(_('Status Reason'), max_length=100, default='')
    payment_method = models.CharField(_('Payment method'), max_length=100, default='')
    sender = models.TextField(_('Sender'), default='')
    recipient = models.TextField(_('Recipient'), default='')

    created_at = models.DateTimeField(default=now)

    def update_from_dict(self, data, save=True):
        self.status = data['status']
        self.status_reason = data['status_reason']
        self.payment_method = data['payment_method']
        self.sender = '%(holder)s\nAccount Number: %(account_number)s\nBank Code: %(bank_code)s\nBank Name: %(bank_name)s\nBIC: %(bic)s\nIBAN: %(iban)s\nCountry: %(country_code)s' % data['sender']
        self.recipient = '%(holder)s\nAccount Number: %(account_number)s\nBank Code: %(bank_code)s\nBank Name: %(bank_name)s\nBIC: %(bic)s\nIBAN: %(iban)s\nCountry: %(country_code)s' % data['recipient']
        if save:
            self.save()

    def get_status_text(self):
        '\n'.join('%s: %s (%s)' % (date_format(item.created_at, 'SHORT_DATETIME_FORMAT'), item.status, item.reason) for item in self.stati.all())

    def __unicode__(self):
        return u'%s (%s)' % (self.transaction_number, self.order_id)

    class Meta:
        verbose_name = _('Sofort Transaction')
        verbose_name_plural = _('Sofort Transactions')


class TransactionStatus(models.Model):
    transaction = models.ForeignKey(SofortTransaction, related_name='stati')
    status = models.CharField(_('Status'), max_length=20)
    reason = models.CharField(_('Reason'), max_length=50)

    created_at = models.DateTimeField(default=now)

    class Meta:
        verbose_name = _('transaction status')
        verbose_name_plural = _('transaction stati')
        ordering = ('-created_at',)
