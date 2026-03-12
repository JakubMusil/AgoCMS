"""
CMS Views for AgoCMS.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from .models import ContentBlock, ContentEntity, Page
from .schema_registry import get_schema, reset_registry


# ---------------------------------------------------------------------------
# Page / Entity routing
# ---------------------------------------------------------------------------

def cms_page(request, path=''):
    """
    Main dispatcher for CMS pages.

    1. Try to match a Page object for the current site + path.
    2. Fall back to a ContentEntity with a matching slug.
    3. 404 if nothing found.
    """
    if not path.startswith('/'):
        path = '/' + path
    if not path.endswith('/'):
        path = path + '/'

    site = getattr(request, 'site', None)
    if site is None:
        raise Http404("No site configured.")

    # Reset the in-memory schema registry for this request
    reset_registry()

    # 1. Try static page
    page = Page.objects.filter(site=site, path=path, is_published=True).first()
    if page:
        context = {
            'page': page,
            'path': path,
            'breadcrumbs': page.get_breadcrumbs(),
            'child_pages': page.get_children(),
        }
        return render(request, page.template_name, context)

    # 2. Try entity routing (strip leading/trailing slashes to get slug)
    slug = path.strip('/')
    entity = ContentEntity.objects.filter(
        site=site, slug=slug, is_published=True
    ).first()
    if entity:
        template_name = entity.template_name or f'cms/{entity.entity_type}_detail.html'
        context = {'entity': entity, 'path': path}
        return render(request, template_name, context)

    raise Http404(f"No page or entity found for path '{path}'.")


# ---------------------------------------------------------------------------
# API: Toggle edit mode
# ---------------------------------------------------------------------------

@login_required
@require_POST
def toggle_edit_mode(request):
    """Toggle the CMS edit mode session flag."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    from django.conf import settings
    key = getattr(settings, 'CMS_EDIT_MODE_SESSION_KEY', 'cms_edit_mode')
    current = request.session.get(key, False)
    request.session[key] = not current
    return JsonResponse({'edit_mode': request.session[key]})


# ---------------------------------------------------------------------------
# API: Save block content
# ---------------------------------------------------------------------------

@login_required
@require_POST
def save_block(request):
    """
    Save the data for a ContentBlock.

    Expected JSON body:
    {
        "key": "hero",
        "scope": "local",
        "data": { "title": "Hello", "image": "/media/img.jpg" },
        "page_id": 1   // optional
        "entity_id": 1 // optional
    }
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    site = getattr(request, 'site', None)
    if site is None:
        return JsonResponse({'error': 'Site not configured'}, status=400)

    key = payload.get('key', '').strip()
    if not key:
        return JsonResponse({'error': 'key is required'}, status=400)

    scope = payload.get('scope', 'local')
    data = payload.get('data', {})
    page_id = payload.get('page_id')
    entity_id = payload.get('entity_id')

    page = None
    entity = None

    if scope == 'local':
        if page_id:
            page = get_object_or_404(Page, pk=page_id, site=site)
        elif entity_id:
            entity = get_object_or_404(ContentEntity, pk=entity_id, site=site)

    lookup = {'site': site, 'key': key, 'scope': scope, 'page': page, 'entity': entity}
    block, created = ContentBlock.objects.update_or_create(
        **lookup,
        defaults={'data': data},
    )

    return JsonResponse({'ok': True, 'id': block.pk, 'created': created})


# ---------------------------------------------------------------------------
# API: Save list block (with ordering)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def save_list_block(request):
    """
    Save an ordered list of items for a ContentBlock.

    Expected JSON body:
    {
        "key": "products",
        "scope": "local",
        "items": [ {"title": "A", ...}, {"title": "B", ...} ],
        "page_id": 1
    }
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    site = getattr(request, 'site', None)
    if site is None:
        return JsonResponse({'error': 'Site not configured'}, status=400)

    key = payload.get('key', '').strip()
    if not key:
        return JsonResponse({'error': 'key is required'}, status=400)

    scope = payload.get('scope', 'local')
    items = payload.get('items', [])
    page_id = payload.get('page_id')
    entity_id = payload.get('entity_id')

    page = None
    entity = None

    if scope == 'local':
        if page_id:
            page = get_object_or_404(Page, pk=page_id, site=site)
        elif entity_id:
            entity = get_object_or_404(ContentEntity, pk=entity_id, site=site)

    lookup = {'site': site, 'key': key, 'scope': scope, 'page': page, 'entity': entity}
    block, created = ContentBlock.objects.update_or_create(
        **lookup,
        defaults={'data': items},
    )

    return JsonResponse({'ok': True, 'id': block.pk, 'created': created})


# ---------------------------------------------------------------------------
# API: Get schema for a template
# ---------------------------------------------------------------------------

@login_required
@require_GET
def get_schema_view(request):
    """Return the schema for a given template_name."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    template_name = request.GET.get('template')
    schema = get_schema(template_name)
    return JsonResponse({'schema': schema})


# ---------------------------------------------------------------------------
# API: Live preview
# ---------------------------------------------------------------------------

@login_required
@require_POST
def live_preview(request):
    """
    Render a template with preview data and return the HTML fragment.

    Expected JSON body:
    {
        "template": "cms/product_detail.html",
        "context": { "title": "Preview Title", ... }
    }
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    template_name = payload.get('template', '')
    extra_context = payload.get('context', {})

    try:
        html = render_to_string(template_name, {'preview_data': extra_context, 'request': request})
        return JsonResponse({'html': html})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)
