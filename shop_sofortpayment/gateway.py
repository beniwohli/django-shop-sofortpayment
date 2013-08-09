#-*- coding: utf-8 -*-

from django import forms
import xmltodict
from django.conf import settings
from django.conf.urls import patterns, url
from django.db import models
from django.core.urlresolvers import reverse
from django.core import signing
from django.forms.forms import DeclarativeFieldsMetaclass
from django.http import (HttpResponseBadRequest, HttpResponse, 
    HttpResponseRedirect, Http404)
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import get_language, ugettext_lazy as _
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_exempt
from .forms import ValueHiddenInput
from .models import SofortTransaction, TransactionStatus
from .utils import security_check, compute_security_checksum
from .conf import settings
from .models import SofortTransaction
from shop_sofortpayment import __version__
import requests

def absolute_url(request, path):
    return '%s://%s%s' % ('https' if request.is_secure() else 'http', 
                          request.get_host(), path)


class SofortPaymentBackend(object):
    backend_name = "sofort"
    backend_verbose_name = _(u"Sofort Direktüberweisung")
    url_namespace = "sofort"
    
    #===========================================================================
    # Defined by the backends API
    #===========================================================================
    
    def __init__(self, shop):
        self.shop = shop
        self.skip_confirmation = settings.SHOP_SOFORT_SKIP_CONFIRMATION
    
    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^$', self.make_request, name='sofort'),
            url(r'^success/$', self.success, name='sofort_success'),
            url(r'^notify/$', csrf_exempt(self.notify), name='sofort_notify'),
        )
        return urlpatterns

    #===========================================================================
    # Views
    #===========================================================================
    
    def make_request(self, request):
        """
        We need this to be a method and not a function, since we need to have
        a reference to the shop interface
        """
        order = self.shop.get_order(request)
        base_url = '%s://%s' % ('https' if request.is_secure() else 'http', request.get_host())
        signed_order = signing.dumps({'order_id': order.pk})
        xml_request = render_to_string('shop_sofortpayment/xml/new_transaction.xml', {
            'project_id': settings.SHOP_SOFORT_PROJECT_ID,
            'language_code': get_language(),
            'interface_version': 'django-shop-sofortpayment-' + __version__,
            'amount': order.order_total,
            'currency': settings.SHOP_SOFORT_CURRENCY,
            'order_number': order.pk,
            'user_name': order.billing_address_text,
            'success_url': '%s%s?s=%s' % (base_url, reverse('sofort_success'), signed_order),
            'notification_url': '%s%s?s=%s' % (base_url, reverse('sofort_notify'), signed_order),
            'abort_url': base_url + reverse('cart'),
            'customer_protection': '1' if settings.SHOP_SOFORT_ENABLE_CUSTOMER_PROTECTION else '0',
        })
        response = requests.post(
            settings.SHOP_SOFORT_API_ENDPOINT,
            data=xml_request.encode('utf-8'),
            headers={'Content-Type': 'application/xml; charset=UTF-8'},
            auth=(settings.SHOP_SOFORT_CUSTOMER_NUMBER, settings.SHOP_SOFORT_API_KEY),
        )
        if response.status_code == 200:
            doc = xmltodict.parse(response.content)
            transaction = SofortTransaction.objects.create(
                order=order,
                transaction_number=doc['new_transaction']['transaction'],
            )
            return HttpResponseRedirect(doc['new_transaction']['payment_url'])
        return render_to_response("shop_sofortpayment/payment.html", context)
    
    def success(self, request):
        try:
            signed_data = signing.loads(request.GET['s'])
            transaction = SofortTransaction.objects.get(order=signed_data['order_id'])
            data = self.update_transaction(transaction)
            if data['status'] in ('received', 'untraceable'):
                self.shop.confirm_payment(self.shop.get_order_for_id(signed_data['order_id']), data['amount'], transaction.transaction_number, self.backend_name)
            elif data['status'] == 'pending':
                self.shop.confirm_payment(self.shop.get_order_for_id(signed_data['order_id']), '0.00', transaction.transaction_number, self.backend_name)
        except signing.BadSignature:
            return HttpResponseBadRequest('tampered with signed data')
        return HttpResponseRedirect(self.shop.get_finished_url())

    def notify(self, request):
        order_id = signing.loads(request.GET['s'])['order_id']
        notification_type = request.GET['type']
        # Django mangels the posted XML a bit
        xml = '<?xml version=' + request.POST['<?xml version']
        data = xmltodict.parse(xml)
        transaction_id = data['status_notification']['transaction']
        transaction = SofortTransaction.objects.get(transaction_number=transaction_id, order=order_id)
        TransactionStatus.objects.create(transaction=transaction, status=notification_type)
        data = self.update_transaction(transaction)
        return HttpResponse('')

    def update_transaction(self, transaction):
        transaction_request = render_to_string('shop_sofortpayment/xml/transaction_request.xml', {'transactions': [transaction.transaction_number]})
        response = requests.post(
            settings.SHOP_SOFORT_API_ENDPOINT,
            data=transaction_request.encode('utf-8'),
            headers={'Content-Type': 'application/xml; charset=UTF-8'},
            auth=(settings.SHOP_SOFORT_CUSTOMER_NUMBER, settings.SHOP_SOFORT_API_KEY),
        )
        doc = xmltodict.parse(response.content)
        transaction.update_from_dict(doc['transactions']['transaction_details'])
        return doc['transactions']['transaction_details']

    def confirm_payment_data(self, data):
        try:
            valid = security_check(data, settings.POSTFINANCE_SHAOUT_KEY)
        except KeyError:
            valid = False
        if valid:
            order_id = data['orderID']
            try:
                order = self.shop.get_order_for_id(order_id)
            except models.ObjectDoesNotExist:
                raise Http404('Order does not exist on this machine')
            transaction_id = data['PAYID']
            amount = data['amount']
            # Create an IPN transaction trace in the database
            ipn, created = PostfinanceIPN.objects.get_or_create(
                orderID=order_id,
                defaults=dict(
                    currency=data.get('currency', ''),
                    amount=data.get('amount', ''),
                    PM=data.get('PM', ''),
                    ACCEPTANCE=data.get('ACCEPTANCE', ''),
                    STATUS=data.get('STATUS', ''),
                    CARDNO=data.get('CARDNO', ''),
                    CN=data.get('CN', ''),
                    TRXDATE=data.get('TRXDATE', ''),
                    PAYID=data.get('PAYID', ''),
                    NCERROR=data.get('NCERROR', ''),
                    BRAND=data.get('BRAND', ''),
                    IPCTY=data.get('IPCTY', ''),
                    CCCTY=data.get('CCCTY', ''),
                    ECI=data.get('ECI', ''),
                    CVCCheck=data.get('CVCCheck', ''),
                    AAVCheck=data.get('AAVCheck', ''),
                    VC=data.get('VC', ''),
                    IP=data.get('IP', ''),
                    SHASIGN=data.get('SHASIGN', ''),
                )
            )
            if created:
                # This actually records the payment in the shop's database
                self.shop.confirm_payment(order, amount, transaction_id, self.backend_name)

            return True

        else:  # Checksum failed
            return False
