# -*- coding: utf-8 -*-

from django.conf import settings
from appconf import AppConf


class SofortPaymentAppConf(AppConf):
    PROJECT_ID = None
    CUSTOMER_NUMBER = None
    API_KEY = None
    CURRENCY = 'EUR'
    ENABLE_CUSTOMER_PROTECTION = True
    API_ENDPOINT = 'https://api.sofort.com/api/xml'

    class Meta:
        prefix = 'SHOP_SOFORT'
