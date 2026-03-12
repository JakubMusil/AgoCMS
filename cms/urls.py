"""
CMS page routing URLs for AgoCMS.
Catch-all pattern to dispatch page or entity views.
"""

from django.urls import path, re_path
from . import views

urlpatterns = [
    # Catch-all: pass everything to the cms_page dispatcher
    re_path(r'^(?P<path>.*)$', views.cms_page, name='cms_page'),
]
