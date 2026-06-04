"""
Accounts - Forms.

Login forms for platform and tenant authentication.
"""
from django import forms


class PlatformLoginForm(forms.Form):
    """
    Login form for the platform owner panel (/loginlogin/).
    Uses phone + password authentication.
    """

    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            "placeholder": "Phone number",
            "class": "form-control",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Password",
            "class": "form-control",
        }),
    )


class TenantLoginForm(forms.Form):
    """
    Login form for tenant users (/<company_code>/login/).
    Uses phone + password authentication.
    """

    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            "placeholder": "Phone number",
            "class": "form-control",
            "autofocus": True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Password",
            "class": "form-control",
        }),
    )
