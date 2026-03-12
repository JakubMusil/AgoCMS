"""
URL configuration for the custom AgoCMS admin panel.
"""

from django.urls import path

from . import admin_views

urlpatterns = [
    # Authentication
    path('login/', admin_views.cms_login, name='cms_login'),
    path('register/', admin_views.cms_register, name='cms_register'),
    path('logout/', admin_views.cms_logout, name='cms_logout'),

    # Dashboard
    path('', admin_views.admin_dashboard, name='cms_admin_dashboard'),

    # Pages
    path('pages/', admin_views.page_list, name='cms_admin_page_list'),
    path('pages/create/', admin_views.page_create, name='cms_admin_page_create'),
    path('pages/<int:pk>/edit/', admin_views.page_edit, name='cms_admin_page_edit'),
    path('pages/<int:pk>/delete/', admin_views.page_delete, name='cms_admin_page_delete'),

    # Entities
    path('entities/', admin_views.entity_list, name='cms_admin_entity_list'),
    path('entities/create/', admin_views.entity_create, name='cms_admin_entity_create'),
    path('entities/<int:pk>/edit/', admin_views.entity_edit, name='cms_admin_entity_edit'),
    path('entities/<int:pk>/delete/', admin_views.entity_delete, name='cms_admin_entity_delete'),

    # Users
    path('users/', admin_views.user_list, name='cms_admin_user_list'),
    path('users/<int:pk>/toggle-staff/', admin_views.user_toggle_staff, name='cms_admin_user_toggle_staff'),
    path('users/<int:pk>/toggle-active/', admin_views.user_toggle_active, name='cms_admin_user_toggle_active'),

    # Sites
    path('sites/', admin_views.site_list, name='cms_admin_site_list'),
    path('sites/create/', admin_views.site_create, name='cms_admin_site_create'),
    path('sites/<int:pk>/edit/', admin_views.site_edit, name='cms_admin_site_edit'),
    path('sites/<int:pk>/delete/', admin_views.site_delete, name='cms_admin_site_delete'),
]
