"""
Change-password-required flow.
Shown after login when user has the default password (123456) or must_change_password=True.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone


@login_required(login_url="/login/")
def change_password_required(request: HttpRequest) -> HttpResponse:
    user = request.user
    error = ""
    do_later = request.POST.get("do_later") == "1"

    if do_later:
        request.session["pw_change_snoozed"] = True
        from apps.accounts.services import RedirectService
        return redirect(RedirectService.get_post_login_url(user=user))

    if request.method == "POST":
        current_pw = request.POST.get("current_password", "")
        new_pw = request.POST.get("new_password", "")
        confirm_pw = request.POST.get("confirm_password", "")

        if not user.check_password(current_pw):
            error = "رمز عبور فعلی اشتباه است."
        elif len(new_pw) < 6:
            error = "رمز عبور جدید باید حداقل ۶ کاراکتر باشد."
        elif new_pw != confirm_pw:
            error = "تکرار رمز عبور جدید مطابقت ندارد."
        elif new_pw == "123456":
            error = "رمز عبور جدید نمی‌تواند همان رمز پیش‌فرض باشد."
        else:
            user.set_password(new_pw)
            user.must_change_password = False
            user.password_changed_at = timezone.now()
            user.save(update_fields=["password", "must_change_password", "password_changed_at"])
            # Re-login to keep session alive after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            request.session.pop("pw_change_snoozed", None)
            from apps.accounts.services import RedirectService
            return redirect(RedirectService.get_post_login_url(user=user))

    return render(request, "accounts/change_password_required.html", {"error": error})
