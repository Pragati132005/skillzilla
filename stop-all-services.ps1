$ErrorActionPreference = 'SilentlyContinue'
$runDir = Join-Path $PSScriptRoot '.run'
$manifest = Join-Path $runDir 'services.json'
if (-not (Test-Path $manifest)) { Write-Host 'No RADIX service manifest found.'; exit 0 }
$items = @(Get-Content $manifest -Raw | ConvertFrom-Json)
foreach ($item in $items) {
    $process = Get-Process -Id ([int]$item.PID) -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Write-Host "Stopped $($item.Name) (PID $($item.PID))"
    }
}
Remove-Item $manifest -Force
