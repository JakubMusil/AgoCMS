# AgoCMS

A modern, flexible Django-based Content Management System with hierarchical pages, inline editing, multi-site support, and a clean custom admin panel.

---

## Features

- **Hierarchical Pages** — Create multi-level page trees with parent-child relationships, breadcrumb navigation, and ordered siblings
- **Inline Editing** — Edit content directly on your pages with a floating overlay panel (text, rich text, images, numbers, colors, booleans, URLs, dates)
- **Multi-Site Support** — Manage multiple websites from a single installation using Django's Sites framework
- **Custom Admin Panel** — Modern, clean admin interface built with Tailwind CSS (no Django built-in admin dependency)
- **User Management** — Registration, login/logout, staff/member roles, user activation
- **Content Entities** — Flexible JSON-based content model for products, blog posts, and any content type
- **Template-Driven Schema** — Field definitions are discovered automatically from your templates
- **Drag & Drop Lists** — Reorderable list blocks with drag-and-drop support
- **Live Preview** — Preview content changes before publishing

---

## Installation

### Prerequisites

- Python 3.10+
- pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/JakubMusil/AgoCMS.git
cd AgoCMS

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Create a superuser for the admin panel
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(insecure dev key)* | Django secret key for production |
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hosts |
| `DB_ENGINE` | `django.db.backends.sqlite3` | Database engine |
| `DB_NAME` | `db.sqlite3` | Database name or path |
| `DB_USER` | *(empty)* | Database user (PostgreSQL) |
| `DB_PASSWORD` | *(empty)* | Database password (PostgreSQL) |
| `DB_HOST` | *(empty)* | Database host |
| `DB_PORT` | *(empty)* | Database port |

### PostgreSQL Setup

```bash
export DB_ENGINE=django.db.backends.postgresql
export DB_NAME=agocms
export DB_USER=postgres
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
export DB_PORT=5432

python manage.py migrate
```

---

## Usage

### Accessing the Admin Panel

Visit `http://localhost:8000/cms-admin/` to access the custom admin panel. Features include:

- **Dashboard** — Overview of pages, content entities, blocks, and users
- **Pages** — Create and manage hierarchical pages with parent-child relationships
- **Content Entities** — Manage products, blog posts, and other content types
- **Users** — Manage user accounts, toggle staff status, activate/deactivate
- **Sites** — Manage multiple websites and domains

### Creating Hierarchical Pages

Pages support parent-child relationships for building navigation trees:

```
Home (/)
├── About (/about/)
│   ├── Team (/about/team/)
│   └── History (/about/history/)
├── Blog (/blog/)
│   ├── Tech (/blog/tech/)
│   └── News (/blog/news/)
└── Contact (/contact/)
```

In the admin panel, set a page's **Parent** field to create hierarchy. Child pages are automatically accessible via `page.get_children()` and breadcrumbs via `page.get_breadcrumbs()` in templates.

### Inline Editing

1. Log in as a staff user
2. Click the floating **Edit** toggle button on any page
3. Click on editable blocks to open the sidebar editor
4. Make changes and save

### Template Tags

AgoCMS provides custom template tags for building editable pages:

```html
{% load cms_tags %}

{# Single editable block #}
{% editable "hero" type="single" scope="local" %}
<section>
    <h1>{% item "heading" type="text" %}</h1>
    <p>{% item "description" type="richtext" %}</p>
    <img src="{% item "image" type="image" %}">
</section>
{% endeditable %}

{# List block with multiple items #}
{% cms_list "features" scope="local" %}
<div>
    <h3>{% item "title" type="text" %}</h3>
    <p>{% item "description" type="text" %}</p>
</div>
{% endcms_list %}

{# Read a single value from a block #}
{% cms_value "footer" "copyright" %}

{# Edit mode toggle for staff #}
{% cms_edit_toggle %}
```

**Supported field types:** `text`, `richtext`, `image`, `number`, `color`, `boolean`, `url`, `date`

**Scope options:** `local` (per-page) or `global` (site-wide)

### Content Entities

Content entities are flexible JSON-based records for any content type:

```python
# Create a product via Django shell
from cms.models import ContentEntity
from django.contrib.sites.models import Site

site = Site.objects.get_current()
entity = ContentEntity.objects.create(
    site=site,
    entity_type='product',
    data={
        'title': 'Blue Widget',
        'price': 29.99,
        'description': '<p>A premium blue widget.</p>',
    },
    template_name='cms/product_detail.html',
)
# slug auto-generated: 'blue-widget'
# search_index auto-populated from data
```

