#-*- coding: utf-8 -*-
from setuptools import setup, find_packages
import os

CLASSIFIERS = []

setup(
    author="Benjamin Wohlwend",
    author_email="bw@piquadrat.ch",
    name='django-shop-sofortpayment',
    version='0.1',
    description='A Sofort Bank payment backend for django SHOP',
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst')).read(),
    url='https://github.com/piquadrat/django-shop-sofortpayment',
    license='BSD License',
    platforms=['OS Independent'],
    classifiers=CLASSIFIERS,
    install_requires=[
        'Django>=1.4',
        'django-appconf',
        'requests',
    ],
    packages=find_packages(exclude=["example", "example.*"]),
    zip_safe = False
)
