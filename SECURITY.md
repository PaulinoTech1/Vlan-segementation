# Security reporting

Do not publish credentials, private keys, compliance snapshots or exploitable deployment details in an issue. Use GitHub private vulnerability reporting if enabled; otherwise contact the repository owner through an established private channel before disclosure.

The repository contains example addresses and explicit secret markers. Treat generated configs as review artifacts. Production operators own platform qualification, secret storage, certificate trust, NAC adapter integrity, monitoring and recovery. See `docs/deployment.md` for drift ownership and `docs/identity-integration.md` for authentication boundaries.

## Security Monitoring and SIEM Integration

VLAN segmentation and ACL enforcement in this repository are preventative controls: they block traffic the policy forbids. Prevention alone does not detect an adversary probing the boundary. Monitoring is required to detect:

* Segmentation bypass attempts
* Unexpected east-west traffic
* Repeated authentication failures
* Unauthorized management-plane access
* Configuration drift
* Privilege changes
* Unexpected VLAN assignments
* Changes to trunk configuration
* Broad firewall rule creation
* AI / Automation Trust Zone policy violations
* Unauthorized outbound connections
* Failed access attempts from isolated networks
* Suspicious administrative configuration changes

The architecture therefore exports security telemetry to an external SIEM, as described in [SIEM Integration and Security Telemetry](README.md#siem-integration-and-security-telemetry) and the [siem_integration/](siem_integration/) directory. The repository defines the telemetry sources, normalization schemas, and integration points. Correlation, detection, investigation, alerting, dashboards, threat hunting, case management, and SOC workflows belong to the external SIEM and are outside the scope of this repository.

## Logging Security Requirements

Telemetry must not become a new exposure surface. The following requirements apply to every log source, exporter, and example in this repository:

* Logs must not contain plaintext passwords.
* API keys and authentication tokens must not be logged.
* RADIUS shared secrets must never be logged.
* Private keys and certificates must not be logged.
* Sensitive authentication material must be redacted before export.
* Logs should use UTC timestamps where practical.
* Devices should use authenticated time synchronization (authenticated NTP or equivalent) so event ordering is trustworthy.
* Administrative configuration changes should include actor identity when available.
* Network events should preserve source IP, destination IP, protocol, port, action, and policy identifier where supported.
* Log transport should be encrypted where supported (for example, syslog over TLS with certificate validation).
* Logs should be protected against unauthorized modification (forwarded off-host, append-only storage, restricted access).

## Repository Scope

**This repository defines SIEM integration points and example telemetry formats. It does not deploy or operate a SIEM platform. Detection engineering, dashboards, threat hunting, case management, and SOC workflows are outside the primary scope of this repository.**

Conceptual-only integrations are labeled as such: workload identity telemetry, AI agent and MCP audit events, and any SIEM-side correlation are reference architecture, not implemented functionality. Example exporters fail closed when required configuration is missing, transmit nothing by default, and never embed credentials.
