"""
AgoCMS Template Tags

Usage:
    {% load cms_tags %}

    {% editable "hero" type="list" scope="local" %}
        {% item "title" type="text" %}
        {% item "image" type="image" %}
        {% item "body" type="richtext" %}
    {% endeditable %}

    {% editable "cta_color" type="single" scope="global" %}
        {% item "color" type="color" %}
    {% endeditable %}
"""

import json
from django import template
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

from cms.schema_registry import register_item

register = template.Library()


# ---------------------------------------------------------------------------
# Helper to get the current template name from the context
# ---------------------------------------------------------------------------

def _template_name_from_context(context):
    try:
        return context.template_name
    except AttributeError:
        try:
            return context.render_context.template.name
        except AttributeError:
            return 'unknown'


# ---------------------------------------------------------------------------
# {% editable "key" type="list|single" scope="local|global" %} ... {% endeditable %}
# ---------------------------------------------------------------------------

class EditableNode(template.Node):
    def __init__(self, key, block_type, scope, nodelist):
        self.key = key
        self.block_type = block_type  # 'list' or 'single'
        self.scope = scope            # 'local' or 'global'
        self.nodelist = nodelist

    def render(self, context):
        key = self.key.resolve(context)
        request = context.get('request')
        template_name = _template_name_from_context(context)

        # Gather the ContentBlock data for this key
        block_data = self._get_block_data(context, key)

        # Push editable context so child {% item %} nodes can access it
        with context.update({
            '_cms_block_key': key,
            '_cms_block_type': self.block_type,
            '_cms_scope': self.scope,
            '_cms_block_data': block_data,
            '_cms_template_name': template_name,
            '_cms_items_schema': [],   # will be populated by ItemNode children
        }):
            inner_html = self.nodelist.render(context)
            items_schema = context.get('_cms_items_schema', [])

        is_staff_edit = request and request.user.is_authenticated and request.user.is_staff
        cms_edit_mode = request and request.session.get('cms_edit_mode', False) if is_staff_edit else False

        if cms_edit_mode:
            schema_json = conditional_escape(json.dumps(items_schema))
            data_json = conditional_escape(json.dumps(block_data))
            return format_html(
                '<div class="cms-editable" '
                'data-cms-key="{key}" '
                'data-cms-type="{btype}" '
                'data-cms-scope="{scope}" '
                'data-cms-schema="{schema}" '
                'data-cms-data="{data}" '
                'data-cms-template="{tmpl}">'
                '{inner}'
                '</div>',
                key=key,
                btype=self.block_type,
                scope=self.scope,
                schema=schema_json,
                data=data_json,
                tmpl=template_name,
                inner=mark_safe(inner_html),
            )
        return inner_html

    def _get_block_data(self, context, key):
        """Load ContentBlock data from context (page/entity) or DB."""
        try:
            from cms.models import ContentBlock, Page
            request = context.get('request')
            site = getattr(request, 'site', None)
            if site is None:
                return {}

            if self.scope == 'global':
                block = ContentBlock.objects.filter(
                    site=site, key=key, scope='global'
                ).first()
            else:
                # Try page block first, then entity
                page = context.get('page')
                entity = context.get('entity')
                if page:
                    block = ContentBlock.objects.filter(
                        site=site, key=key, page=page, scope='local'
                    ).first()
                elif entity:
                    block = ContentBlock.objects.filter(
                        site=site, key=key, entity=entity, scope='local'
                    ).first()
                else:
                    block = None

            return block.data if block else {}
        except Exception:
            return {}


@register.tag('editable')
def editable_tag(parser, token):
    bits = token.split_contents()
    tag_name = bits[0]

    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            f"'{tag_name}' requires at least one argument: the block key."
        )

    key = parser.compile_filter(bits[1])
    kwargs = _parse_kwargs(bits[2:])

    block_type = kwargs.get('type', 'single')
    scope = kwargs.get('scope', 'local')

    nodelist = parser.parse(('endeditable',))
    parser.delete_first_token()

    return EditableNode(key, block_type, scope, nodelist)


# ---------------------------------------------------------------------------
# {% item "name" type="text|image|richtext|color|number|boolean" %}
# ---------------------------------------------------------------------------

