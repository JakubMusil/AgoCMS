"""
Tests for AgoCMS — models, template tags, views, schema registry, and routing.
"""

import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.template import Context, RequestContext, Template
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from cms.models import ContentBlock, ContentEntity, Page, SchemaEntry
from cms.schema_registry import (
    get_current_registry,
    get_schema,
    register_item,
    reset_registry,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class PageModelTest(TestCase):
    def setUp(self):
        self.site = Site.objects.update_or_create(
            domain='example.com', defaults={'name': 'Example'}
        )[0]

    def test_create_page(self):
        page = Page.objects.create(
            site=self.site,
            path='/about/',
            template_name='cms/home.html',
            title='About Us',
        )
        self.assertEqual(str(page), 'example.com/about/')
        self.assertTrue(page.is_published)

    def test_unique_path_per_site(self):
        Page.objects.create(site=self.site, path='/about/', template_name='t.html')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Page.objects.create(site=self.site, path='/about/', template_name='t2.html')


class ContentEntityModelTest(TestCase):
    def setUp(self):
        self.site = Site.objects.update_or_create(
            domain='example.com', defaults={'name': 'Example'}
        )[0]

    def test_slug_auto_from_title(self):
        entity = ContentEntity.objects.create(
            site=self.site,
            entity_type='product',
            data={'title': 'My First Product'},
        )
        self.assertEqual(entity.slug, 'my-first-product')

    def test_slug_auto_from_name(self):
        entity = ContentEntity.objects.create(
            site=self.site,
            entity_type='product',
            data={'name': 'Blue Widget'},
        )
        self.assertEqual(entity.slug, 'blue-widget')

    def test_search_index_populated(self):
        entity = ContentEntity.objects.create(
            site=self.site,
            entity_type='product',
            data={'title': 'Super Widget', 'description': 'Amazing product'},
        )
        self.assertIn('Super Widget', entity.search_index)
        self.assertIn('Amazing product', entity.search_index)

    def test_search_index_strips_html(self):
        entity = ContentEntity.objects.create(
            site=self.site,
            entity_type='blog_post',
            data={'body': '<p>Hello <strong>world</strong></p>'},
        )
        self.assertNotIn('<p>', entity.search_index)
        self.assertIn('Hello', entity.search_index)

    def test_str(self):
        entity = ContentEntity(
            site=self.site,
            entity_type='product',
            slug='test',
        )
        self.assertIn('product:test', str(entity))


class ContentBlockModelTest(TestCase):
    def setUp(self):
        self.site = Site.objects.update_or_create(
            domain='example.com', defaults={'name': 'Example'}
        )[0]
        self.page = Page.objects.create(
            site=self.site, path='/home/', template_name='cms/home.html'
        )

    def test_create_block(self):
        block = ContentBlock.objects.create(
            site=self.site,
            key='hero',
            page=self.page,
            data={'heading': 'Hello World'},
        )
        self.assertEqual(block.key, 'hero')
        self.assertEqual(block.data['heading'], 'Hello World')
        self.assertIn('hero', str(block))


# ---------------------------------------------------------------------------
# Schema Registry tests
# ---------------------------------------------------------------------------


class SchemaRegistryTest(TestCase):
    def setUp(self):
        reset_registry()

    def test_register_and_get(self):
        register_item('test.html', 'hero', 'title', 'text')
        schema = get_schema('test.html')
        self.assertIn('hero', schema)
        self.assertEqual(schema['hero']['title']['type'], 'text')

    def test_reset_clears_registry(self):
        register_item('test.html', 'hero', 'title', 'text')
        reset_registry()
        registry = get_current_registry()
        self.assertEqual(registry, {})

    def test_multiple_items(self):
        register_item('product.html', 'info', 'price', 'number')
        register_item('product.html', 'info', 'name', 'text')
        register_item('product.html', 'info', 'image', 'image')
        schema = get_schema('product.html')
        self.assertIn('price', schema['info'])
        self.assertIn('name', schema['info'])
        self.assertIn('image', schema['info'])

    def test_persists_to_db(self):
        register_item('tpl.html', 'blk', 'field', 'color', is_list=False)
        entry = SchemaEntry.objects.get(
            template_name='tpl.html', block_key='blk', item_name='field'
        )
        self.assertEqual(entry.field_type, 'color')


# ---------------------------------------------------------------------------
# Template tag tests
# ---------------------------------------------------------------------------


class TemplateTagTest(TestCase):
    def setUp(self):
        reset_registry()
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.factory = RequestFactory()
        self.user = User.objects.create_user('staff', password='pass', is_staff=True)

    def _make_request(self, edit_mode=False):
        request = self.factory.get('/')
        request.user = self.user
        request.site = self.site
        request.session = {'cms_edit_mode': edit_mode}
        return request

    def test_editable_tag_renders_inner_without_edit_mode(self):
        template_str = (
            "{% load cms_tags %}"
            "{% editable 'hero' type='single' %}"
            "<p>content</p>"
            "{% endeditable %}"
        )
        request = self._make_request(edit_mode=False)
        t = Template(template_str)
        ctx = RequestContext(request, {})
        output = t.render(ctx)
        self.assertIn('<p>content</p>', output)
        self.assertNotIn('cms-editable', output)

    def test_editable_tag_adds_data_attrs_in_edit_mode(self):
        template_str = (
            "{% load cms_tags %}"
            "{% editable 'hero' type='single' %}"
            "<p>content</p>"
            "{% endeditable %}"
        )
        request = self._make_request(edit_mode=True)
        t = Template(template_str)
        ctx = RequestContext(request, {})
        output = t.render(ctx)
        self.assertIn('cms-editable', output)
        self.assertIn('data-cms-key="hero"', output)

    def test_item_tag_registers_schema(self):
        template_str = (
            "{% load cms_tags %}"
            "{% editable 'product' type='single' %}"
            "{% item 'price' type='number' %}"
            "{% endeditable %}"
        )
        request = self._make_request(edit_mode=False)
        t = Template(template_str)
        ctx = RequestContext(request, {})
        t.render(ctx)
        schema = get_schema()
        # Template name may be '<unknown source>' in tests; just check registry has entries
        found = False
        for tmpl_schema in schema.values():
            if 'product' in tmpl_schema and 'price' in tmpl_schema['product']:
                found = True
        self.assertTrue(found, "price field should be registered in schema")

    def test_item_tag_invalid_type_raises(self):
        from django.template import TemplateSyntaxError
        template_str = "{% load cms_tags %}{% item 'foo' type='invalid_type' %}"
        with self.assertRaises(TemplateSyntaxError):
            Template(template_str)

    def test_cms_value_tag(self):
        block = ContentBlock.objects.create(
            site=self.site,
            key='footer',
            scope='global',
            data={'copyright': '2024 AgoCMS'},
        )
        template_str = "{% load cms_tags %}{% cms_value 'footer' 'copyright' %}"
        request = self._make_request()
        t = Template(template_str)
        ctx = RequestContext(request, {})
        output = t.render(ctx)
        self.assertIn('2024 AgoCMS', output)

    def test_cms_edit_toggle_shown_for_staff(self):
        template_str = "{% load cms_tags %}{% cms_edit_toggle %}"
        request = self._make_request(edit_mode=False)
        t = Template(template_str)
        ctx = RequestContext(request, {})
        output = t.render(ctx)
        self.assertIn('cms-edit-toggle', output)

    def test_cms_edit_toggle_hidden_for_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        template_str = "{% load cms_tags %}{% cms_edit_toggle %}"
        request = self._make_request()
        request.user = AnonymousUser()
        t = Template(template_str)
        ctx = RequestContext(request, {})
        output = t.render(ctx)
        self.assertEqual(output.strip(), '')


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------


class SiteMiddlewareTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]

    def test_site_attached_to_request(self):
        client = Client(SERVER_NAME='testserver')
        User.objects.create_user('u', password='p', is_staff=False)
        response = client.get('/nonexistent-path-for-404/')
        # Middleware should have run; no AttributeError on request.site
        self.assertIn(response.status_code, [200, 404])


