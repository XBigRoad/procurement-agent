Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        if ($uvCommand) {
            & uv venv .venv --python 3.13
        } else {
            & python -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) { throw 'Python 虚拟环境创建失败，请检查 Python 3.11+ 是否可用。' }
    }
    if ($uvCommand) {
        & uv pip install --python $pythonPath --requirement requirements-lock.txt
        if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
        & uv pip install --python $pythonPath --no-deps -e .
    } else {
        & $pythonPath -m pip install --requirement requirements-lock.txt
        if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
        & $pythonPath -m pip install --no-deps -e .
    }
    if ($LASTEXITCODE -ne 0) { throw '采购审核程序安装失败。' }
    & $pythonPath -m procurement_agent --help
    if ($LASTEXITCODE -ne 0) { throw '安装后的命令检查失败。' }
    Write-Host '安装完成。运行 scripts/start.ps1 或双击 启动采购审核.cmd。'
} finally {
    Pop-Location
}
