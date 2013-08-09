#-*- coding: utf-8 -*-

import xmltodict
from django.conf.urls import patterns, url
from django.db import models
from django.core.urlresolvers import reverse
from django.core import signing
from django.http import (HttpResponseBadRequest, HttpResponse,
    HttpResponseRedirect, Http404)
from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.utils.translation import get_language, ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from .models import SofortTransaction, TransactionStatus
from .conf import settings
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

