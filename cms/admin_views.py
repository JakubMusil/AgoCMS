"""
Custom admin views for AgoCMS.
Provides a modern, clean admin panel without relying on Django's built-in admin.
"""

import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CMSLoginForm,
    CMSRegistrationForm,
    ContentEntityForm,
    PageForm,
    SiteForm,
)
from .models import ContentBlock, ContentEntity, Page, SchemaEntry

User = get_user_model()


# ---------------------------------------------------------------------------
# Authentication views
# ---------------------------------------------------------------------------


def cms_login(request):
    """Custom login page."""
    if request.user.is_authenticated:
        return redirect('cms_admin_dashboard')
    form = CMSLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        next_url = request.GET.get('next', '')
        return redirect(next_url if next_url else 'cms_admin_dashboard')
    return render(request, 'cms/admin/login.html', {'form': form})


def cms_register(request):
    """User registration page."""
    if request.user.is_authenticated:
        return redirect('cms_admin_dashboard')
    form = CMSRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('cms_admin_dashboard')
    return render(request, 'cms/admin/register.html', {'form': form})


def cms_logout(request):
    """Log out and redirect to login."""
    logout(request)
    return redirect('cms_login')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@login_required(login_url='cms_login')
def admin_dashboard(request):
    """Main admin dashboard showing overview stats."""
    site = getattr(request, 'site', None)
    context = {
        'page_count': Page.objects.filter(site=site).count() if site else 0,
        'entity_count': ContentEntity.objects.filter(site=site).count() if site else 0,
        'block_count': ContentBlock.objects.filter(site=site).count() if site else 0,
        'user_count': User.objects.count(),
        'site_count': Site.objects.count(),
        'recent_pages': Page.objects.filter(site=site).order_by('-updated_at')[:5] if site else [],
        'recent_entities': ContentEntity.objects.filter(site=site).order_by('-updated_at')[:5] if site else [],
    }
    return render(request, 'cms/admin/dashboard.html', context)


# ---------------------------------------------------------------------------
# Page management
# ---------------------------------------------------------------------------


@login_required(login_url='cms_login')
def page_list(request):
    """List all pages with hierarchy."""
    site = getattr(request, 'site', None)
    if site:
        pages = Page.objects.filter(site=site).select_related('parent').order_by('sort_order', 'path')
    else:
        pages = Page.objects.none()
    return render(request, 'cms/admin/page_list.html', {'pages': pages})


@login_required(login_url='cms_login')
def page_create(request):
    """Create a new page."""
    site = getattr(request, 'site', None)
    form = PageForm(request.POST or None, site=site)
    if request.method == 'POST' and form.is_valid():
        page = form.save(commit=False)
        page.site = site
        page.save()
        return redirect('cms_admin_page_list')
    return render(request, 'cms/admin/page_form.html', {'form': form, 'action': 'Create'})


@login_required(login_url='cms_login')
def page_edit(request, pk):
    """Edit an existing page."""
    site = getattr(request, 'site', None)
    page = get_object_or_404(Page, pk=pk, site=site)
    form = PageForm(request.POST or None, instance=page, site=site)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('cms_admin_page_list')
    return render(request, 'cms/admin/page_form.html', {
        'form': form,
        'page': page,
        'action': 'Edit',
    })


@login_required(login_url='cms_login')
@require_POST
def page_delete(request, pk):
    """Delete a page."""
    site = getattr(request, 'site', None)
    page = get_object_or_404(Page, pk=pk, site=site)
    page.delete()
    return redirect('cms_admin_page_list')


# ---------------------------------------------------------------------------
# Content Entity management
# ---------------------------------------------------------------------------


@login_required(login_url='cms_login')
def entity_list(request):
    """List all content entities."""
    site = getattr(request, 'site', None)
    if site:
        entities = ContentEntity.objects.filter(site=site).order_by('-updated_at')
    else:
        entities = ContentEntity.objects.none()
    return render(request, 'cms/admin/entity_list.html', {'entities': entities})


@login_required(login_url='cms_login')
def entity_create(request):
    """Create a new content entity."""
    site = getattr(request, 'site', None)
    form = ContentEntityForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        entity = form.save(commit=False)
        entity.site = site
        entity.save()
        return redirect('cms_admin_entity_list')
    return render(request, 'cms/admin/entity_form.html', {'form': form, 'action': 'Create'})


@login_required(login_url='cms_login')
def entity_edit(request, pk):
    """Edit an existing content entity."""
    site = getattr(request, 'site', None)
    entity = get_object_or_404(ContentEntity, pk=pk, site=site)
    form = ContentEntityForm(request.POST or None, instance=entity)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('cms_admin_entity_list')
    return render(request, 'cms/admin/entity_form.html', {
        'form': form,
        'entity': entity,
        'action': 'Edit',
    })


@login_required(login_url='cms_login')
@require_POST
def entity_delete(request, pk):
    """Delete a content entity."""
    site = getattr(request, 'site', None)
    entity = get_object_or_404(ContentEntity, pk=pk, site=site)
    entity.delete()
    return redirect('cms_admin_entity_list')


# ---------------------------------------------------------------------------
# User management (staff only)
# ---------------------------------------------------------------------------


@login_required(login_url='cms_login')
def user_list(request):
    """List all users."""
    if not request.user.is_staff:
        return redirect('cms_admin_dashboard')
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'cms/admin/user_list.html', {'users': users})


@login_required(login_url='cms_login')
@require_POST
def user_toggle_staff(request, pk):
    """Toggle staff status for a user."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    user = get_object_or_404(User, pk=pk)
    if user != request.user:
        user.is_staff = not user.is_staff
        user.save()
    return redirect('cms_admin_user_list')


@login_required(login_url='cms_login')
@require_POST
def user_toggle_active(request, pk):
    """Toggle active status for a user."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    user = get_object_or_404(User, pk=pk)
    if user != request.user:
        user.is_active = not user.is_active
        user.save()
    return redirect('cms_admin_user_list')


# ---------------------------------------------------------------------------
# Site management (staff only)
# ---------------------------------------------------------------------------


@login_required(login_url='cms_login')
def site_list(request):
    """List all sites."""
    if not request.user.is_staff:
        return redirect('cms_admin_dashboard')
    sites = Site.objects.all().order_by('domain')
    return render(request, 'cms/admin/site_list.html', {'sites': sites})


@login_required(login_url='cms_login')
def site_create(request):
    """Create a new site."""
    if not request.user.is_staff:
        return redirect('cms_admin_dashboard')
    form = SiteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('cms_admin_site_list')
    return render(request, 'cms/admin/site_form.html', {'form': form, 'action': 'Create'})


@login_required(login_url='cms_login')
def site_edit(request, pk):
    """Edit an existing site."""
    if not request.user.is_staff:
        return redirect('cms_admin_dashboard')
    site_obj = get_object_or_404(Site, pk=pk)
    form = SiteForm(request.POST or None, instance=site_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('cms_admin_site_list')
    return render(request, 'cms/admin/site_form.html', {
        'form': form,
        'site_obj': site_obj,
        'action': 'Edit',
    })


@login_required(login_url='cms_login')
@require_POST
def site_delete(request, pk):
    """Delete a site."""
    if not request.user.is_staff:
        return redirect('cms_admin_dashboard')
    site_obj = get_object_or_404(Site, pk=pk)
    site_obj.delete()
    return redirect('cms_admin_site_list')
