$ErrorActionPreference = "Stop"

Set-Location "D:\mySaaSsite\current_project"

Write-Host ""
Write-Host "==== Django check ===="
python manage.py check

Write-Host ""
Write-Host "==== Migration sync check ===="
python manage.py makemigrations --check --dry-run

Write-Host ""
Write-Host "==== Auto-sync verification ===="
python manage.py sync_sms_notification_settings --company-code n54 --source notification
python manage.py verify_auto_notification_sync --company-code n54

Write-Host ""
Write-Host "==== Notification event matrix ===="
python manage.py notification_event_matrix --company-code n54 --repair

Write-Host ""
Write-Host "[DONE] Notification matrix check completed."