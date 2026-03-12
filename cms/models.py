import re
from django.db import models
from django.contrib.sites.models import Site
from django.utils.text import slugify


class Page(models.Model):
    """Represents a CMS page tied to a specific site."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='pages')
    path = models.CharField(max_length=500, help_text='URL path, e.g. /about/')
    template_name = models.CharField(
        max_length=500,
        help_text='Path to the template file, e.g. cms/about.html',
    )
    title = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('site', 'path')
        ordering = ['path']

    def __str__(self):
        return f'{self.site.domain}{self.path}'


class ContentEntity(models.Model):
    """
    Universal entity model for all content types (products, blog posts, etc.).
    The 'data' JSONField is the source of truth for all entity fields.
    """

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='entities')
    entity_type = models.CharField(
        max_length=100,
        help_text='e.g. "product", "blog_post", "page_section"',
    )
    data = models.JSONField(default=dict)
    search_index = models.TextField(
        blank=True,
        help_text='Auto-populated text for full-text search',
    )
    slug = models.SlugField(
        max_length=255,
        blank=True,
        help_text='Auto-extracted from data["slug"] or data["title"]',
    )
    template_name = models.CharField(
        max_length=500,
        blank=True,
        help_text='Optional override template for entity detail view',
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('site', 'entity_type', 'slug')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.entity_type}:{self.slug} ({self.site.domain})'

    def save(self, *args, **kwargs):
        self._update_slug()
        self._update_search_index()
        super().save(*args, **kwargs)

    def _update_slug(self):
        if not self.slug:
            raw = (
                self.data.get('slug')
                or self.data.get('title')
                or self.data.get('name')
                or str(self.pk or '')
            )
            self.slug = slugify(raw)[:255]

    def _update_search_index(self):
        """Build a flat text representation of all string values in data."""
        parts = []
        self._extract_text(self.data, parts)
        self.search_index = ' '.join(parts)

    def _extract_text(self, obj, parts):
        if isinstance(obj, dict):
            for v in obj.values():
                self._extract_text(v, parts)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_text(item, parts)
        elif isinstance(obj, str):
            clean = re.sub(r'<[^>]+>', ' ', obj)
            parts.append(clean.strip())


class ContentBlock(models.Model):
    """
    Stores the actual content data for a named editable block on a page or entity.
    """

    SCOPE_LOCAL = 'local'
    SCOPE_GLOBAL = 'global'
    SCOPE_CHOICES = [
        (SCOPE_LOCAL, 'Local (per-page)'),
        (SCOPE_GLOBAL, 'Global (site-wide)'),
    ]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='blocks')
    key = models.CharField(max_length=255, help_text='Matches the {% editable "key" %} tag')
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SCOPE_LOCAL)
    page = models.ForeignKey(
        Page,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='blocks',
    )
    entity = models.ForeignKey(
        ContentEntity,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='blocks',
    )
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('site', 'key', 'page', 'scope')

    def __str__(self):
        return f'{self.key} ({self.scope})'


class SchemaEntry(models.Model):
    """
    Records field definitions discovered from template rendering.
    Maps (template_name, block_key, item_name) -> field_type.
    """

    template_name = models.CharField(max_length=500)
    block_key = models.CharField(max_length=255)
    item_name = models.CharField(max_length=255)
    field_type = models.CharField(
        max_length=50,
        default='text',
        help_text='text, richtext, image, number, color, boolean',
    )
    is_list = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('template_name', 'block_key', 'item_name')

    def __str__(self):
        return f'{self.template_name}::{self.block_key}::{self.item_name} ({self.field_type})'
