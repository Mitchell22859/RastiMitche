"""
Orders - Forms.

Forms for order creation and management.
"""
from django import forms

from .models import Order


class OrderCreateForm(forms.Form):
    """Form for creating a new order."""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "placeholder": "Order title",
            "class": "form-control",
        }),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "Description",
            "class": "form-control",
            "rows": 3,
        }),
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "placeholder": "Service address",
            "class": "form-control",
            "rows": 2,
        }),
    )
    priority = forms.ChoiceField(
        choices=Order.Priority.choices,
        initial=Order.Priority.NORMAL,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    price_estimate = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            "placeholder": "Price estimate",
            "class": "form-control",
        }),
    )
    required_skill = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "placeholder": "Required skill (optional)",
            "class": "form-control",
        }),
    )
    customer_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True,
    )
