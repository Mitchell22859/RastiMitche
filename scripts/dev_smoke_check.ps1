# dev_smoke_check.ps1
# Safe daily smoke check for RastiService.

param(
    [string]$CurrentProject = "D:\mySaaSsite\current_project"
)

$ErrorActionPreference = "Stop"

function Run-Cmd {
    param(
        [string]$File,
        [string[]]$Args
    )
    Write-Host "> $File $($Args -join ' ')" -ForegroundColor DarkGray
    & $File @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $File $($Args -join ' ')"
    }
}

if (-not (Test-Path (Join-Path $CurrentProject "manage.py"))) {
    throw "manage.py not found at $CurrentProject"
}

Set-Location $CurrentProject

Write-Host ""
Write-Host "Checking that test files are absent..." -ForegroundColor Cyan
$tests = Get-ChildItem -Path $CurrentProject -Recurse -File -Include "tests.py","tests_*.py","test_*.py" -ErrorAction SilentlyContinue
if ($tests.Count -gt 0) {
    $tests | Select-Object FullName | Format-Table -AutoSize
    throw "Test files still exist."
}
Write-Host "[OK] No test files found." -ForegroundColor Green

Write-Host ""
Write-Host "Running Django system check..." -ForegroundColor Cyan
Run-Cmd "python" @("manage.py", "check")

Write-Host ""
Write-Host "Checking migrations..." -ForegroundColor Cyan
Run-Cmd "python" @("manage.py", "makemigrations", "--check", "--dry-run")

Write-Host ""
Write-Host "Showing migrate plan..." -ForegroundColor Cyan
Run-Cmd "python" @("manage.py", "migrate", "--plan")

Write-Host ""
Write-Host "[OK] Smoke check completed." -ForegroundColor Green
