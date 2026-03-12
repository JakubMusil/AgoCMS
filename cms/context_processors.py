"""
CMS context processors for AgoCMS.
"""

from django.conf import settings


def cms_context(request):
    """
    Inject CMS-specific context variables into every template.
    """
    is_staff = request.user.is_authenticated and request.user.is_staff
    edit_mode = is_staff and request.session.get(
        getattr(settings, 'CMS_EDIT_MODE_SESSION_KEY', 'cms_edit_mode'), False
    )
    return {
        'cms_edit_mode': edit_mode,
        'cms_site': getattr(request, 'site', None),
    }
