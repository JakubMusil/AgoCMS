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


# ---------------------------------------------------------------------------
# Hierarchical page tests
# ---------------------------------------------------------------------------


class HierarchicalPageTest(TestCase):
    def setUp(self):
        self.site = Site.objects.update_or_create(
            domain='example.com', defaults={'name': 'Example'}
        )[0]
        self.root = Page.objects.create(
            site=self.site, path='/', template_name='cms/home.html', title='Home'
        )
        self.about = Page.objects.create(
            site=self.site, path='/about/', template_name='cms/home.html',
            title='About', parent=self.root, sort_order=1,
        )
        self.team = Page.objects.create(
            site=self.site, path='/about/team/', template_name='cms/home.html',
            title='Team', parent=self.about, sort_order=1,
        )

    def test_page_depth(self):
        self.assertEqual(self.root.depth, 0)
        self.assertEqual(self.about.depth, 1)
        self.assertEqual(self.team.depth, 2)

    def test_get_ancestors(self):
        ancestors = self.team.get_ancestors()
        self.assertEqual(len(ancestors), 2)
        self.assertEqual(ancestors[0], self.root)
        self.assertEqual(ancestors[1], self.about)

    def test_get_breadcrumbs(self):
        crumbs = self.team.get_breadcrumbs()
        self.assertEqual(len(crumbs), 3)
        self.assertEqual(crumbs[-1], self.team)

    def test_get_children(self):
        children = self.root.get_children()
        self.assertEqual(children.count(), 1)
        self.assertEqual(children.first(), self.about)

    def test_get_siblings(self):
        sibling = Page.objects.create(
            site=self.site, path='/blog/', template_name='cms/home.html',
            title='Blog', parent=self.root, sort_order=2,
        )
        siblings = self.about.get_siblings()
        self.assertIn(sibling, siblings)
        self.assertNotIn(self.about, siblings)

    def test_root_page_ancestors_empty(self):
        self.assertEqual(self.root.get_ancestors(), [])

    def test_unpublished_children_excluded(self):
        Page.objects.create(
            site=self.site, path='/about/secret/', template_name='cms/home.html',
            title='Secret', parent=self.about, is_published=False,
        )
        children = self.about.get_children()
        self.assertEqual(children.count(), 1)  # only 'team'


# ---------------------------------------------------------------------------
# Custom admin panel tests
# ---------------------------------------------------------------------------


class CustomAdminAuthTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.client = Client(SERVER_NAME='testserver')

    def test_login_page_renders(self):
        resp = self.client.get(reverse('cms_login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sign in')

    def test_register_page_renders(self):
        resp = self.client.get(reverse('cms_register'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create a new account')

    def test_login_success(self):
        User.objects.create_user('testuser', password='testpass123')
        resp = self.client.post(reverse('cms_login'), {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertEqual(resp.status_code, 302)

    def test_register_creates_user(self):
        resp = self.client.post(reverse('cms_register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_logout_redirects(self):
        User.objects.create_user('testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get(reverse('cms_logout'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('cms_admin_dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)


class CustomAdminDashboardTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.client = Client(SERVER_NAME='testserver')
        self.user = User.objects.create_user('admin', password='pass', is_staff=True)
        self.client.login(username='admin', password='pass')

    def test_dashboard_renders(self):
        resp = self.client.get(reverse('cms_admin_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dashboard')

    def test_page_list_renders(self):
        resp = self.client.get(reverse('cms_admin_page_list'))
        self.assertEqual(resp.status_code, 200)

    def test_entity_list_renders(self):
        resp = self.client.get(reverse('cms_admin_entity_list'))
        self.assertEqual(resp.status_code, 200)

    def test_page_create(self):
        resp = self.client.post(reverse('cms_admin_page_create'), {
            'title': 'New Page',
            'path': '/new/',
            'template_name': 'cms/home.html',
            'sort_order': '0',
            'is_published': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Page.objects.filter(path='/new/', site=self.site).exists())

    def test_page_edit(self):
        page = Page.objects.create(
            site=self.site, path='/edit-me/', template_name='cms/home.html', title='Old'
        )
        resp = self.client.post(reverse('cms_admin_page_edit', args=[page.pk]), {
            'title': 'Updated',
            'path': '/edit-me/',
            'template_name': 'cms/home.html',
            'sort_order': '0',
            'is_published': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        page.refresh_from_db()
        self.assertEqual(page.title, 'Updated')

    def test_page_delete(self):
        page = Page.objects.create(
            site=self.site, path='/delete-me/', template_name='cms/home.html'
        )
        resp = self.client.post(reverse('cms_admin_page_delete', args=[page.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Page.objects.filter(pk=page.pk).exists())

    def test_entity_create(self):
        resp = self.client.post(reverse('cms_admin_entity_create'), {
            'entity_type': 'product',
            'slug': 'test-product',
            'is_published': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(ContentEntity.objects.filter(slug='test-product').exists())

    def test_entity_delete(self):
        entity = ContentEntity.objects.create(
            site=self.site, entity_type='product', slug='delete-me',
        )
        resp = self.client.post(reverse('cms_admin_entity_delete', args=[entity.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(ContentEntity.objects.filter(pk=entity.pk).exists())


class CustomAdminUserManagementTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.client = Client(SERVER_NAME='testserver')
        self.staff = User.objects.create_user('admin', password='pass', is_staff=True)
        self.client.login(username='admin', password='pass')

    def test_user_list_renders(self):
        resp = self.client.get(reverse('cms_admin_user_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'admin')

    def test_toggle_staff(self):
        user = User.objects.create_user('regular', password='pass', is_staff=False)
        resp = self.client.post(reverse('cms_admin_user_toggle_staff', args=[user.pk]))
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_toggle_active(self):
        user = User.objects.create_user('regular', password='pass', is_active=True)
        resp = self.client.post(reverse('cms_admin_user_toggle_active', args=[user.pk]))
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_cannot_toggle_self(self):
        resp = self.client.post(reverse('cms_admin_user_toggle_staff', args=[self.staff.pk]))
        self.assertEqual(resp.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)  # unchanged

    def test_non_staff_redirected_from_user_list(self):
        normal = User.objects.create_user('normal', password='pass', is_staff=False)
        self.client.login(username='normal', password='pass')
        resp = self.client.get(reverse('cms_admin_user_list'))
        self.assertEqual(resp.status_code, 302)


class CustomAdminSiteManagementTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get_or_create(domain='testserver', name='Test')[0]
        self.client = Client(SERVER_NAME='testserver')
        self.staff = User.objects.create_user('admin', password='pass', is_staff=True)
        self.client.login(username='admin', password='pass')

    def test_site_list_renders(self):
        resp = self.client.get(reverse('cms_admin_site_list'))
        self.assertEqual(resp.status_code, 200)

    def test_site_create(self):
        resp = self.client.post(reverse('cms_admin_site_create'), {
            'domain': 'new.example.com',
            'name': 'New Site',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Site.objects.filter(domain='new.example.com').exists())

    def test_site_edit(self):
        site_obj = Site.objects.create(domain='edit.example.com', name='Edit Me')
        resp = self.client.post(reverse('cms_admin_site_edit', args=[site_obj.pk]), {
            'domain': 'edited.example.com',
            'name': 'Edited',
        })
        self.assertEqual(resp.status_code, 302)
        site_obj.refresh_from_db()
        self.assertEqual(site_obj.domain, 'edited.example.com')

    def test_site_delete(self):
        site_obj = Site.objects.create(domain='delete.example.com', name='Delete Me')
        resp = self.client.post(reverse('cms_admin_site_delete', args=[site_obj.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Site.objects.filter(pk=site_obj.pk).exists())
