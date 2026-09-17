[CmdletBinding(SupportsShouldProcess)]
param([string]$DefinitionPath = "$PSScriptRoot/../policies/corporate-windows-group.json")
. "$PSScriptRoot/Graph.Common.ps1"
$definition = Get-Content -Raw -LiteralPath $DefinitionPath | ConvertFrom-Json -AsHashtable
$escaped = $definition.displayName.Replace("'", "''")
$filter = [uri]::EscapeDataString("displayName eq '$escaped'")
$existing = @(Get-GraphCollection -Uri "https://graph.microsoft.com/v1.0/groups?`$filter=$filter")
if ($existing.Count -gt 1) { throw 'Ambiguous group display name; resolve duplicates first.' }
if ($existing.Count -eq 1) {
    if ('DynamicMembership' -notin $existing[0].groupTypes) { throw 'Existing group is not dynamic.' }
    $body = @{ membershipRule = $definition.membershipRule; membershipRuleProcessingState = 'On' }
    if ($PSCmdlet.ShouldProcess($existing[0].id, 'Update dynamic membership rule')) {
        Invoke-MgGraphRequest -Method PATCH -Uri "https://graph.microsoft.com/v1.0/groups/$($existing[0].id)" -Body ($body | ConvertTo-Json) -ContentType 'application/json'
    }
    Write-Output $existing[0].id
} elseif ($PSCmdlet.ShouldProcess($definition.displayName, 'Create dynamic device group')) {
    $created = Invoke-MgGraphRequest -Method POST -Uri 'https://graph.microsoft.com/v1.0/groups' -Body ($definition | ConvertTo-Json -Depth 8) -ContentType 'application/json' -OutputType Hashtable
    Write-Output $created.id
}
