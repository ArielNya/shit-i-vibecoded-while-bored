param(
    [switch]$RestartCanary,
    [int]$DebugPort = 9222
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$builtDist = Join-Path $projectRoot ".vendor\Vencord\dist"
$vencordRoot = Join-Path $env:APPDATA "Vencord"
$installedDist = Join-Path $vencordRoot "dist"
$settingsPath = Join-Path $vencordRoot "settings\settings.json"
$quickCssPath = Join-Path $vencordRoot "settings\quickCss.css"
$themePath = Join-Path $projectRoot "theme\MobileUX.theme.css"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $projectRoot "build\canary-backup-$timestamp"

foreach ($required in @(
    (Join-Path $builtDist "renderer.js"),
    (Join-Path $builtDist "renderer.css"),
    $settingsPath,
    $quickCssPath,
    $themePath
)) {
    if (-not (Test-Path $required)) { throw "Missing required file: $required" }
}

Get-Process Discord, DiscordCanary -ErrorAction SilentlyContinue |
    Stop-Process -Force

New-Item -ItemType Directory -Force $backup | Out-Null
Copy-Item -Force (Join-Path $installedDist "renderer.js") $backup
Copy-Item -Force (Join-Path $installedDist "renderer.css") $backup
Copy-Item -Force $settingsPath $backup
Copy-Item -Force $quickCssPath $backup

Copy-Item -Force (Join-Path $builtDist "renderer.js") $installedDist
Copy-Item -Force (Join-Path $builtDist "renderer.css") $installedDist

$settings = Get-Content -Raw $settingsPath | ConvertFrom-Json
if (-not $settings.plugins.PSObject.Properties["MobileUX"]) {
    $settings.plugins | Add-Member -NotePropertyName "MobileUX" -NotePropertyValue ([pscustomobject]@{})
}
$settings.plugins.MobileUX | Add-Member -Force -NotePropertyName "enabled" -NotePropertyValue $true
$settings.plugins.MobileUX | Add-Member -Force -NotePropertyName "activation" -NotePropertyValue "on"
$settings.plugins.MobileUX | Add-Member -Force -NotePropertyName "density" -NotePropertyValue "comfortable"
$settings.plugins.MobileUX | Add-Member -Force -NotePropertyName "fontSize" -NotePropertyValue "medium"
$settings.useQuickCss = $true
$settingsJson = $settings | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($settingsPath, $settingsJson, (New-Object System.Text.UTF8Encoding($false)))

$startMarker = "/* --- Mobile UX test theme: start --- */"
$endMarker = "/* --- Mobile UX test theme: end --- */"
$quickCss = Get-Content -Raw $quickCssPath
if ($null -eq $quickCss) { $quickCss = "" }
$escapedStart = [regex]::Escape($startMarker)
$escapedEnd = [regex]::Escape($endMarker)
$quickCss = [regex]::Replace($quickCss, "$escapedStart[\s\S]*?$escapedEnd\s*", "")
$theme = Get-Content -Raw $themePath
"$quickCss`r`n$startMarker`r`n$theme`r`n$endMarker`r`n" |
    Set-Content -Encoding UTF8 $quickCssPath

Write-Host "Installed desktop test build. Backup: $backup"

if ($RestartCanary) {
    $canary = Get-ChildItem (Join-Path $env:LOCALAPPDATA "DiscordCanary") -Directory |
        Where-Object Name -Like "app-*" |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "DiscordCanary.exe" } |
        Where-Object { Test-Path $_ } |
        Select-Object -First 1

    if (-not $canary) { throw "Discord Canary executable was not found" }
    Start-Process -FilePath $canary -ArgumentList "--remote-debugging-port=$DebugPort"
    Write-Host "Started Discord Canary with Chromium debugging on port $DebugPort"
}
