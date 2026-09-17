# Intune, Entra and RADIUS integration

## Trust boundary

Graph compliance does not directly change a switch VLAN. This implementation exports Intune state and Entra group membership, evaluates a verified certificate identity, and produces RADIUS reply attributes. A compatible NAC must invoke the evaluator **after EAP-TLS succeeds** and map JSON to its reply. No deployable NPS plug-in or vendor-specific NAC adapter is supplied.

Use a dedicated issuing CA/template that permits only authenticated Intune device enrollment. Enforce certificate chain, expiry, Client Authentication EKU, revocation and approved issuer/template on the NAC. Extract the device GUID only from the validated certificate subject; never accept a username, MAC address or client-provided GUID as proof. Subject `{{AAD_Device_ID}}` represents Entra `deviceId`, not the directory object `id` or Intune managed-device `id`.

The eligibility dynamic group uses ownership/platform/MDM attributes; compliance is independently read from Intune. Do not use a speculative `device.isCompliant` dynamic membership rule. Group evaluation and Intune reporting are eventually consistent.

## Permissions and authentication

Use separate least-privilege principals for setup and runtime. Install a reviewed version of `Microsoft.Graph.Authentication` on PowerShell 7 (`Install-Module Microsoft.Graph.Authentication -Scope CurrentUser`) and record/pin the accepted version in your execution image. Connect explicitly. Runtime app permissions: `DeviceManagementManagedDevices.Read.All`, `GroupMember.Read.All`, `Device.Read.All`. Group publishing requires `Group.ReadWrite.All`; profile publishing requires `DeviceManagementConfiguration.ReadWrite.All`. Grant admin consent, audit app credentials, and use managed identity where available or a certificate-backed app. Intune and applicable Entra dynamic-group licensing are prerequisites.

```powershell
# Managed identity on a supported Azure execution host:
Connect-MgGraph -Identity -NoWelcome
# Alternatively use a certificate from the local certificate store:
# Connect-MgGraph -TenantId $tenant -ClientId $client -CertificateThumbprint $thumbprint -NoWelcome

./intune_entra_id/scripts/Publish-DynamicGroup.ps1 -WhatIf
./intune_entra_id/scripts/Publish-DynamicGroup.ps1
```

Record the returned group ID. Re-running updates its membership rule by name; ambiguous names fail. Preserve the original rule before changing it. Provisioning is operator-invoked and is not run by the read-only export job.

## Certificate and wired policy deployment

1. Deploy AD CS + NDES + Intune Certificate Connector or a supported SCEP provider. Secure connector access and CRL/OCSP reachability. Do not expose an unrestricted enrollment endpoint.
2. Upload the public root/intermediate chain using Intune trusted-certificate profiles; never upload a private CA key. Deploy to the same pilot scope as the certificate and wired profiles.
3. Copy `policies/scep-device.json` outside tracked files, replace the SCEP URL, review the TPM requirement and certificate lifetime. This profile is for GUID-aware NAC device identity, not NPS AD computer mapping.
4. Publish the unassigned profile using the trusted-root profile ID:

```powershell
./intune_entra_id/scripts/Publish-ScepProfile.ps1 `
  -DefinitionPath ./artifacts/scep-device.json -TrustedRootProfileId $rootId -WhatIf
./intune_entra_id/scripts/Publish-ScepProfile.ps1 `
  -DefinitionPath ./artifacts/scep-device.json -TrustedRootProfileId $rootId
# Subsequent changes require -ProfileId $existingProfileId.
```

5. In Intune, assign root and SCEP to a pilot device group. Create a Windows wired network profile using EAP-TLS, machine authentication, this certificate, server certificate validation, the trusted server CA and explicit allowed RADIUS server names. Disable prompts to trust arbitrary servers. Deploy Wired AutoConfig (`dot3svc`) and test the actual Windows version.
6. Establish a restricted enrollment/remediation network before enforcing 802.1X. Do not scope certificate issuance only to compliant devices: that creates a recovery dependency. Already enrolled, known noncompliant devices use VLAN40; missing-certificate devices need a separate physical bootstrap process.

The SCEP publisher isolates the documented Graph beta resource and refuses placeholder URLs. Beta behavior requires pilot-tenant contract validation on upgrades. Profile assignments are deliberately separate so existing assignments are not overwritten.

