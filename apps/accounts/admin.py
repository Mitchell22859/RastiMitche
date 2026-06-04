from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CompanyUser, Customer, Technician, TechnicianCategorySkill, TechnicianSkill


@admin.register(CompanyUser)
class CompanyUserAdmin(BaseUserAdmin):
    list_display = ["phone", "first_name", "last_name", "role", "company", "is_active"]
    list_filter = ["role", "is_active", "company"]
    search_fields = ["phone", "first_name", "last_name", "email"]
    ordering = ["-date_joined"]

    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "email")}),
        ("Company", {"fields": ("company", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {"fields": ("phone", "password1", "password2", "company", "role")}),
    )


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "is_available", "rating"]
    list_filter = ["is_available", "company"]


@admin.register(TechnicianSkill)
class TechnicianSkillAdmin(admin.ModelAdmin):
    list_display = ["technician", "name", "level"]
    list_filter = ["level"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "phone", "company"]
    list_filter = ["company"]
    search_fields = ["first_name", "last_name", "phone"]



@admin.register(TechnicianCategorySkill)
class TechnicianCategorySkillAdmin(admin.ModelAdmin):
    list_display = ["technician", "category", "priority"]
    list_filter = ["priority", "category"]
    search_fields = ["technician__user__first_name", "technician__user__last_name"]