Entities are routed by slug — visiting `/blue-widget/` renders the entity's template.

### Breadcrumb Navigation in Templates

Use the `breadcrumbs` context variable in your templates:

```html
<nav>
    <ol>
        {% for crumb in breadcrumbs %}
        <li>
            {% if not forloop.last %}
            <a href="{{ crumb.path }}">{{ crumb.title }}</a> /
            {% else %}
            <span>{{ crumb.title }}</span>
            {% endif %}
        </li>
        {% endfor %}
    </ol>
</nav>
```

### Child Page Navigation

Display child pages for hierarchical navigation:

```html
{% if child_pages %}
<ul>
    {% for child in child_pages %}
    <li><a href="{{ child.path }}">{{ child.title }}</a></li>
    {% endfor %}
</ul>
{% endif %}
```

---

## Examples

The `templates/cms/examples/` directory contains ready-to-use templates:

### 1. Landing Page (`cms/examples/landing.html`)
A conversion-focused landing page with hero section, benefits list, testimonials, and call-to-action blocks.

### 2. Blog (`cms/examples/blog.html`)
A blog template with breadcrumb navigation, post listing as a list block, and child page categories.

### 3. Portfolio (`cms/examples/portfolio.html`)
A portfolio/showcase template with project cards featuring images, categories, and descriptions.

### 4. Contact (`cms/examples/contact.html`)
A contact page with editable contact information, address/email/phone fields, and a contact form layout.

### 5. Home Page (`cms/home.html`)
The default home page with hero, about section, and feature list blocks.

### 6. Product Detail (`cms/product_detail.html`)
A product detail page with product info block and related products list.

### Using Example Templates

To use an example template, create a page in the admin panel and set its template to one of the example paths:

1. Go to `http://localhost:8000/cms-admin/pages/create/`
2. Set the **Template name** to `cms/examples/blog.html`
3. Set the **Path** and **Title**
4. Optionally set a **Parent** page for hierarchy
5. Save and visit the page
6. Toggle edit mode to add content

---

## Project Structure

```
AgoCMS/
├── agocms/                    # Django project settings
│   ├── settings.py            # Configuration with env var support
│   ├── urls.py                # Root URL routing
│   ├── wsgi.py                # WSGI entry point
│   └── asgi.py                # ASGI entry point
├── cms/                       # Main CMS application
│   ├── models.py              # Page, ContentEntity, ContentBlock, SchemaEntry
│   ├── views.py               # Page routing, API endpoints
│   ├── admin_views.py         # Custom admin panel views
│   ├── admin_panel_urls.py    # Custom admin URL routing
│   ├── forms.py               # Forms for admin panel
│   ├── admin.py               # Django admin registration
│   ├── middleware.py           # Site resolution middleware
│   ├── context_processors.py  # CMS context injection
│   ├── schema_registry.py     # Template schema discovery
│   ├── api_urls.py            # CMS API endpoints
│   ├── urls.py                # Catch-all page routing
│   ├── tests.py               # Comprehensive test suite
│   ├── templatetags/
│   │   └── cms_tags.py        # Template tags (editable, item, cms_list, etc.)
│   └── migrations/
├── templates/cms/
│   ├── base.html              # Base template with Tailwind, Alpine.js, htmx
│   ├── home.html              # Home page template
│   ├── product_detail.html    # Product detail template
│   ├── admin_overlay.html     # Inline editing overlay
│   ├── admin/                 # Custom admin panel templates
│   │   ├── base.html          # Admin layout with sidebar
│   │   ├── login.html         # Login page
│   │   ├── register.html      # Registration page
│   │   ├── dashboard.html     # Admin dashboard
│   │   ├── page_list.html     # Page management
│   │   ├── page_form.html     # Page create/edit form
│   │   ├── entity_list.html   # Entity management
│   │   ├── entity_form.html   # Entity create/edit form
│   │   ├── user_list.html     # User management
│   │   ├── site_list.html     # Site management
│   │   └── site_form.html     # Site create/edit form
│   └── examples/              # Example templates
│       ├── blog.html          # Blog template
│       ├── contact.html       # Contact page template
│       ├── landing.html       # Landing page template
│       └── portfolio.html     # Portfolio template
├── requirements.txt
├── manage.py
└── README.md
```

---

## Running Tests

```bash
python manage.py test cms
```

The test suite covers models, views, template tags, middleware, API endpoints, hierarchical pages, custom admin panel, user management, and site management (60+ tests).

---

## License

See [LICENSE](LICENSE) for details.