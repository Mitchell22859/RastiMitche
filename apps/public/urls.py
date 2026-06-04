"""
Public - URLs.

Public-facing pages served at root level (/, /features/, /pricing/, etc.)
"""
from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("features/", views.features, name="features"),
    path("pricing/", views.pricing, name="pricing"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("register/", views.register, name="register"),
    path("register/verify/", views.register_verify, name="register_verify"),
    path("register/resend-otp/", views.register_resend_otp, name="register_resend_otp"),
    path("register/success/", views.register_success, name="register_success"),
]
