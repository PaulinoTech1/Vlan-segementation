# Beta is isolated here. Validate against a test tenant before each release.
# Assignment is intentionally a separate, visible operation in Intune.
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$DefinitionPath,
    [Parameter(Mandatory)][guid]$TrustedRootProfileId,
    [guid]$ProfileId = [guid]::Empty
)
. "$PSScriptRoot/Graph.Common.ps1"
$raw = Get-Content -Raw -LiteralPath $DefinitionPath
if ($raw -match 'REPLACE_|example\.invalid') { throw 'Customize the profile before publishing.' }
$body = $raw | ConvertFrom-Json -AsHashtable
$base = 'https://graph.microsoft.com/beta/deviceManagement/deviceConfigurations'
$root = Invoke-MgGraphRequest -Method GET -Uri "$base/$TrustedRootProfileId" -OutputType Hashtable
if ($root['@odata.type'] -ne '#microsoft.graph.windows81TrustedRootCertificate') {
    throw 'The referenced profile must be a Windows trusted root certificate.'
}
$body['rootCertificate@odata.bind'] = "$base/$TrustedRootProfileId"
if ($ProfileId -ne [guid]::Empty) {
    $current = Invoke-MgGraphRequest -Method GET -Uri "$base/$ProfileId" -OutputType Hashtable
    if ($current['@odata.type'] -ne $body['@odata.type']) { throw 'Profile type mismatch.' }
    if ($PSCmdlet.ShouldProcess($ProfileId, 'Update SCEP profile')) {
        Invoke-MgGraphRequest -Method PATCH -Uri "$base/$ProfileId" -Body ($body | ConvertTo-Json -Depth 12) -ContentType 'application/json'
    }
} else {
    $escaped = $body.displayName.Replace("'", "''")
    $filter = [uri]::EscapeDataString("displayName eq '$escaped'")
    $existing = @(Get-GraphCollection -Uri "$base`?`$filter=$filter")
    if ($existing.Count -gt 0) { throw 'Profile exists; pass its ProfileId to update explicitly.' }
    if ($PSCmdlet.ShouldProcess($body.displayName, 'Create unassigned SCEP profile')) {
        Invoke-MgGraphRequest -Method POST -Uri $base -Body ($body | ConvertTo-Json -Depth 12) -ContentType 'application/json'
    }
}
