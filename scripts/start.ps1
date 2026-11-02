param([ValidateRange(1024, 65535)][int]$Port = 8511)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $PSScriptRoot 'install.ps1')
}
Push-Location -LiteralPath $projectRoot
try {
    Write-Host "本机访问：http://127.0.0.1:$Port"
    & $pythonPath -m procurement_agent serve --port $Port
    if ($LASTEXITCODE -ne 0) { throw '启动失败，请检查端口占用和终端错误。' }
} finally {
    Pop-Location
}
