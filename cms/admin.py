from django.contrib import admin
from django.utils.html import format_html

from .models import ContentBlock, ContentEntity, Page, SchemaEntry


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('path', 'site', 'template_name', 'title', 'is_published', 'updated_at')
    list_filter = ('site', 'is_published')
    search_fields = ('path', 'title', 'template_name')
    ordering = ('site', 'path')


@admin.register(ContentEntity)
class ContentEntityAdmin(admin.ModelAdmin):
    list_display = ('entity_type', 'slug', 'site', 'is_published', 'updated_at')
    list_filter = ('site', 'entity_type', 'is_published')
    search_fields = ('slug', 'search_index')
    ordering = ('site', 'entity_type', 'slug')
    readonly_fields = ('search_index', 'created_at', 'updated_at')


@admin.register(ContentBlock)
class ContentBlockAdmin(admin.ModelAdmin):
    list_display = ('key', 'scope', 'site', 'page', 'entity', 'updated_at')
    list_filter = ('site', 'scope')
    search_fields = ('key',)
    ordering = ('site', 'key')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SchemaEntry)
class SchemaEntryAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'block_key', 'item_name', 'field_type', 'is_list', 'updated_at')
    list_filter = ('field_type', 'is_list')
    search_fields = ('template_name', 'block_key', 'item_name')
    ordering = ('template_name', 'block_key', 'item_name')
