"""
Tenants - Branding & Gallery Views.

Views for company admin to manage branding (logo, hero) and gallery images.
"""
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_tenant_role

from .models import CompanyGalleryImage, CompanyPage
from .selectors import CompanyGallerySelector, CompanyPageSelector
from .validators import validate_image_file


# =============================================================================
# BRANDING (LOGO + HERO + PAGE SETTINGS)
# =============================================================================


@require_tenant_role("COMPANY_ADMIN")
def admin_branding(request: HttpRequest, **kwargs) -> HttpResponse:
    """Branding page: edit logo, hero, title, intro, contact."""
    company = request.company
    page, _ = CompanyPage.objects.get_or_create(company=company)
    error = ""
    success = ""

    if request.method == "POST":
        # Text fields
        page.title = request.POST.get("title", page.title)
        page.intro_text = request.POST.get("intro_text", page.intro_text)
        page.contact_phone = request.POST.get("contact_phone", page.contact_phone)
        page.contact_email = request.POST.get("contact_email", page.contact_email)
        page.address = request.POST.get("address", page.address)
        page.working_hours = request.POST.get("working_hours", page.working_hours)
        page.is_request_form_enabled = "is_request_form_enabled" in request.POST
        page.is_published = "is_published" in request.POST

        # Logo upload
        if "logo" in request.FILES:
            logo_file = request.FILES["logo"]
            try:
                validate_image_file(logo_file)
                page.logo = logo_file
            except ValidationError as e:
                error = e.message
                return render(request, "tenants/admin_branding.html", {
                    "company": company, "page": page, "error": error,
                })

        # Hero image upload
        if "hero_image" in request.FILES:
            hero_file = request.FILES["hero_image"]
            try:
                validate_image_file(hero_file)
                page.hero_image = hero_file
            except ValidationError as e:
                error = e.message
                return render(request, "tenants/admin_branding.html", {
                    "company": company, "page": page, "error": error,
                })

        page.save()
        success = "تغییرات با موفقیت ذخیره شد."

    return render(request, "tenants/admin_branding.html", {
        "company": company, "page": page, "error": error, "success": success,
    })


# =============================================================================
# GALLERY CRUD
# =============================================================================


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def admin_gallery_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List all gallery images."""
    company = request.company
    images = CompanyGallerySelector.get_all_for_company(company=company)
    return render(request, "tenants/admin_gallery.html", {
        "company": company, "images": images,
    })


@require_tenant_role("COMPANY_ADMIN")
def admin_gallery_create(request: HttpRequest, **kwargs) -> HttpResponse:
    """Upload a new gallery image."""
    company = request.company
    error = ""

    if request.method == "POST":
        if "image" not in request.FILES:
            error = "لطفا یک تصویر انتخاب کنید."
        else:
            image_file = request.FILES["image"]
            try:
                validate_image_file(image_file)
                CompanyGalleryImage.objects.create(
                    company=company,
                    image=image_file,
                    caption=request.POST.get("caption", ""),
                    sort_order=int(request.POST.get("sort_order", 0)),
                    is_active="is_active" in request.POST,
                )
                return redirect(f"/{company.code}/admin/gallery/")
            except ValidationError as e:
                error = e.message

    return render(request, "tenants/admin_gallery_form.html", {
        "company": company, "error": error, "is_edit": False,
    })


@require_tenant_role("COMPANY_ADMIN")
def admin_gallery_edit(request: HttpRequest, image_id: int, **kwargs) -> HttpResponse:
    """Edit a gallery image (caption, order, active status)."""
    company = request.company
    image = CompanyGalleryImage.objects.filter(id=image_id, company=company).first()
    if not image:
        raise Http404("تصویر یافت نشد.")

    error = ""
    if request.method == "POST":
        image.caption = request.POST.get("caption", "")
        image.sort_order = int(request.POST.get("sort_order", 0))
        image.is_active = "is_active" in request.POST

        # Optional new image upload
        if "image" in request.FILES:
            image_file = request.FILES["image"]
            try:
                validate_image_file(image_file)
                image.image = image_file
            except ValidationError as e:
                error = e.message
                return render(request, "tenants/admin_gallery_form.html", {
                    "company": company, "image": image, "error": error, "is_edit": True,
                })

        image.save()
        return redirect(f"/{company.code}/admin/gallery/")

    return render(request, "tenants/admin_gallery_form.html", {
        "company": company, "image": image, "error": error, "is_edit": True,
    })


@require_tenant_role("COMPANY_ADMIN")
def admin_gallery_delete(request: HttpRequest, image_id: int, **kwargs) -> HttpResponse:
    """Delete a gallery image."""
    company = request.company
    image = CompanyGalleryImage.objects.filter(id=image_id, company=company).first()
    if not image:
        raise Http404("تصویر یافت نشد.")

    if request.method == "POST":
        image.delete()
        return redirect(f"/{company.code}/admin/gallery/")

    return render(request, "tenants/admin_gallery_delete.html", {
        "company": company, "image": image,
    })
