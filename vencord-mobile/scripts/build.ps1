param(
    [string]$VencordPath = (Join-Path $PSScriptRoot "..\.vendor\Vencord"),
    [string]$PnpmPath = (Join-Path $PSScriptRoot "..\.tools\pnpm\pnpm.exe"),
    [string]$NodeDirectory = (Join-Path $PSScriptRoot "..\.tools\node-v26.10.0-win-x64"),
    [ValidateSet("Web", "Desktop", "Both")]
    [string]$Target = "Both",
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vencordRoot = (Resolve-Path $VencordPath).Path
$pluginSource = Join-Path $projectRoot "plugin\mobileUX"
$pluginTarget = Join-Path $vencordRoot "src\userplugins\mobileUX"
$legacyPluginTarget = Join-Path $vencordRoot "src\userplugins\mobileUX.browser"
$output = Join-Path $projectRoot "build"

if (-not (Test-Path $PnpmPath)) {
    $PnpmPath = (Get-Command pnpm -ErrorAction Stop).Source
}

$pnpmDirectory = Split-Path (Resolve-Path $PnpmPath).Path -Parent
$env:Path = "$pnpmDirectory;$env:Path"

if (Test-Path (Join-Path $NodeDirectory "node.exe")) {
    $env:Path = "$NodeDirectory;$env:Path"
}

New-Item -ItemType Directory -Force (Split-Path $pluginTarget -Parent) | Out-Null
if (Test-Path $legacyPluginTarget) {
    Remove-Item -LiteralPath $legacyPluginTarget -Recurse -Force
}
if (Test-Path $pluginTarget) {
    Remove-Item -LiteralPath $pluginTarget -Recurse -Force
}
Copy-Item -Recurse -Force $pluginSource $pluginTarget

Push-Location $vencordRoot
try {
    if ($Target -in @("Web", "Both")) {
        $webArguments = @("buildWebStandalone", "--skip-extension")
        if ($Dev) { $webArguments += "--dev" }
        & $PnpmPath @webArguments
        if ($LASTEXITCODE -ne 0) { throw "Vencord web build failed with exit code $LASTEXITCODE" }
    }

    if ($Target -in @("Desktop", "Both")) {
        $desktopArguments = @("build")
        if ($Dev) { $desktopArguments += "--dev" }
        & $PnpmPath @desktopArguments
        if ($LASTEXITCODE -ne 0) { throw "Vencord desktop build failed with exit code $LASTEXITCODE" }
    }
}
finally {
    Pop-Location
}

New-Item -ItemType Directory -Force $output | Out-Null
if ($Target -in @("Web", "Both")) {
    Copy-Item -Force (Join-Path $vencordRoot "dist\browser.js") $output
    Copy-Item -Force (Join-Path $vencordRoot "dist\browser.css") $output
}
if ($Target -in @("Desktop", "Both")) {
    Copy-Item -Force (Join-Path $vencordRoot "dist\renderer.js") $output
    Copy-Item -Force (Join-Path $vencordRoot "dist\renderer.css") $output
}
Copy-Item -Force (Join-Path $projectRoot "theme\MobileUX.theme.css") $output

Write-Host "Built $Target Vencord assets and MobileUX.theme.css in $output"
