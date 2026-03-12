"""
CMS Middleware for AgoCMS.

- SiteMiddleware: resolves the current site from the request host
  and attaches it as request.site.
"""

from django.contrib.sites.models import Site
from django.http import Http404


class SiteMiddleware:
    """
    Determine which Site matches the current request and attach it
    as ``request.site``.

    Falls back to SITE_ID from settings if no host match is found.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.site = self._get_site(request)
        response = self.get_response(request)
        return response

    def _get_site(self, request):
        from django.conf import settings
        host = request.get_host().split(':')[0]  # strip port

        try:
            return Site.objects.get(domain=host)
        except Site.DoesNotExist:
            pass

        # Fall back to configured SITE_ID
        try:
            return Site.objects.get(pk=getattr(settings, 'SITE_ID', 1))
        except Site.DoesNotExist:
            return None
