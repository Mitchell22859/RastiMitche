# Phase 20D cleanup: remove obsolete subcategory templates that are no longer routed or used.
$ErrorActionPreference = 'SilentlyContinue'
Remove-Item "templates\tenants\admin_base_subcategories.html" -Force
Remove-Item "templates\tenants\admin_base_subcategory_form.html" -Force
Remove-Item "templates\tenants\admin_base_subcategory_delete.html" -Force
Write-Host "Phase 20D cleanup complete: obsolete subcategory templates removed."
