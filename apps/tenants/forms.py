"""
Tenants - Forms.

Forms for public service request and admin management.
"""
from django import forms


class ServiceRequestForm(forms.Form):
    """Public service request form shown on /<company_code>/request/."""

    customer_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Full name", "class": "form-control"}),
    )
    customer_phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"placeholder": "Phone number", "class": "form-control"}),
    )
    customer_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "Email (optional)", "class": "form-control"}),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Service address", "class": "form-control", "rows": 2}),
    )
    service_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Describe your issue", "class": "form-control", "rows": 3}),
    )
    preferred_time = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Preferred time", "class": "form-control"}),
    )


class CompanyPageForm(forms.Form):
    """Admin form for editing company page settings."""

    title = forms.CharField(max_length=200, required=False)
    intro_text = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    contact_phone = forms.CharField(max_length=20, required=False)
    contact_email = forms.EmailField(required=False)
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    working_hours = forms.CharField(max_length=200, required=False)
    is_request_form_enabled = forms.BooleanField(required=False)
    is_published = forms.BooleanField(required=False)


class CompanyServiceForm(forms.Form):
    """Admin form for creating/editing company services."""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "عنوان خدمات"}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "توضیحات"}),
    )
    base_price = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "قیمت پایه (تومان)"}),
    )
    is_active = forms.BooleanField(required=False, initial=True)


class TechnicianCreateForm(forms.Form):
    """Admin form for creating a technician."""

    username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "مثلاً tech_ali", "style": "direction:ltr;"}),
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "09121234567", "style": "direction:ltr;"}),
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "رمز ورود؛ اگر خالی باشد changeme123"}),
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام"}),
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی"}),
    )
    is_available = forms.BooleanField(required=False, initial=True)
    skills = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "مهارت‌ها (با کاما جدا کنید)"}),
    )


class TechnicianEditForm(forms.Form):
    """Admin form for editing a technician."""

    username = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly", "style": "direction:ltr;background:#f1f5f9;"}),
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "09121234567", "style": "direction:ltr;"}),
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "برای تغییر رمز پر کنید"}),
    )
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    is_available = forms.BooleanField(required=False)
    skills = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "مهارت‌ها (با کاما جدا کنید)"}),
    )
