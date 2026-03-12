"""
Schema Registry for AgoCMS.

Stores which fields (items) belong to which editable blocks,
discovered at template render time. Entries are saved to the DB
(SchemaEntry model) so the admin overlay can know field types
without re-rendering the template.
"""

from threading import local

_local = local()


def get_current_registry():
    """Return the per-request in-memory registry dict."""
    if not hasattr(_local, 'registry'):
        _local.registry = {}
    return _local.registry


def reset_registry():
    """Clear the per-request registry (call at the start of each request)."""
    _local.registry = {}


def register_item(template_name, block_key, item_name, field_type, is_list=False):
    """
    Record a field discovered during template rendering.

    Also persists the entry to the DB (upsert) so the admin overlay
    can read the schema without a fresh render.
    """
    registry = get_current_registry()
    registry.setdefault(template_name, {}).setdefault(block_key, {})[item_name] = {
        'type': field_type,
        'is_list': is_list,
    }
    _persist_entry(template_name, block_key, item_name, field_type, is_list)


def get_schema(template_name=None):
    """
    Return the in-memory schema, optionally filtered by template_name.
    Falls back to DB if memory is empty (e.g. after server restart).
    """
    registry = get_current_registry()
    if template_name:
        mem = registry.get(template_name)
        if mem:
            return mem
        return _load_from_db(template_name)
    return registry


def _persist_entry(template_name, block_key, item_name, field_type, is_list):
    """Upsert a SchemaEntry row."""
    try:
        from cms.models import SchemaEntry
        SchemaEntry.objects.update_or_create(
            template_name=template_name,
            block_key=block_key,
            item_name=item_name,
            defaults={'field_type': field_type, 'is_list': is_list},
        )
    except Exception:
        # DB may not be available (e.g. during migrations or tests without DB)
        pass


def _load_from_db(template_name):
    """Load schema for a template from the DB."""
    try:
        from cms.models import SchemaEntry
        entries = SchemaEntry.objects.filter(template_name=template_name)
        result = {}
        for entry in entries:
            result.setdefault(entry.block_key, {})[entry.item_name] = {
                'type': entry.field_type,
                'is_list': entry.is_list,
            }
        return result
    except Exception:
        return {}
