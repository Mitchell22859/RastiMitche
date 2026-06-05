from django.urls import path
from . import views_password_reset as views

urlpatterns = [
    path("", views.password_reset_form, name="password_reset"),
    path("select/", views.password_reset_select, name="password_reset_select"),
    path("verify/", views.password_reset_verify, name="password_reset_verify"),
    path("confirm/", views.password_reset_confirm, name="password_reset_confirm"),
]
