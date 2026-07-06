param(
  [Parameter(Mandatory = $true)]
  [string]$Version,

  [Parameter(Mandatory = $true)]
  [string]$MsiUrl,

  [string]$SignaturePath = "desktop/gui/src-tauri/target/release/bundle/msi/WeUnix_$($Version)_x64_zh-CN.msi.sig",
  [string]$OutputPath = "desktop/gui/src-tauri/target/release/bundle/msi/latest.json",
  [string]$Notes = "WeUnix desktop update."
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$sigFile = Join-Path $root $SignaturePath
$outFile = Join-Path $root $OutputPath

if (-not (Test-Path -LiteralPath $sigFile)) {
  throw "Signature file not found: $sigFile"
}

$signature = (Get-Content -Raw -LiteralPath $sigFile).Trim()
$payload = [ordered]@{
  version = $Version
  notes = $Notes
  pub_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  platforms = [ordered]@{
    "windows-x86_64" = [ordered]@{
      signature = $signature
      url = $MsiUrl
    }
  }
}

$json = $payload | ConvertTo-Json -Depth 8
$dir = Split-Path -Parent $outFile
New-Item -ItemType Directory -Force -Path $dir | Out-Null
[System.IO.File]::WriteAllText($outFile, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Host "latest.json written to $outFile"
