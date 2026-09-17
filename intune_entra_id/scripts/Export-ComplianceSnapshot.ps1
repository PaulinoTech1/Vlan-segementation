# App permissions: DeviceManagementManagedDevices.Read.All, GroupMember.Read.All,
# Device.Read.All. Use a certificate-backed app or managed identity, with consent.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][guid]$EligibleGroupId,
    [Parameter(Mandatory)][string]$OutputPath
)
. "$PSScriptRoot/Graph.Common.ps1"
if (-not (Get-MgContext)) { throw 'Connect-MgGraph before exporting.' }
$started = [DateTimeOffset]::UtcNow
$devices = @(Get-GraphCollection -Uri 'https://graph.microsoft.com/v1.0/deviceManagement/managedDevices?$select=id,azureADDeviceId,complianceState,lastSyncDateTime')
# Entra object id is NOT the Entra deviceId and NOT the Intune managedDevice id.
$members = @(Get-GraphCollection -Uri "https://graph.microsoft.com/v1.0/groups/$EligibleGroupId/members/microsoft.graph.device?`$select=id,deviceId")
$snapshot = [ordered]@{
    schemaVersion = 1
    generatedAt = $started.ToString('o')
    eligibleGroupId = $EligibleGroupId.ToString()
    eligibleDeviceIds = @($members | ForEach-Object { $_['deviceId'] })
    devices = @($devices | ForEach-Object {
        [ordered]@{
            deviceId = $_['azureADDeviceId']
            complianceState = $_['complianceState']
            lastSyncDateTime = $_['lastSyncDateTime']
        }
    })
}
if (([DateTimeOffset]::UtcNow - $started).TotalMinutes -gt 5) {
    throw 'Collection exceeded snapshot age budget; prior snapshot left intact.'
}
$target = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $target
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw 'Create a restricted output directory before exporting.'
}
$temporary = Join-Path $parent ([IO.Path]::GetRandomFileName())
try {
    [IO.File]::WriteAllText($temporary, ($snapshot | ConvertTo-Json -Depth 8))
    # Same-filesystem atomic replacement; readers see a complete old or new file.
    [IO.File]::Move($temporary, $target, $true)
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Output 'Complete compliance snapshot exported.'
