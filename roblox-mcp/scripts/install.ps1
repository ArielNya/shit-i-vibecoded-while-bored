<#
.SYNOPSIS
    Runs roblox-mcp from this clone and registers it with an MCP harness,
    pointed at a specific Roblox/Rojo project.

.PARAMETER ProjectPath
    Path to the Roblox game project folder. Passed to the server as
    --project, and used as claude-code's registration scope.

.PARAMETER Harness
    Which MCP client to register with: claude-code, claude-desktop, codex.

.EXAMPLE
    ./install.ps1 -ProjectPath C:\games\my-game -Harness claude-code
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ProjectPath,

    [Parameter(Mandatory)]
    [ValidateSet("claude-code", "claude-desktop", "codex")]
    [string]$Harness
)

$ErrorActionPreference = "Stop"

$ServerName = "roblox"
$Command = "uv"
$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Test-Path $ProjectPath)) {
    throw "ProjectPath '$ProjectPath' does not exist."
}
$ProjectPath = (Resolve-Path $ProjectPath).Path

$McpArgs = @("run", "--directory", $RepoDir, "roblox-mcp", "--project", $ProjectPath)

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

Write-Host "Installing roblox-mcp (from $RepoDir) for project '$ProjectPath' into $Harness ..."

switch ($Harness) {
    "claude-code"    { Install-ClaudeCode }
    "claude-desktop" { Install-ClaudeDesktop }
    "codex"          { Install-Codex }
}

Write-Host "Done. The code tools (check_code/format_code/run_tests) need the toolchain:"
Write-Host "  uv run --directory `"$RepoDir`" python scripts/install_toolchain.py <bin-dir>   (or 'rokit install' in the project)"
