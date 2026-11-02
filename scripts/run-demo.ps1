Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { & (Join-Path $PSScriptRoot 'install.ps1') }
Push-Location -LiteralPath $projectRoot
try {
    $outputDirectory = Join-Path $projectRoot ('output\' + (Get-Date -Format 'yyyy-MM-dd'))
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    & $pythonPath -m procurement_agent compare --quotes samples/v1/quotes.json --history samples/v1/history.json --market samples/v1/market.json --as-of 2026-11-02 --output (Join-Path $outputDirectory 'comparison.json') --report (Join-Path $outputDirectory 'comparison.xlsx') --advice (Join-Path $outputDirectory '采购建议.md') --review-template (Join-Path $outputDirectory 'review-template.json')
    if ($LASTEXITCODE -ne 0) { throw '正常报价演示失败。' }
    & $pythonPath -m procurement_agent compare --quotes samples/v1/quotes-low.json --history samples/v1/history.json --market samples/v1/market.json --as-of 2026-11-02 --output (Join-Path $outputDirectory 'low-price.json') --report (Join-Path $outputDirectory '异常低价.xlsx') --advice (Join-Path $outputDirectory '异常低价建议.md') --review-template (Join-Path $outputDirectory 'low-price-review-template.json')
    if ($LASTEXITCODE -ne 0) { throw '异常低价演示失败。' }
    & $pythonPath -m procurement_agent templates --directory (Join-Path $outputDirectory '输入模板')
    if ($LASTEXITCODE -ne 0) { throw '输入模板生成失败。' }
    Write-Host "演示文件已生成：$outputDirectory"
} finally {
    Pop-Location
}
