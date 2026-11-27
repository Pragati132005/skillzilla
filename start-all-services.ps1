[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipProfileBackend,
    [switch]$NoHealthWait
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$runDir = Join-Path $root '.run'
$logDir = Join-Path $runDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$services = @(
    @{ Name='Module 1 - JD Analytics'; Port=8020; Path='Module1-JDAnalyzer/radix-jd-analytics-main'; App='src.api:app'; Health='/health' },
    @{ Name='Module 2 - Resume Parser'; Port=8000; Path='Module2-ResumeParser/role2_resume_parsing'; App='resume_parser.api:app'; Health='/health' },
    @{ Name='Module 4 - Talent Check'; Port=8010; Path='Module4-TalentCheck'; App='talent_check'; Health='/health' },
    @{ Name='Module 5 - Skill Matching'; Port=8030; Path='Module5-SkillMatch/role5'; App='app.main:app'; Health='/health' }
)
if (-not $SkipProfileBackend) {
    $services += @{ Name='Profile Persistence'; Port=8040; Path='profilebackend'; App='profilebackend.main:app'; Health='/health' }
}

function Get-PythonForService([string]$servicePath) {
    $venvPython = Join-Path $root (Join-Path $servicePath '.venv/Scripts/python.exe')
    if (Test-Path $venvPython) { return $venvPython }
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    throw "Python was not found. Install Python or create .venv in $servicePath."
}

function Test-PortFree([int]$port) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return ($null -eq $listener)
}

Write-Host "`nStarting RADIX services from: $root" -ForegroundColor Cyan
$started = @()
foreach ($service in $services) {
    $workingDir = Join-Path $root $service.Path
    if (-not (Test-Path $workingDir)) { throw "Missing service folder: $workingDir" }
    if (-not (Test-PortFree $service.Port)) {
        Write-Host "[SKIP] $($service.Name): port $($service.Port) is already in use." -ForegroundColor Yellow
        continue
    }

    $python = Get-PythonForService $service.Path
    $stdout = Join-Path $logDir ("{0}.out.log" -f $service.Port)
    $stderr = Join-Path $logDir ("{0}.err.log" -f $service.Port)
    $processArgs = @('-m','uvicorn',$service.App,'--host','127.0.0.1','--port',[string]$service.Port)
    if ($python -like '*\py.exe') { $processArgs = @('-3') + $processArgs }

    $process = Start-Process -FilePath $python -ArgumentList $processArgs -WorkingDirectory $workingDir -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
    $started += [pscustomobject]@{ Name=$service.Name; Port=$service.Port; PID=$process.Id; Health=$service.Health }
    Write-Host "[STARTING] $($service.Name) on :$($service.Port) (PID $($process.Id))" -ForegroundColor Green
}

if (-not $SkipFrontend) {
    $frontend = Join-Path $root 'Module3-ProfileBuilder/JSScandidateportal-profilebuilder'
    if (-not (Test-Path (Join-Path $frontend 'package.json'))) { throw "Frontend package.json not found: $frontend" }
    if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
        Write-Host '[ERROR] Frontend dependencies are not installed. Run npm ci in the Module 3 folder first.' -ForegroundColor Red
    } else {
        $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
        if (-not $npm) { $npm = Get-Command npm -ErrorAction SilentlyContinue }
        if (-not $npm) { throw 'npm was not found. Install Node.js and npm.' }
        $frontOut = Join-Path $logDir '5173.out.log'
        $frontErr = Join-Path $logDir '5173.err.log'
        $proc = Start-Process -FilePath $npm.Source -ArgumentList @('run','dev','--','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory $frontend -RedirectStandardOutput $frontOut -RedirectStandardError $frontErr -PassThru -WindowStyle Hidden
        $started += [pscustomobject]@{ Name='Module 3 - Candidate Portal'; Port=5173; PID=$proc.Id; Health='/' }
        Write-Host "[STARTING] Module 3 - Candidate Portal on :5173 (PID $($proc.Id))" -ForegroundColor Green
    }
}

$started | ConvertTo-Json | Set-Content (Join-Path $runDir 'services.json') -Encoding UTF8

Write-Host "`nHealth checks skipped temporarily." -ForegroundColor Yellow

Write-Host "`nPortal: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API docs: http://localhost:8020/docs, :8000/docs, :8010/docs, :8030/docs, :8040/docs" -ForegroundColor DarkCyan
Write-Host "Logs: $logDir" -ForegroundColor DarkCyan
Write-Host 'Stop services with: .\stop-all-services.ps1' -ForegroundColor Yellow
