<#
.SYNOPSIS
    Runs blender-mcp from this clone and registers it with an MCP harness.

.DESCRIPTION
    blender-mcp has no --project flag (it talks to the Blender add-on, not a
    folder on disk), so -ProjectPath is only used to locate the repo root
    relative to this script; it is not passed to the server.

.PARAMETER ProjectPath
    Path to the game/Blender project this server will be used on. Only used
    for claude-code's project-scoped registration (writes .mcp.json there).
    Defaults to the current directory.

.PARAMETER Harness
    Which MCP client to register with: claude-code, claude-desktop, codex.

.EXAMPLE
    ./install.ps1 -ProjectPath C:\games\my-scene -Harness claude-code
#>
[CmdletBinding()]
param(
    [string]$ProjectPath = (Get-Location).Path,

    [Parameter(Mandatory)]
    [ValidateSet("claude-code", "claude-desktop", "codex")]
    [string]$Harness
)

$ErrorActionPreference = "Stop"

$ServerName = "blender"
$Command = "uv"
$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$McpArgs = @("run", "--directory", $RepoDir, "blender-mcp")

if (-not (Test-Path $ProjectPath)) {
    throw "ProjectPath '$ProjectPath' does not exist."
}
$ProjectPath = (Resolve-Path $ProjectPath).Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not on PATH. Install it from https://docs.astral.sh/uv/ first."
}

function Install-ClaudeCode {
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        throw "claude CLI not found on PATH."
    }
    Push-Location $ProjectPath
    try {
        & claude mcp add $ServerName -s project -- $Command @McpArgs
    } finally {
        Pop-Location
    }
    & claude mcp list
}

function Install-Codex {
    if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        throw "codex CLI not found on PATH."
    }
    & codex mcp add $ServerName -- $Command @McpArgs
}

function Install-ClaudeDesktop {
    $configPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
    $configDir = Split-Path $configPath -Parent
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    $config = if (Test-Path $configPath) {
        Get-Content $configPath -Raw | ConvertFrom-Json -AsHashtable
    } else {
        @{}
    }
    if (-not $config.ContainsKey("mcpServers")) {
        $config["mcpServers"] = @{}
    }

    $config["mcpServers"][$ServerName] = @{
        command = $Command
        args    = $McpArgs
    }

    ($config | ConvertTo-Json -Depth 10) | Set-Content -Path $configPath -Encoding utf8
    Write-Host "Wrote $ServerName to $configPath. Restart Claude Desktop to pick it up."
}

Write-Host "Installing blender-mcp (from $RepoDir) into $Harness ..."

switch ($Harness) {
    "claude-code"    { Install-ClaudeCode }
    "claude-desktop" { Install-ClaudeDesktop }
    "codex"          { Install-Codex }
}

Write-Host "Done. Remember blender-mcp also needs the add-on installed inside Blender itself (see README.md)."
