from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction


PASSWORD = "123456"


def field_names(model):
    return {f.name for f in model._meta.get_fields() if hasattr(f, "attname")}


def set_if_exists(obj, name, value):
    if name in field_names(obj.__class__):
        setattr(obj, name, value)


def set_role(user, wanted):
    names = field_names(user.__class__)
    if "role" not in names:
        return

    field = user.__class__._meta.get_field("role")
    choices = list(getattr(field, "choices", None) or [])
    wanted = wanted.lower()

    for value, label in choices:
        haystack = f"{value} {label}".lower()
        if wanted in haystack:
            user.role = value
            return

    # Common fallbacks used by this project across branches.
    fallback_values = {
        "platform_owner": ["PLATFORM_OWNER", "platform_owner", "platform"],
        "company_admin": ["COMPANY_ADMIN", "company_admin", "admin"],
    }

    for candidate in fallback_values.get(wanted, [wanted]):
        if choices:
            valid_values = [value for value, _label in choices]
            if candidate in valid_values:
                user.role = candidate
                return
        else:
            user.role = candidate
            return

    user.role = wanted


def ensure_company():
    Company = apps.get_model("tenants", "Company")

    company = None
    names = field_names(Company)

    if "code" in names:
        company = Company.objects.filter(code="n54").first()
    elif "slug" in names:
        company = Company.objects.filter(slug="n54").first()

    if company is None:
        company = Company()

    set_if_exists(company, "code", "n54")
    set_if_exists(company, "slug", "n54")
    set_if_exists(company, "name", "شرکت n54")
    set_if_exists(company, "title", "شرکت n54")
    set_if_exists(company, "display_name", "شرکت n54")
    set_if_exists(company, "email", "n54@example.com")
    set_if_exists(company, "phone", "09170000054")
    set_if_exists(company, "mobile", "09170000054")
    set_if_exists(company, "address", "تهران")
    set_if_exists(company, "is_active", True)
    set_if_exists(company, "status", "active")

    company.save()
    return company


def ensure_user(username, password, phone, email, company, role, is_platform=False):
    User = get_user_model()
    user = User.objects.filter(username=username).first()

    if user is None:
        user = User(username=username)

    set_if_exists(user, "company", company)
    set_if_exists(user, "phone", phone)
    set_if_exists(user, "mobile", phone)
    set_if_exists(user, "email", email)
    set_if_exists(user, "first_name", username)
    set_if_exists(user, "last_name", "")

    set_role(user, role)

    set_if_exists(user, "is_active", True)
    set_if_exists(user, "is_staff", bool(is_platform))
    set_if_exists(user, "is_superuser", bool(is_platform))

    user.set_password(password)
    user.save()
    return user


with transaction.atomic():
    company = ensure_company()

    platform_owner = ensure_user(
        username="platform_owner",
        password=PASSWORD,
        phone="09170000000",
        email="platform@example.com",
        company=None,
        role="platform_owner",
        is_platform=True,
    )

    n54_admin = ensure_user(
        username="n54_admin",
        password=PASSWORD,
        phone="09170000054",
        email="n54@example.com",
        company=company,
        role="company_admin",
        is_platform=False,
    )

for command_name in ("ensure_sms_master_templates", "seed_sms_templates"):
    try:
        call_command(command_name, verbosity=1)
        print(f"SMS templates ensured by: {command_name}")
        break
    except CommandError:
        continue

User = get_user_model()
Company = apps.get_model("tenants", "Company")

print("")
print("MINIMAL SEED COMPLETED")
print("=" * 60)
print("companies:", list(Company.objects.values_list("code", "name")))
print("users:", list(User.objects.values_list("username", "role", "is_superuser")))
print("")
print("Logins:")
print("platform_owner / 123456")
print("n54_admin      / 123456")
print("")
print("URLs:")
print("http://127.0.0.1:8000/")
print("http://127.0.0.1:8000/login/")
print("http://127.0.0.1:8000/owner-platform/")
print("http://127.0.0.1:8000/n54/admin/")
