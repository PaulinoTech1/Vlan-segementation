# Requires PowerShell 7 and Microsoft.Graph.Authentication. Connect separately;
# no credentials or access tokens are serialized by these helpers.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-GraphCollection {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Uri)
    $items = [System.Collections.Generic.List[object]]::new()
    $visited = [System.Collections.Generic.HashSet[string]]::new()
    while ($Uri) {
        $parsed = [uri]$Uri
        if ($parsed.Scheme -ne 'https' -or $parsed.Host -ne 'graph.microsoft.com') {
            throw 'Unexpected Graph pagination origin.'
        }
        if (-not $visited.Add($Uri)) { throw 'Graph pagination cycle.' }
        $response = $null
        for ($attempt = 0; $attempt -lt 5; $attempt++) {
            try {
                $response = Invoke-MgGraphRequest -Method GET -Uri $Uri -OutputType Hashtable
                break
            } catch {
                $status = 0
                if ($_.Exception.PSObject.Properties['ResponseStatusCode']) {
                    $status = [int]$_.Exception.ResponseStatusCode
                }
                if ($status -notin @(429, 500, 502, 503, 504) -or $attempt -eq 4) { throw }
                # SDK also honors Retry-After; this bounds retries outside the SDK.
                Start-Sleep -Seconds ([math]::Min(30, [math]::Pow(2, $attempt + 1)))
            }
        }
        if (-not $response.ContainsKey('value')) { throw 'Incomplete Graph collection response.' }
        foreach ($item in $response['value']) { $items.Add($item) }
        $Uri = $response['@odata.nextLink']
    }
    return $items.ToArray()
}
