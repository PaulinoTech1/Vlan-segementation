# Event Normalization

This document defines the common structured event baseline used at **layer 3 (normalization)** of the five-layer model in [README.md](../README.md). Normalization happens before events cross the SIEM ingestion boundary; the external SIEM is responsible for parsing, correlation, and detection on the other side.

The goal is a consistent core that every event carries, plus source-specific extensions where forcing a single shape would lose important information. Do not flatten away source-specific detail just to fit the baseline.

## Common baseline fields

| Field | Type | Guidance |
|-------|------|----------|
| `timestamp` | string, RFC3339 UTC | Required. Use UTC where practical; devices should use authenticated time synchronization (NTP/NTS). |
| `event_type` | string | Required. A stable category such as `network_policy_violation`, `authentication`, `configuration_drift`, `admin_config_change`. |
| `severity` | string | Required. One of `info`, `low`, `medium`, `high`, `critical`, assigned by the source according to site policy. |
| `source` | object | Required. `device` (hostname, fictional `.example` names only), `ip`, and `network_zone` or `zone` where known. |
| `destination` | object | Required for network events. `ip`, `port`/`destination_port`, `network_zone` where known. Omit for non-network events such as drift. |
| `user_identity` | string | Optional. Human identity where the event involves one (for example RADIUS user, Entra sign-in). |
| `device_identity` | string | Optional. Managed device identity (for example Intune device ID or certificate subject). |
| `workload_identity` | string | Optional. Non-human workload identity (for example service principal or managed identity) for AI/automation events. Reference architecture; only populate where the platform provides it. |
| `vlan` | integer or string | Optional. VLAN ID where the event is VLAN-scoped. |
| `network_zone` | string | Optional at top level when not already in source/destination (for example `AI_AUTOMATION`, `MANAGEMENT`, `GUEST`, `CORPORATE`). |
| `protocol` | string | Optional. `tcp`, `udp`, `icmp`, etc., for network events. |
| `destination_port` | integer | Optional. Destination port for network events. |
| `action` | string | Required for policy events. `allow` or `deny` (firewall/ACL decisions). |
| `policy_id` | string | Optional but recommended for policy events. The rule or policy identifier that produced the decision, for example `AI_TO_MGMT_DENY`. |
| `authentication_result` | string | Optional. `success` or `failure`, plus method where known, for authentication events. |
| `configuration_object` | string | Optional. What was changed or drifted, for example `vlan_trunk`, `acl_binding`. |
| `previous_state` | string | Optional. State before a change, where known. |
| `expected_state` | string | Required for drift events. The golden-model state. |
| `observed_state` | string | Required for drift events. The state actually found on the device. |
| `correlation_id` | string | Optional. A value that ties related events together (for example an Ansible run ID linking drift events across hosts, or a RADIUS session ID linking authentication to authorization). |
| `message` | string | Required. A short human-readable description. Must not contain secrets (see redaction rules). |

## Required vs optional

- **Always required:** `timestamp`, `event_type`, `severity`, `message`.
- **Required by event class:** `source` for all events; `destination`, `protocol`, `action` for network policy events; `expected_state` and `observed_state` for drift events.
- **Optional:** identity fields, `vlan`, `network_zone`, ports, `policy_id`, `authentication_result`, `configuration_object`, `previous_state`, `correlation_id`. Populate them when the source provides the data; never invent values to fill them.

## Source-specific extensions

Keep source-specific information in a nested object named after the source rather than dropping it. Examples:

- Firewall events may add `firewall: { "rule_name": ..., "bytes_in": ..., "bytes_out": ... }`.
- RADIUS events may add `radius: { "auth_method": ..., "policy_selected": ..., "assigned_vlan": ... }`.
- Ansible drift events may add `ansible: { "run_id": ..., "remediation": "not_performed" }`.

The common baseline stays flat and queryable; the extension object preserves fidelity for investigation.

## Example

```json
{
  "timestamp": "2026-01-01T12:00:00Z",
  "event_type": "network_policy_violation",
  "severity": "high",
  "source": {
    "device": "firewall.example",
    "ip": "10.50.0.25",
    "zone": "AI_AUTOMATION"
  },
  "destination": {
    "ip": "10.99.0.10",
    "zone": "MANAGEMENT",
    "port": 443
  },
  "protocol": "tcp",
  "action": "deny",
  "policy_id": "AI_TO_MGMT_DENY",
  "message": "AI automation workload attempted access to management network"
}
```

## UTC and time rules

- Emit `timestamp` in RFC3339 UTC (for example `2026-01-01T12:00:00Z`) wherever the source supports it.
- Devices should synchronize time via authenticated NTP or NTS so that correlation across sources is meaningful.
- If a source cannot emit UTC, record its local offset explicitly rather than silently converting.

## Redaction rules

These apply to every event at normalization time, before transport:

- Logs must not contain plaintext passwords.
- API keys and authentication tokens must not be logged.
- RADIUS shared secrets must never be logged.
- Private keys and certificates must not be logged.
- Sensitive authentication material must be redacted or replaced with a placeholder such as `[REDACTED]`.
- Network events should preserve source IP, destination IP, protocol, port, action, and policy identifier where supported; these are telemetry, not secrets, but avoid including full packet payloads.
- Administrative configuration changes should include actor identity when available, but never include credential material from the change itself.
- When in doubt, drop the field. A missing optional field is always safer than a leaked secret.
