# Telemetry Sources

This document lists the telemetry sources this architecture is designed to produce for an external SIEM. For each source it gives example events, the security value, and suggested transports. Transport choice is site-specific; not every platform supports every transport listed, and vendor-specific capabilities are labeled as such.

Layer reference: this document covers **layer 1 (telemetry source)** of the five-layer model in [README.md](../README.md). Normalization is covered in [event-normalization.md](event-normalization.md); transport examples live in [../syslog/README.md](../syslog/README.md).

All addresses and hostnames below are fictional examples. `10.50.0.0/24` is the AI/Automation trust zone, `10.99.0.0/24` is the management/infrastructure range, and `203.0.113.0/24` is TEST-NET-3 documentation space, intentionally non-production.

## Firewalls

| Item | Detail |
|------|--------|
| Example events | Allow events where operationally useful; deny events; rule changes; administrative logins; configuration changes; VPN authentication where applicable; inter-VLAN policy violations |
| Security value | Deny events are the primary signal of segmentation bypass attempts and unauthorized east-west traffic. Rule changes and admin logins detect unauthorized management-plane access and broad firewall rule creation. |
| Suggested transport | Syslog; syslog over TLS where supported |

## Layer 3 switches

| Item | Detail |
|------|--------|
| Example events | SVI ACL deny hits (for example VLAN50_IN denies); inter-VLAN routing decisions; HSRP/VRRP state changes; routing table changes |
| Security value | ACL deny hits on the AI trust zone SVI are the first network-layer evidence of an agent attempting unauthorized movement. HSRP state changes can indicate failover events or spoofing attempts. |
| Suggested transport | Syslog; syslog over TLS where supported |

## Managed switches

| Item | Detail |
|------|--------|
| Example events | Port state changes; VLAN changes; trunk changes; 802.1X state changes; port-security violations; administrative access; configuration modifications; authentication failures |
| Security value | Detects unexpected VLAN assignments, unauthorized trunk configuration changes, and port-security violations that precede lateral movement. |
| Suggested transport | Syslog; syslog over TLS where supported |

## 802.1X authentication

| Item | Detail |
|------|--------|
| Example events | Authentication success; authentication failure; EAP method used; session start/stop |
| Security value | Repeated failures indicate credential attacks or misconfigured supplicants. Success/failure patterns feed the "excessive 802.1X failures" detection concept. |
| Suggested transport | Syslog from the authenticator switch; RADIUS accounting records |

## RADIUS / NPS

| Item | Detail |
|------|--------|
| Example events | Authentication success; authentication failure; device identity; user identity where appropriate; authentication method; policy selected; VLAN assignment; rejected VLAN assignment |
| Security value | Correlating RADIUS authorization (assigned VLAN) with the expected identity role detects unauthorized VLAN assignment. Never log or expose RADIUS shared secrets. |
| Suggested transport | Syslog; Windows Event Forwarding where applicable (NPS runs on Windows Server, vendor-specific); structured JSON export where the platform supports it |

## Microsoft Entra ID

| Item | Detail |
|------|--------|
| Example events | Sign-in events; Conditional Access results; device compliance state; dynamic group membership changes; administrative role changes; service principal activity where relevant; device registration or removal; authentication anomalies |
| Security value | Detects identity-side privilege changes and anomalous authentication that network telemetry alone cannot see. Conditional Access results explain why a device was or was not granted access. |
| Suggested transport | Microsoft Graph API (vendor-specific); HTTPS API export to the SIEM collector. This repository does not implement a Graph ingestion pipeline; see the sanitized query examples referenced in the root identity documentation. |

## Microsoft Intune

| Item | Detail |
|------|--------|
| Example events | Device compliance state changes; device registration or removal; policy assignment changes |
| Security value | A device that drops out of compliance but keeps network access is a gap between identity policy and network enforcement. Correlate with RADIUS authorization events. |
| Suggested transport | Microsoft Graph API (vendor-specific); HTTPS API export |

## Ansible drift-management jobs