class ItemNode(template.Node):
    ALLOWED_TYPES = {'text', 'richtext', 'image', 'number', 'color', 'boolean', 'url', 'date'}

    def __init__(self, name, field_type, index_var=None):
        self.name = name
        self.field_type = field_type
        self.index_var = index_var  # optional: loop index for list items

    def render(self, context):
        name = self.name.resolve(context)
        field_type = self.field_type
        block_key = context.get('_cms_block_key', '')
        block_data = context.get('_cms_block_data', {})
        template_name = context.get('_cms_template_name', 'unknown')
        is_list = context.get('_cms_block_type') == 'list'

        # Register the field in the schema registry
        register_item(template_name, block_key, name, field_type, is_list)

        # Accumulate schema for the parent editable node
        schema = context.get('_cms_items_schema')
        if schema is not None and not any(s['name'] == name for s in schema):
            schema.append({'name': name, 'type': field_type})

        # Extract value from block_data
        value = self._get_value(block_data, name, context)

        # Store the resolved value in context for template usage
        context[f'cms_{block_key}_{name}'] = value

        request = context.get('request')
        is_staff_edit = request and request.user.is_authenticated and request.user.is_staff
        cms_edit_mode = request and request.session.get('cms_edit_mode', False) if is_staff_edit else False

        if cms_edit_mode:
            value_json = conditional_escape(json.dumps(value))
            rendered_value = self._render_value(value, field_type)
            return format_html(
                '<span class="cms-item" '
                'data-cms-item="{name}" '
                'data-cms-item-type="{ftype}" '
                'data-cms-item-value="{val}">'
                '{rendered}'
                '</span>',
                name=name,
                ftype=field_type,
                val=value_json,
                rendered=mark_safe(rendered_value),
            )

        return self._render_value(value, field_type)

    def _get_value(self, block_data, name, context):
        """Extract the field value from block data, supporting list iteration."""
        block_type = context.get('_cms_block_type')
        if block_type == 'list':
            # For list blocks, data is a list of dicts
            items = block_data if isinstance(block_data, list) else []
            index = context.get('_cms_list_index', 0)
            if index < len(items):
                return items[index].get(name, '')
            return ''
        return block_data.get(name, '') if isinstance(block_data, dict) else ''

    def _render_value(self, value, field_type):
        if field_type == 'richtext' and value:
            return mark_safe(value)
        if value is None:
            return ''
        return conditional_escape(str(value))


@register.tag('item')
def item_tag(parser, token):
    bits = token.split_contents()
    tag_name = bits[0]

    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            f"'{tag_name}' requires at least one argument: the field name."
        )

    name = parser.compile_filter(bits[1])
    kwargs = _parse_kwargs(bits[2:])
    field_type = kwargs.get('type', 'text')

    if field_type not in ItemNode.ALLOWED_TYPES:
        raise template.TemplateSyntaxError(
            f"'{tag_name}' got unknown type '{field_type}'. "
            f"Allowed: {', '.join(sorted(ItemNode.ALLOWED_TYPES))}"
        )

    return ItemNode(name, field_type)


# ---------------------------------------------------------------------------
# {% cms_list_item %} — iterate over list block items
# ---------------------------------------------------------------------------

