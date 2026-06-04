$ErrorActionPreference = "Stop"

Set-Location "D:\mySaaSsite\current_project"

Write-Host ""
Write-Host "==== Django system check ===="
python manage.py check

Write-Host ""
Write-Host "==== Migration sync check ===="
python manage.py makemigrations --check --dry-run

Write-Host ""
Write-Host "==== Migration plan ===="
python manage.py migrate --plan

Write-Host ""
Write-Host "==== Ensure no test files remain ===="
$testFiles = Get-ChildItem -Path . -File -Recurse -Include "tests.py","tests_*.py","test_*.py" -ErrorAction SilentlyContinue
if ($testFiles.Count -gt 0) {
    Write-Host "[FAIL] Test files still exist:"
    $testFiles | ForEach-Object { Write-Host $_.FullName }
    exit 1
}
Write-Host "[OK] No test files found."

Write-Host ""
Write-Host "==== Seeded URL smoke check ===="
python manage.py smoke_seeded_urls --company-code n54

Write-Host ""
Write-Host "[DONE] Tech panel smoke check completed."
