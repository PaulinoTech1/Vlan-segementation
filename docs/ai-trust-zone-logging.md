# AI / Automation Trust Zone logging reference

The AI / Automation trust zone (VLAN 50, `AI_AUTOMATION`, `10.50.0.0/24`) contains privileged non-human workloads: AI agent runtimes, MCP servers, local inference servers, automation workers, API orchestration services and RAG/query services. Logging in this zone exists to detect policy violations, configuration drift, and misuse of those autonomous workloads.

The goal of logging here is not just connectivity troubleshooting. A compromised or misbehaving agent looks, at the network layer, like authorized traffic from a trusted host. You need evidence that answers: which workload acted, what tool it invoked, what it reached, and whether the network policy it operated under was the intended one.

**Explicit non-goal.** This repository ships no SIEM integration, no log forwarding configuration, no parsing rules, and no agent platform audit integration. Where to send logs, how to parse them, and how to alert are site-specific operational decisions outside this repository. Anything in this document that describes a monitoring destination or correlation platform is reference architecture, not something the repo implements.

## Recommended logging sources

| Source | What to collect | Why it matters for the AI zone |
|---|---|---|
| Firewall allow/deny events for the AI zone | 5-tuple, action (allow/deny), byte counts, rule or policy name that matched | The firewall is the Layer-3/Layer-4 enforcement point between the AI zone and other networks. Deny hits here are the first signal of an agent attempting unauthorized east-west movement or unapproved egress. |
| Switch ACL deny hits for VLAN50_IN | Deny ACE matches on the AI SVI ingress ACL | VLAN50_IN is deny-by-default and stateless. Consider evaluating `log` on deny ACEs so that dropped attempts toward user, management, IoT and guest destinations produce evidence. Note: the rendered ACLs in this repository intentionally include no `log` keywords; enabling ACL logging is an operational decision to evaluate, because deny logging on a busy SVI can produce high log volume and affect device CPU. |
| Authentication events | Successful and failed logins on AI hosts and on the switches that carry the AI VLAN | Detects credential theft or brute-force attempts against agent runtimes, automation accounts, and infrastructure. Correlate unexpected source addresses with the other signals below. |
| RADIUS/NAC events | Access-Accept, Access-Reject, and authorization changes | Human endpoints authenticate via Intune/Entra device certificates and RADIUS/NAC evaluation; AI workloads do not. These events show the human-side authentication boundary and help separate user activity from workload activity. |
| Configuration change events | Switch config diffs, timestamps, and who made them; Ansible enforce run results; out-of-band manual changes | An unauthorized or accidental change (for example an accidental permissive AI-to-management rule) silently changes what the logs mean. Every enforcement run backs up the running config first and requires a `change_ticket`; preserve those artifacts with the change history. |
| Ansible drift findings | Per-host `drift.json` under `artifacts/ansible/` | The audit-only playbook writes a secret-free `drift.json` per host and succeeds even when drift is found. A non-empty drift report after an enforce run means the AI trust zone policy is not what the golden model describes; treat it as a security-relevant event, not just a compliance metric. |
| Administrative access | SSH/console sessions to AI hosts and to switches in the AI zone path; privilege escalations | Privileged autonomous workloads make admin access a high-value target. Short or unusual admin sessions around the time of a policy change or an anomalous connection deserve scrutiny. |
| Unusual outbound destinations from 10.50.0.0/24 | Connections to destinations outside the approved egress list (reference example: `203.0.113.10` and `203.0.113.11` on TCP 443) | Controlled HTTPS egress is the expected pattern. A new external destination, an unusual port, or a spike in outbound bytes can indicate unauthorized model or API access, or data exfiltration. |
| Failed internal access attempts from the AI zone | Denied connections from 10.50.0.0/24 toward user VLANs, management VLANs, domain controller administrative services, or arbitrary RFC1918 destinations | Would-be lateral movement. Under the deny-by-default policy these attempts should never succeed; their frequency and targets tell you what the compromised or misconfigured workload was reaching for. |
| DNS query logs for AI hosts | Queries from 10.50.0.0/24, especially to any resolver other than the approved one (reference example: `10.99.0.53`) | DNS is the approved infrastructure exception for the zone. Queries to unapproved resolvers or DNS tunneling patterns can precede or accompany exfiltration and command-and-control. |
| Agent/tool execution audit events | Which tool the agent invoked, with what arguments, at what time | Platform-dependent: only collect this where the agent platform (MCP server, orchestration layer, inference gateway) actually produces an audit trail. This repository does not define or integrate an agent audit pipeline, so do not assume this log exists. |

## Correlating the five signals

No single source tells the whole story. The value comes from joining five signals:

1. **Network Identity.** Which VLAN and IP the traffic came from, for example `10.50.0.0/24`. This tells you the packet originated inside the AI trust zone and which device it is.
2. **Workload Identity.** Which service principal, managed identity, or automation account the agent runs as. This tells you which non-human identity is responsible. Note that this is reference architecture: the repo's identity model covers human devices via Intune/Entra certificates and RADIUS/NAC evaluation, not workload identity for AI agents.
3. **Network Flow.** The 5-tuple (source, destination, protocol, ports), byte counts, and the allow/deny decision from the firewall and switch ACLs.
4. **Tool Invocation.** Which tool the agent called, with what arguments, taken from the agent platform audit log where one exists. This connects a network connection to the agent's intent, for example a tool that fetches an arbitrary URL.
5. **Configuration Change.** Ansible drift and enforce events plus switch config diffs. This tells you whether the observed traffic was evaluated against the intended policy or against a drifted one.

### Walkthrough: anomalous outbound connection from an AI host

Suppose the firewall logs a denied outbound HTTPS connection from `10.50.0.100` to an external address outside the approved egress list (`203.0.113.10/11` on TCP 443):

1. **Network Flow (start here).** The firewall deny gives you the 5-tuple, timestamp, byte count, and the rule that dropped it. The source is inside the AI trust zone, so this is a policy violation attempt, not a connectivity failure.
2. **DNS.** Check DNS query logs for `10.50.0.100` around that timestamp. If the host resolved the destination through an unapproved resolver instead of `10.99.0.53`, or if the query pattern looks like tunneling, you have a second indicator that the workload is avoiding the approved infrastructure.
3. **Workload Identity.** Identify which service principal, managed identity, or automation account runs the agent on `10.50.0.100`. This scopes the blast radius: which credentials and tools that identity can reach.
4. **Tool Invocation.** In the agent platform audit log (where available), find what tool the agent invoked just before the connection. A web-fetch or shell-execution tool called with the external URL points to prompt injection or excessive agency; a routine scheduled task with the same behavior points to a misconfigured allowlist.
5. **Configuration Change.** Check the latest `drift.json` for the switches in the AI zone path and the most recent enforce run result. If drift.json is non-empty, or an out-of-band change added an egress exception, the deny may be masking a larger policy gap. Confirm the VLAN50_IN ACL on the SVI matches the golden model before declaring the incident contained.

Each pivot narrows the hypothesis: flow tells you what happened, DNS and workload identity tell you how it was attempted, tool invocation tells you why, and configuration change history tells you whether the guardrails were intact when it happened.

## What this repository does and does not provide

**Does provide:**

- Deterministic deny-by-default policy for the AI zone (`VLAN50_IN`), rendered from a single intent model by `scripts/render.py`. Every ACE names an explicit destination and port; there is no broad permit.
- Offline validation of that policy: rendered configs, authorization and traffic-boundary tests, Ansible syntax checks, and acceptance criteria in `docs/validation.md`.
- Drift reporting: `playbooks/audit_only.yml` implements AUDIT, DETECT DRIFT, REPORT and writes a secret-free `drift.json` per host under `artifacts/ansible/`. It succeeds even when drift is found.
- Backup-before-enforce: `playbooks/enforce.yml` backs up the running config first, changes one switch at a time, verifies convergence, and requires a `change_ticket`.
- The drift-recovery acceptance test in `docs/validation.md`: change an owned VLAN name, add a trunk VLAN, add an unauthorized ACL permit; audit reports, enforce restores.

**Does not provide:**

- Log forwarding configuration (no syslog destinations, no collector setup).
- SIEM parsing rules, dashboards, or alert definitions.
- Agent platform audit integration (no tool-execution log pipeline).
- Workload identity provisioning (service principals, managed identities, automation accounts appear in the identity model as reference architecture, not as implemented configuration).
- Automatic remediation decisions: not every detected deviation should be auto-remediated, and the README explains the operational risk of running enforcement against a stale desired state or an intentionally applied emergency change.

Anything beyond these lists is reference architecture. Do not fabricate an integration the repository does not implement.

## Operational notes

- **Protect log integrity.** Forward logs off the hosts that generate them as close to real time as the site design allows. Restrict who can modify, delete, or rotate log storage. A log an attacker can rewrite is not evidence.
- **Alert on the highest-value signals first.** Start with: deny hits from the AI zone toward management or user VLANs; any new outbound destination from `10.50.0.0/24` outside the approved egress list; a non-empty `drift.json` after an enforce run; and administrative logins to AI hosts or their switches outside approved change windows. Tune from there based on observed baseline traffic.
- **Retain per site policy.** Retention is driven by the site's compliance obligations and investigation needs, not by this repository. Whatever the site chooses, keep firewall denies, config change history, drift reports, and (where they exist) tool invocation logs for the same window, so the five-signal correlation above is possible after the fact.