## Runtime export and adapter

Create a directory writable only by the exporter and readable by NAC. On Linux use owner/group modes, on Windows a restricted NTFS ACL. Both the snapshot and evaluator executable are authorization inputs: an attacker who can edit either can grant access. Transfer across hosts only with authenticated transport and integrity protection; local atomic rename is not remote replication.

```powershell
./intune_entra_id/scripts/Export-ComplianceSnapshot.ps1 `
  -EligibleGroupId $groupId -OutputPath ./intune_entra_id/output/compliance.json
```

Schedule every five minutes using a managed identity or certificate principal. All Graph pages must complete before replacing the snapshot; failures retain the old file, which expires after 15 minutes. Alert on exporter failure and age. Test pagination, 429 handling, missing permissions and empty results in the pilot tenant. Do not extend freshness automatically during outages.

Adapter invocation after verified EAP-TLS (UUID below is illustrative):

```bash
python intune_entra_id/radius/evaluate.py \
  --snapshot intune_entra_id/output/compliance.json \
  --verified-device-id 12345678-1234-4234-8234-123456789abc
```

Invoke with an argument array, never interpolate attributes into a shell. Fail on nonzero exit, timeout, malformed output or unsupported attributes. Accept replies contain Tunnel-Type VLAN (13), Tunnel-Medium-Type IEEE-802 (6), Tunnel-Private-Group-ID string `10` or `40`, Session-Timeout 900 and Termination-Action RADIUS-Request (1). Keep tunnel tags consistent if the NAC emits tagged attributes. Every assigned VLAN must exist and cross the access trunk.

| Input | Result |
|---|---|
| Valid certificate + unique device + compliant + eligible + sync within 24 hours | Corporate VLAN10 |
| Known unique device, noncompliant/unknown/grace/error, out of group or stale sync | Quarantine VLAN40 |
| Invalid certificate, missing/duplicate identity, malformed or expired snapshot | Reject |

Validate RADIUS clients by management IP and unique strong secrets; enforce Message-Authenticator according to current platform support. The switch reauthenticates periodically; without a NAC-specific CoA/disconnect implementation, changes are not immediate. Worst-case convergence includes Intune reporting, group evaluation, five-minute export cadence and up to 15-minute reauth. Test Windows DHCP renewal on VLAN changes. Revoked certificates cannot use quarantine through EAP-TLS: they are rejected.

## NPS: supported separate path

Native Windows NPS authorizes using AD identities/groups, not Entra dynamic groups or the local JSON evaluator. The Entra MFA NPS extension does not provide Intune compliance-based VLAN decisions. Entra-only device GUID certificates do not create AD computer accounts.

For hybrid AD-backed clients, use a domain-joined NPS pair, an approved CA/template, strong certificate-to-AD identity mapping, and NPS Network Policies conditioned on AD groups. Configure EAP-TLS only (Microsoft Smart Card or other certificate), trusted CA/server certificates, and explicit NAS/client conditions. Corporate policy replies use Tunnel-Type VLAN, Tunnel-Medium-Type 802 and Tunnel-Pvt-Group-ID `10`; a restricted mapped group can reply `40`; deny unmatched requests. Place restricted rules before broad corporate rules.

This NPS path requires an explicitly engineered, audited AD group synchronization bridge if Graph compliance is to affect it; no automatic Entra-to-AD group writeback is assumed. For user certificates, follow Microsoft's SCEP strong-mapping guidance including the supported on-premises SID SAN variable. Device mappings require an actual AD computer and a validated strong-mapping issuance process. Do not weaken certificate binding enforcement or synthesize shadow AD accounts as a shortcut. For cloud-only device authentication, use a NAC that supports Entra device identities and the policy contract here.

References: [Entra join planning](https://learn.microsoft.com/en-us/entra/identity/devices/device-join-plan), [Intune SCEP](https://learn.microsoft.com/en-us/intune/intune-service/protect/certificates-profile-scep), [Graph SCEP schema](https://learn.microsoft.com/en-us/graph/api/resources/intune-deviceconfig-windows81scepcertificateprofile?view=graph-rest-beta), [dynamic membership rules](https://learn.microsoft.com/en-us/entra/identity/users/groups-dynamic-membership).
