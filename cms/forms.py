"""
Forms for AgoCMS custom admin panel and user management.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.sites.models import Site

from .models import ContentBlock, ContentEntity, Page

User = get_user_model()


# ---------------------------------------------------------------------------
# Authentication forms
# ---------------------------------------------------------------------------


class CMSLoginForm(AuthenticationForm):
    """Custom login form with Tailwind styling."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Password',
        })
    )


class CMSRegistrationForm(UserCreationForm):
    """User registration form with Tailwind styling."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Email address',
        }),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        widget_attrs = {
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
        }
        self.fields['username'].widget.attrs.update({
            **widget_attrs,
            'placeholder': 'Username',
        })
        self.fields['password1'].widget.attrs.update({
            **widget_attrs,
            'placeholder': 'Password',
        })
        self.fields['password2'].widget.attrs.update({
            **widget_attrs,
            'placeholder': 'Confirm password',
        })


# ---------------------------------------------------------------------------
# Page forms
# ---------------------------------------------------------------------------


class PageForm(forms.ModelForm):
    """Form for creating/editing CMS pages."""

    class Meta:
        model = Page
        fields = ['title', 'path', 'template_name', 'parent', 'sort_order', 'is_published']

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        widget_attrs = {
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
        }
        for field_name in self.fields:
            field = self.fields[field_name]
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500',
                })
            else:
                field.widget.attrs.update(widget_attrs)

        if site:
            self.fields['parent'].queryset = Page.objects.filter(site=site)
        else:
            self.fields['parent'].queryset = Page.objects.none()


# ---------------------------------------------------------------------------
# Content Entity forms
# ---------------------------------------------------------------------------


class ContentEntityForm(forms.ModelForm):
    """Form for creating/editing content entities."""

    class Meta:
        model = ContentEntity
        fields = ['entity_type', 'slug', 'template_name', 'is_published']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        widget_attrs = {
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
        }
        for field_name in self.fields:
            field = self.fields[field_name]
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({
                    'class': 'h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500',
                })
            else:
                field.widget.attrs.update(widget_attrs)


# ---------------------------------------------------------------------------
# Site forms
# ---------------------------------------------------------------------------


class SiteForm(forms.ModelForm):
    """Form for creating/editing sites."""

    class Meta:
        model = Site
        fields = ['domain', 'name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        widget_attrs = {
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
        }
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update(widget_attrs)
