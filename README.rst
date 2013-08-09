========================
django-shop-sofortpayment
========================

This application is a Sofort Bank backend for django-SHOP.

Usage
======

Add this project to your INSTALLED_APPS, and add 
``'shop_sofortpayment.gateway.SofortPaymentBackend',`` to django-SHOP's
``SHOP_PAYMENT_BACKENDS`` setting.


Other settings you might want to adapt::

    SHOP_SOFORT_PROJECT_ID = None
    SHOP_SOFORT_CUSTOMER_NUMBER = None
    SHOP_SOFORT_API_KEY = None
    SHOP_SOFORT_CURRENCY = 'EUR'
    SHOP_SOFORT_ENABLE_CUSTOMER_PROTECTION = True
