param(
    [string]$Image,
    [string]$Output,
    [int]$Steps = 30,
    [int]$Resolution = 256
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonExe = Join-Path $projectRoot 'work\hunyuan2mini\.venv\Scripts\python.exe'
$scriptPath = Join-Path $PSScriptRoot 'generate_shape.py'
$arguments = @('-u', $scriptPath, '--steps', $Steps, '--resolution', $Resolution)
if ($Image) { $arguments += @('--image', $Image) }
if ($Output) { $arguments += @('--output', $Output) }
& $pythonExe @arguments
exit $LASTEXITCODE
