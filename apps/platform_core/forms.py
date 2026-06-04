"""
Platform Core - Forms.

Forms for platform owner management: companies, plans, subscriptions.
"""
from django import forms

from .models import Plan, Subscription


class CompanyCreateForm(forms.Form):
    """Form for creating a new company."""
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام شرکت"}))
    code = forms.SlugField(max_length=50, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "کد شرکت (لاتین، بدون فاصله)"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "ایمیل"}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "تلفن"}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "آدرس"}))


class CompanyEditForm(forms.Form):
    """Form for editing a company."""
    name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))


class PlanForm(forms.Form):
    """Form for creating/editing plans."""
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام پلن"}))
    code = forms.SlugField(max_length=50, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "کد پلن"}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))
    price_monthly = forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "قیمت ماهانه"}))
    price_yearly = forms.IntegerField(required=False, initial=0, widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "قیمت سالانه"}))
    max_users = forms.IntegerField(initial=5, widget=forms.NumberInput(attrs={"class": "form-control"}))
    max_technicians = forms.IntegerField(initial=10, widget=forms.NumberInput(attrs={"class": "form-control"}))
    max_orders_per_month = forms.IntegerField(initial=100, widget=forms.NumberInput(attrs={"class": "form-control"}))
    is_active = forms.BooleanField(required=False, initial=True)


class SubscriptionForm(forms.Form):
    """Form for creating/editing subscriptions."""
    company_id = forms.IntegerField(widget=forms.Select(attrs={"class": "form-control"}))
    plan_id = forms.IntegerField(widget=forms.Select(attrs={"class": "form-control"}))
    status = forms.ChoiceField(choices=Subscription.Status.choices, widget=forms.Select(attrs={"class": "form-control"}))
    started_at = forms.DateTimeField(widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "YYYY-MM-DD HH:MM"}))
    expires_at = forms.DateTimeField(widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "YYYY-MM-DD HH:MM"}))
