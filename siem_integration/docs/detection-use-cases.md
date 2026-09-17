# Detection Use Cases

**Integration examples only.** The use cases below show what kinds of detections the telemetry defined in [telemetry-sources.md](telemetry-sources.md) and normalized per [event-normalization.md](event-normalization.md) can support once ingested by an external SIEM. They are not a detection framework, not detection content, and not tuned rules. Thresholds, time windows, and approved-zone lists are site-specific and intentionally left as variables.

Detection engineering, tuning, dashboards, and SOC workflows are the responsibility of the organization operating the external SIEM, which is outside the scope of this repository.

## 1. AI workload accessing Management VLAN

- **Condition:** `source_zone = AI_AUTOMATION AND destination_zone = MANAGEMENT AND action = deny`
- **Priority:** High
- **Notes:** The AI trust zone (VLAN 50, `10.50.0.0/24`) is deny-by-default toward management. Any deny here is a policy violation attempt by a privileged non-human workload. Repeated hits from the same source IP suggest a compromised or misconfigured agent probing its boundaries. Correlate with workload identity and tool invocation where the agent platform provides an audit trail.

## 2. Guest network accessing corporate resources

- **Condition:** `source_zone = GUEST AND destination_zone = CORPORATE`
- **Priority:** Medium (raise to High on repeated or successful attempts if the firewall logs allows)
- **Notes:** Guest traffic should never reach corporate resources. Deny events confirm the control is working; allow events, if any are logged, indicate a policy failure. Correlate with the firewall rule or policy identifier that produced the decision.

## 3. Unauthorized VLAN assignment

- **Condition:** correlate three signals:
  - RADIUS authorization event (assigned VLAN)
  - Expected identity role (from Entra ID group or device compliance state)
  - The VLAN actually assigned to the session
- **Priority:** High
- **Notes:** A mismatch between the expected role and the assigned VLAN indicates a RADIUS/NPS policy error or an authorization bypass. Never log RADIUS shared secrets while building this correlation. This is a cross-source use case: it only works if RADIUS, Entra ID, and switch telemetry share a common time base and identity keys.

## 4. Configuration drift

- **Condition:** `expected_state != observed_state` on a drift event emitted by Ansible audit jobs
- **Priority:** High for trunk, ACL binding, or AI trust zone objects; Medium for other objects
- **Notes:** A non-empty drift report after an enforce run means the enforced policy is not what the golden model describes. Include the Ansible run ID as `correlation_id` so drift events across hosts from the same run can be grouped. Drift in AI trust zone ACL bindings deserves the same urgency as a firewall rule change.

## 5. Management access from unexpected network

- **Condition:** `destination_zone = MANAGEMENT AND source_zone NOT IN approved_admin_zones`
- **Priority:** High
- **Notes:** `approved_admin_zones` is a site-specific list (for example, the management VLAN and approved jump hosts). Administrative access to network devices from any other zone is unauthorized management-plane access. Correlate with authentication results: a successful admin login from an unexpected zone is more urgent than a failed one.

## 6. Excessive 802.1X failures

- **Condition:** repeated authentication failures from the same identity or the same switch port within a configurable time window
- **Priority:** Medium (raise on volume or on correlation with RADIUS rejects)
- **Notes:** The failure threshold and window are site-specific; this repository does not prescribe them. Distinguish credential attacks from misconfigured supplicants by correlating with device identity and with successful authentications from the same device. 802.1X failures alone do not prove compromise.

## 7. AI outbound anomaly

- **Condition:** AI automation workloads repeatedly attempting connections to destinations outside approved service categories
- **Priority:** High
- **Notes:** The AI trust zone has a controlled egress list (reference example: `203.0.113.10` and `203.0.113.11` on TCP 443, TEST-NET-3 documentation space). Repeated attempts to unapproved external destinations, unusual ports, or spikes in outbound volume can indicate unauthorized model or API access or data exfiltration. Correlate with DNS query logs: resolution through an unapproved resolver strengthens the signal.

## Explicit limitation

Simple network logs cannot detect prompt injection directly. Prompt injection happens inside the agent's context; the network layer sees only the resulting connections. What network telemetry can do is bound the blast radius: deny-by-default policy, allowlisted destinations, and the correlations above make the *consequences* of a successful injection visible (unexpected destinations, unusual volume, management-zone probes). Determining whether a prompt or tool invocation was malicious requires application-layer audit data from the agent platform, which is outside what this repository provides.
