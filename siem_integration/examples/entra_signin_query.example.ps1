# Example: query Microsoft Entra sign-in logs via Microsoft Graph and convert
# records to the auth_event baseline JSON shape.
#
# Conceptual example only. No tenant-specific values are embedded and no
# secrets are read from disk. All configuration comes from environment
# variables. Replace the stubbed query with your site's approved Graph
# client; do not hard-code tokens or endpoints.

$ErrorActionPreference = "Stop"

$tenantId = $env:SIEM_TENANT_ID
$clientId = $env:SIEM_CLIENT_ID
$outFile  = $env:SIEM_EVENT_OUT

if ([string]::IsNullOrEmpty($tenantId) -or [string]::IsNullOrEmpty($clientId)) {
    Write-Error "Set SIEM_TENANT_ID and SIEM_CLIENT_ID environment variables before running."
    exit 1
}

# Placeholder records standing in for Graph auditLogs/signIns results.
# A real implementation pages this endpoint and maps each record below.
$signIns = @(
    [pscustomobject]@{
        createdDateTime         = "2026-01-01T12:10:00Z"
        userPrincipalName       = "user@example.com"
        ipAddress               = "203.0.113.50"
        status                  = "failure"
        conditionalAccessStatus = "failure"
        authenticationMethod    = "password"
    }
)

$events = foreach ($s in $signIns) {
    $result = "failure"
    if ($s.status -eq "success") { $result = "success" }

    [ordered]@{
        timestamp             = $s.createdDateTime
        event_type            = "authentication"
        severity              = "medium"
        source                = @{
            device = "entra-id"
            ip     = $s.ipAddress
            zone   = "EXTERNAL"
        }
        user_identity         = $s.userPrincipalName
        authentication_result = $result
        authentication_method = $s.authenticationMethod
        policy_selected       = $s.conditionalAccessStatus
        radius_result         = "not-applicable"
        message               = "Entra ID sign-in record converted to auth_event baseline"
    }
}

$json = $events | ConvertTo-Json -Depth 4

if ([string]::IsNullOrEmpty($outFile)) {
    Write-Output $json
} else {
    Set-Content -Path $outFile -Value $json -Encoding utf8
}