class CmsListNode(template.Node):
    """
    {% cms_list "key" scope="local" %}
        ...{% item "title" type="text" %}...
    {% endcms_list %}

    Renders the nodelist once per item in the list, exposing _cms_list_index.
    Supports drag-and-drop ordering via data-attributes in edit mode.
    """

    def __init__(self, key, scope, nodelist):
        self.key = key
        self.scope = scope
        self.nodelist = nodelist

    def render(self, context):
        key = self.key.resolve(context)
        request = context.get('request')
        template_name = _template_name_from_context(context)
        block_data = self._get_block_data(context, key)
        items = block_data if isinstance(block_data, list) else []

        is_staff_edit = request and request.user.is_authenticated and request.user.is_staff
        cms_edit_mode = request and request.session.get('cms_edit_mode', False) if is_staff_edit else False

        rendered_items = []
        for index, item_data in enumerate(items):
            with context.update({
                '_cms_block_key': key,
                '_cms_block_type': 'list',
                '_cms_scope': self.scope,
                '_cms_block_data': items,
                '_cms_list_index': index,
                '_cms_template_name': template_name,
                '_cms_items_schema': [],
            }):
                inner = self.nodelist.render(context)
                items_schema = context.get('_cms_items_schema', [])

            if cms_edit_mode:
                schema_json = conditional_escape(json.dumps(items_schema))
                rendered_items.append(format_html(
                    '<div class="cms-list-item" '
                    'data-cms-list-key="{key}" '
                    'data-cms-list-index="{idx}" '
                    'data-cms-schema="{schema}" '
                    'draggable="true">'
                    '{inner}'
                    '</div>',
                    key=key,
                    idx=index,
                    schema=schema_json,
                    inner=mark_safe(inner),
                ))
            else:
                rendered_items.append(inner)

        if cms_edit_mode:
            data_json = conditional_escape(json.dumps(items))
            return format_html(
                '<div class="cms-list" '
                'data-cms-key="{key}" '
                'data-cms-scope="{scope}" '
                'data-cms-data="{data}" '
                'data-cms-template="{tmpl}">'
                '{items}'
                '</div>',
                key=key,
                scope=self.scope,
                data=data_json,
                tmpl=template_name,
                items=mark_safe(''.join(rendered_items)),
            )
        return mark_safe(''.join(rendered_items))

    def _get_block_data(self, context, key):
        try:
            from cms.models import ContentBlock
            request = context.get('request')
            site = getattr(request, 'site', None)
            if site is None:
                return []
            if self.scope == 'global':
                block = ContentBlock.objects.filter(
                    site=site, key=key, scope='global'
                ).first()
            else:
                page = context.get('page')
                entity = context.get('entity')
                if page:
                    block = ContentBlock.objects.filter(
                        site=site, key=key, page=page, scope='local'
                    ).first()
                elif entity:
                    block = ContentBlock.objects.filter(
                        site=site, key=key, entity=entity, scope='local'
                    ).first()
                else:
                    block = None
            return block.data if block else []
        except Exception:
            return []


@register.tag('cms_list')
def cms_list_tag(parser, token):
    bits = token.split_contents()
    tag_name = bits[0]

    if len(bits) < 2:
        raise template.TemplateSyntaxError(
            f"'{tag_name}' requires at least one argument: the block key."
        )

    key = parser.compile_filter(bits[1])
    kwargs = _parse_kwargs(bits[2:])
    scope = kwargs.get('scope', 'local')

    nodelist = parser.parse(('endcms_list',))
    parser.delete_first_token()

    return CmsListNode(key, scope, nodelist)


# ---------------------------------------------------------------------------
# {% cms_value "block_key" "item_name" %} — render a single value
# ---------------------------------------------------------------------------

@register.simple_tag(takes_context=True)
def cms_value(context, block_key, item_name, default=''):
    """
    Render the value of a single item from a ContentBlock.

    Usage: {% cms_value "hero" "title" %}
    """
    try:
        from cms.models import ContentBlock
        request = context.get('request')
        site = getattr(request, 'site', None)
        if site is None:
            return default
        block = ContentBlock.objects.filter(site=site, key=block_key).first()
        if block and isinstance(block.data, dict):
            return block.data.get(item_name, default)
    except Exception:
        pass
    return default


# ---------------------------------------------------------------------------
# {% cms_edit_toggle %} — renders the edit mode on/off button for staff
# ---------------------------------------------------------------------------

@register.simple_tag(takes_context=True)
def cms_edit_toggle(context):
    """
    Renders a floating edit-mode toggle button for staff users.
    Place this near the end of your base template's <body>.
    """
    request = context.get('request')
    if not (request and request.user.is_authenticated and request.user.is_staff):
        return ''

    edit_mode = request.session.get('cms_edit_mode', False)
    label = 'Exit Edit Mode' if edit_mode else 'Enter Edit Mode'
    btn_class = 'cms-edit-toggle--active' if edit_mode else ''

    return format_html(
        '<button class="cms-edit-toggle {cls}" '
        'hx-post="/cms-api/toggle-edit-mode/" '
        'hx-swap="none" '
        'onclick="window.location.reload()">'
        '{label}'
        '</button>',
        cls=btn_class,
        label=label,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_kwargs(bits):
    """Parse key=value pairs from token bits."""
    kwargs = {}
    for bit in bits:
        if '=' in bit:
            k, v = bit.split('=', 1)
            kwargs[k.strip()] = v.strip().strip('"').strip("'")
    return kwargs
