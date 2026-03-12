"""
CMS internal API URLs for AgoCMS.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('toggle-edit-mode/', views.toggle_edit_mode, name='cms_toggle_edit_mode'),
    path('save-block/', views.save_block, name='cms_save_block'),
    path('save-list-block/', views.save_list_block, name='cms_save_list_block'),
    path('schema/', views.get_schema_view, name='cms_schema'),
    path('live-preview/', views.live_preview, name='cms_live_preview'),
]
