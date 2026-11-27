[CmdletBinding()]
param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$projects = @(
    @{ Name='Module 1 - JD Analytics'; Path='Module1-JDAnalyzer/radix-jd-analytics-main'; Requirements='requirements.txt' },
    @{ Name='Module 2 - Resume Parser'; Path='Module2-ResumeParser/role2_resume_parsing'; Requirements='requirements.txt' },
    @{ Name='Module 4 - Talent Check'; Path='Module4-TalentCheck'; Requirements='requirements.txt' },
    @{ Name='Module 5 - Skill Matching'; Path='Module5-SkillMatch/role5'; Requirements='requirements.txt' },
    @{ Name='Profile Persistence'; Path='profilebackend'; Requirements='requirements.txt' }
)
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyLauncher) { throw 'Python launcher "py" not found. Install Python 3.11+ and enable the Python launcher.' }

foreach ($project in $projects) {
    $folder = Join-Path $root $project.Path
    $venv = Join-Path $folder '.venv'
    $python = Join-Path $venv 'Scripts/python.exe'
    if (-not (Test-Path $python)) {
        Write-Host "Creating virtual environment: $($project.Name)" -ForegroundColor Cyan
        & $pyLauncher.Source -3 -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw "Could not create venv for $($project.Name)" }
    }
    Write-Host "Installing dependencies: $($project.Name)" -ForegroundColor Cyan
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $folder $project.Requirements)
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed for $($project.Name)" }
}

if (-not $SkipFrontend) {
    $frontend = Join-Path $root 'Module3-ProfileBuilder/JSScandidateportal-profilebuilder'
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js/npm not found. Install Node.js 20 LTS or newer.' }
    Push-Location $frontend
    try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'npm ci failed for Module 3 frontend.' } }
    finally { Pop-Location }
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host 'Before launching: create profilebackend/.env from profilebackend/.env.example and set DATABASE_URL.' -ForegroundColor Yellow
Write-Host 'If Module 2 or Module 1 needs live Gemini extraction, configure its own .env from its .env.example.' -ForegroundColor Yellow
Write-Host 'Then run: .\start-all-services.ps1' -ForegroundColor Cyan
