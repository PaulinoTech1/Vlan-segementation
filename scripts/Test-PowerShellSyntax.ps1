[CmdletBinding()]
param([string]$Root = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$failed = $false
$files = @(Get-ChildItem -LiteralPath "$Root/intune_entra_id/scripts" -Filter '*.ps1')
$files += @(Get-ChildItem -LiteralPath "$Root/scripts" -Filter '*.ps1')
foreach ($file in $files) {
    $tokens = $null
    $parseErrors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count -gt 0) {
        $failed = $true
        $parseErrors | ForEach-Object { Write-Output "$($file.Name): $($_.Message)" }
    }
}
if ($failed) { throw 'PowerShell syntax validation failed.' }
Write-Output "Parsed $($files.Count) PowerShell scripts."