# ---------------------------------------------------------------------------
# View / routing tests
# ---------------------------------------------------------------------------


class CMSRoutingTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.client = Client(SERVER_NAME='testserver')

    def test_page_routing(self):
        Page.objects.create(
            site=self.site,
            path='/about/',
            template_name='cms/home.html',
            title='About',
        )
        resp = self.client.get('/about/')
        self.assertEqual(resp.status_code, 200)

    def test_entity_routing(self):
        ContentEntity.objects.create(
            site=self.site,
            entity_type='product',
            slug='blue-widget',
            data={'name': 'Blue Widget', 'price': 29.99},
            template_name='cms/product_detail.html',
        )
        resp = self.client.get('/blue-widget/')
        self.assertEqual(resp.status_code, 200)

    def test_404_for_unknown_path(self):
        resp = self.client.get('/this-does-not-exist/')
        self.assertEqual(resp.status_code, 404)

    def test_unpublished_page_returns_404(self):
        Page.objects.create(
            site=self.site,
            path='/draft/',
            template_name='cms/home.html',
            is_published=False,
        )
        resp = self.client.get('/draft/')
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# API view tests
# ---------------------------------------------------------------------------


class CMSAPITest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.client = Client(SERVER_NAME='testserver')
        self.staff = User.objects.create_user('admin', password='pass', is_staff=True)
        self.client.login(username='admin', password='pass')

    def test_toggle_edit_mode(self):
        resp = self.client.post('/cms-api/toggle-edit-mode/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('edit_mode', data)
        self.assertTrue(data['edit_mode'])

        # Toggle again
        resp2 = self.client.post('/cms-api/toggle-edit-mode/')
        self.assertFalse(resp2.json()['edit_mode'])

    def test_save_block(self):
        page = Page.objects.create(
            site=self.site, path='/test/', template_name='cms/home.html'
        )
        payload = {
            'key': 'hero',
            'scope': 'local',
            'page_id': page.pk,
            'data': {'heading': 'Hello World'},
        }
        resp = self.client.post(
            '/cms-api/save-block/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        block = ContentBlock.objects.get(site=self.site, key='hero', page=page)
        self.assertEqual(block.data['heading'], 'Hello World')

    def test_save_list_block(self):
        page = Page.objects.create(
            site=self.site, path='/list-test/', template_name='cms/home.html'
        )
        payload = {
            'key': 'features',
            'scope': 'local',
            'page_id': page.pk,
            'items': [
                {'title': 'Fast', 'description': 'Very quick'},
                {'title': 'Reliable', 'description': 'Always on'},
            ],
        }
        resp = self.client.post(
            '/cms-api/save-list-block/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        block = ContentBlock.objects.get(site=self.site, key='features', page=page)
        self.assertEqual(len(block.data), 2)
        self.assertEqual(block.data[0]['title'], 'Fast')

    def test_save_block_requires_login(self):
        self.client.logout()
        resp = self.client.post(
            '/cms-api/save-block/',
            data=json.dumps({'key': 'hero', 'data': {}}),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [302, 403])

    def test_get_schema(self):
        SchemaEntry.objects.create(
            template_name='cms/home.html',
            block_key='hero',
            item_name='heading',
            field_type='text',
        )
        resp = self.client.get('/cms-api/schema/?template=cms/home.html')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('schema', data)
        self.assertIn('hero', data['schema'])

    def test_non_staff_cannot_save_block(self):
        normal_user = User.objects.create_user('normaluser', password='pass', is_staff=False)
        self.client.login(username='normaluser', password='pass')
        resp = self.client.post(
            '/cms-api/save-block/',
            data=json.dumps({'key': 'hero', 'data': {}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