| Item | Detail |
|------|--------|
| Example events | Drift detected (expected vs observed state per host); enforce run started/completed; backup taken; change ticket recorded; remediation performed or not performed |
| Security value | A non-empty drift report after an enforce run means the enforced policy is not what the golden model describes. Drift in trunk configuration or ACL bindings is a security-relevant event, not just a compliance metric. |
| Suggested transport | File or stdout output from Ansible jobs (structured JSON written locally, for example per-host `drift.json`); forwarded to the SIEM collector by the site's existing log pipeline. External SIEM transmission from Ansible is disabled by default. See [../ansible/README.md](../ansible/README.md). |

## Administrative configuration changes

| Item | Detail |
|------|--------|
| Example events | Configuration commits on switches and firewalls; who made the change (actor identity where available); what changed; change ticket reference |
| Security value | Detects suspicious administrative configuration changes, such as a newly permissive rule toward the AI trust zone or an unexpected trunk addition. Every enforce run in this repo backs up the running configuration first and requires a change ticket. |
| Suggested transport | Syslog; structured JSON from automation tooling |

## DHCP

| Item | Detail |
|------|--------|
| Example events | Lease assignments; declined or conflicting addresses; rogue server detection events where the platform supports it |
| Security value | Useful for attributing an IP to a device at a point in time during investigation. Collect where useful; not every environment needs full DHCP telemetry in the SIEM. |
| Suggested transport | Syslog; syslog over TLS where supported |

## DNS

| Item | Detail |
|------|--------|
| Example events | Queries from the AI trust zone, especially to resolvers other than the approved one (example: `10.99.0.53`); high-volume or tunneling-like query patterns |
| Security value | DNS is the approved infrastructure exception for the AI zone. Queries to unapproved resolvers can precede exfiltration or command-and-control. |
| Suggested transport | Syslog from the resolver; structured JSON where the resolver supports it |

## AI / Automation Trust Zone traffic

| Item | Detail |
|------|--------|
| Example events | AI workload attempts access to the Management VLAN; attempts access to the User VLAN; attempts to unauthorized RFC1918 destinations; unapproved outbound connections; repeated ACL denials; unexpected DNS destinations; excessive outbound connection attempts; AI workload configuration changes |
| Security value | The trust zone is deny-by-default, so any deny here is a policy violation attempt by a privileged non-human workload. Repeated denials indicate a compromised or misconfigured agent probing its boundaries. |
| Suggested transport | Syslog; syslog over TLS; firewall JSON export where the firewall platform supports it (vendor-specific) |

## AI agent or MCP service audit events (when available)

| Item | Detail |
|------|--------|
| Example events | Agent tool invocations with arguments and timestamps; MCP server connection attempts; workload identity authentication failures; agent administrative access; the user who delegated the task |
| Security value | Connects a network connection to the agent's intent. Platform-dependent: only collect this where the agent platform actually produces an audit trail. This repository does not define or integrate an agent audit pipeline, so do not assume this log exists. |
| Suggested transport | Structured JSON via HTTPS API where the platform supports it (vendor-specific) |

## Authentication failures (cross-source)

| Item | Detail |
|------|--------|
| Example events | Failed 802.1X authentications; failed RADIUS authentications; failed device admin logins; failed Entra sign-ins |
| Security value | Repeated authentication failures across sources indicate brute-force or credential-stuffing activity. Correlate by identity and source address. |
| Suggested transport | Per source above (syslog, Windows Event Forwarding, Graph API) |

## ACL and firewall denies (cross-source)

| Item | Detail |
|------|--------|
| Example events | Deny ACE matches on switch SVI ACLs; firewall deny rule matches; inter-VLAN policy violation drops |
| Security value | The clearest network-layer evidence of segmentation bypass attempts, lateral movement attempts, and AI trust zone policy violations. |
| Suggested transport | Syslog; syslog over TLS where supported |

## Network-device administrative access

| Item | Detail |
|------|--------|
| Example events | SSH/console sessions on switches and firewalls; privilege escalations; failed admin login attempts |
| Security value | Detects unauthorized management-plane access. Correlate admin sessions with subsequent configuration changes. |
| Suggested transport | Syslog; syslog over TLS where supported |
