# AI Agent Threat Model

## Scope and architectural stance

AI agent runtimes, MCP servers, local inference servers, automation workers, API orchestration services, RAG/query services, and administrative automation workers are treated as **privileged non-human workloads with their own trust boundary**, the AI/Automation trust zone: VLAN 50, name `AI_AUTOMATION`, subnet `10.50.0.0/24` (gateway `10.50.0.1` as the HSRP VIP in topology 3; core1 `.2`, core2 `.3`). They are not "another user device class" and they do not inherit user-network trust.

A VLAN alone is not sufficient protection for these workloads. The zone combines network segmentation, a deny-by-default least-privilege ingress policy, workload identity (service principals, managed identities, automation accounts; reference architecture, not implemented by this repository), controlled outbound access, explicit internal destination allowlisting, credential isolation, configuration drift monitoring, and logging and auditing. The SVI ingress ACLs are stateless and are explicitly not a firewall replacement (see the architectural decisions table in the root README).

**Topology 1 intentionally demonstrates the risk of AI workloads operating inside a flat trust domain**: AI agent and automation workloads share the single VLAN 10 broadcast domain with corporate endpoints, guest devices, and IoT, so every threat below lands at full severity there. Topologies 2 and 3 add the AI/Automation trust zone as the mitigation reference.

Identity is split into two paths. The implemented human path is: Intune/Entra device certificate, 802.1X/EAP-TLS, RADIUS/NAC evaluator, then VLAN assignment (VLAN 10/40). The AI workload path (workload identity to authorization policy to trust zone) is reference architecture: it is documented as the design, not claimed as an existing integration.

### Baseline deny-by-default policy (VLAN50_IN)

ACE order rendered by `scripts/render.py` (function `ai_acl`) from the `ai_trust_zone` policy inputs in `topologies/02-segmented/intent.json`:

1. DHCP bootstrap (udp bootpc to bootps)
2. HSRP (udp `10.50.0.0/24` to `224.0.0.102` eq 1985)
3. DNS udp and tcp to the approved resolver `10.99.0.53` only
4. NTP udp to the approved source `10.99.0.123` only
5. Management return path only: `permit tcp 10.50.0.0/24 to 10.99.0.0/24 established` (return traffic of management-initiated admin sessions; AI-initiated connections to management still deny)
6. Approved internal inference/API server: tcp to `10.10.0.25` eq 443
7. Controlled egress: tcp to `203.0.113.10` eq 443 and `203.0.113.11` eq 443 (documentation addresses)
8. Deny `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
9. Deny ip any any

There is intentionally no broad `permit ip` rule. Corporate users reach the zone only through one narrow exception in VLAN10_IN, `permit tcp 10.10.0.0/24 to 10.50.0.10 eq 443` (the AI application gateway presented to users), placed before the RFC1918 denies.

## 1. Prompt Injection

A malicious external input manipulates an agent into invoking its authorized tools improperly, for example steering a fetch or API call toward an attacker-chosen target.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Prompt injection steering tool execution | Egress is limited to two named external hosts on 443 (`203.0.113.10`, `203.0.113.11`) and one internal service (`10.10.0.25` tcp 443); attacker-chosen destinations fall through to deny ip any any | SVI ingress ACL `VLAN50_IN` on the core SVIs (stateless; not a firewall replacement) | `tests/test_network.py::test_ai_controlled_egress`, `test_ai_deny_by_default`; playbook check "Reject unauthorized broad permit ACEs in VLAN50_IN"; lab: curl from a `10.50.0.x` host to an unlisted host, expect deny |
| Prompt injection steering tool execution | Tool-capability allowlists and input validation are application controls outside this repository; the network policy bounds the blast radius, it does not evaluate intent | (reference architecture at the application layer) | Lab negative test confirmed with `show access-lists` deny counters |

## 2. Excessive Agency

An agent holds network access to more systems or operations than its function requires.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Excessive agency | Every ACE names an explicit destination and port; no broad permit rule exists in `VLAN50_IN` | `VLAN50_IN` rendered from `ai_trust_zone` in `intent.json` by `scripts/render.py` | `tests/test_network.py::test_ai_no_broad_permit_in_model`; playbook check "Reject unauthorized broad permit ACEs in VLAN50_IN" |
| Excessive agency | AI-initiated administration of the management network is denied; only return traffic of management-initiated sessions is permitted (`established`) | `VLAN50_IN` ingress ACE toward `10.99.0.0/24` | `tests/test_network.py::test_ai_management_admin_return_only`; playbook check "Reject permissive AI-to-management rules (established return only)" |
| Excessive agency | Policy changes that widen agency (added permits) are detected as drift and reported before any remediation | Golden models in `ansible/golden/*.yml` reconciled by `roles/vlan_enforce`; `playbooks/audit_only.yml` audits, detects, and reports without writing; `playbooks/enforce.yml` remediates only with a `change_ticket` | `docs/validation.md` "Drift recovery": add an unauthorized ACL permit, audit reports it, enforce restores the golden state |

## 3. Credential Exposure

API keys, tokens, certificates, or service credentials accessible to the agent are stolen from configuration, environment, logs, or agent-accessible stores.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Credential exposure | Network automation credentials are stored in an Ansible Vault encrypted file, never in generated configs; generated `.cfg` files carry deliberate secret placeholders | `ansible/playbooks/enforce.yml` consuming `vault_network_password` / `vault_enable_password` (see README deployment section) | Manual review: output of `python scripts/render.py --check` contains no credential values |
| Credential exposure | Workload identity for AI agents (service principals, managed identities, automation accounts, short-lived tokens) is reference architecture: it reduces reliance on long-lived secrets that the network cannot protect | (reference architecture; not implemented by this repository) | Design review only; do not claim an existing integration |
| Credential exposure | If credentials do leak, the egress allowlist limits where a compromised agent can phone home or reuse them | `VLAN50_IN` egress ACEs | `test_ai_controlled_egress`; playbook check "Verify VLAN50_IN ends with an explicit deny-all" |

## 4. Lateral Movement

A compromised agent attempts to pivot into corporate, management, IoT, server, or user networks.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Lateral movement | RFC1918 deny ACEs (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) plus terminal deny ip any any; AI-initiated management access denied (established return only) | `VLAN50_IN` ingress on core SVIs | `tests/test_network.py::test_ai_deny_by_default`, `test_ai_management_admin_return_only`; `show access-lists` on the core |
| Lateral movement | Users and guests can reach only the AI application gateway (`10.50.0.10` tcp 443), never AI hosts or AI infrastructure directly | `VLAN10_IN` narrow exception before its RFC1918 denies; Guest, IoT, and Management VLANs have no permit toward `10.50.0.0/24` | `test_user_to_ai_application_interface_only`, `test_guest_to_ai_denied`, `test_corporate_lateral_denied` |
| Lateral movement | ACL drift that would open a pivot path (missing deny-all, added broad permit, split HA config) is detected before enforcement | `ansible/playbooks/validate-ai-trust-zone.yml`: deny-all ordering, shadowing, and ha-core1 vs ha-core2 consistency | Run the playbook in CI before any enforce run touching the AI boundary |

## 5. MCP / Tool Compromise

A malicious or compromised MCP server or agent tool attempts unauthorized network access, such as scanning, callbacks to attacker infrastructure, or reaching internal services.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| MCP/tool compromise | MCP servers and tool endpoints hosted in the AI zone are subject to the same `VLAN50_IN` policy as agents: named destinations and ports only | `VLAN50_IN` ingress on core SVIs; AI access ports assigned to VLAN 50 | `test_ai_controlled_egress`, `test_ai_approved_internal_service`; playbook checks "AI access ports are assigned to VLAN 50" and "Every trunk carries the AI VLAN" |
| MCP/tool compromise | Compromised tooling cannot re-home a host into a different trust zone on its own: VLAN assignment is infrastructure-owned (trunk allowed lists, access-port assignment) and drift-audited | Golden L2 models reconciled by `roles/vlan_enforce` | `docs/validation.md` "Drift recovery" and "Binding drift" rows; playbook check "VLAN50_IN is defined and bound to Vlan50 on every core" |

## 6. SSRF

An agent or associated web service is manipulated into accessing internal network resources, such as metadata endpoints, admin consoles, or internal APIs.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| SSRF to internal targets | All RFC1918 space is denied with exactly two narrow, named exceptions: `10.10.0.25` tcp 443, and established return traffic to `10.99.0.0/24` | `VLAN50_IN` ingress | `test_ai_deny_by_default`, `test_ai_approved_internal_service`; lab: from a `10.50.0.x` host, curl an unapproved RFC1918 address and port, expect deny or timeout; confirm with `show access-lists` counters |
| SSRF to internal targets | Corporate hosts cannot be used as SSRF relays into the AI zone beyond the single application gateway interface | `VLAN10_IN` single exception to `10.50.0.10` eq 443 | `test_user_to_ai_application_interface_only` |

## 7. Data Exfiltration

An agent sends confidential data to unauthorized external destinations.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Data exfiltration | External egress is limited to two named documentation addresses on 443; DNS only to `10.99.0.53`; arbitrary destinations deny | `VLAN50_IN` ingress; the perimeter firewall pair is a site prerequisite for stateful inspection (README HA topology) | `test_ai_controlled_egress`, `test_ai_approved_dns_ntp_only`, `test_ai_no_broad_permit_in_model`; playbook check "Verify no permit ACE is shadowed by an earlier deny" |
| Data exfiltration | Enforcement limitation: SVI ACLs are stateless and are not a firewall replacement; application-layer DLP and egress proxying are reference architecture | (reference architecture; not implemented by this repository) | Do not claim the repository inspects payloads or proxies TLS |

## 8. Unauthorized Model or API Access

Automation connects to unapproved external AI APIs or inference services, bypassing review.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Unauthorized model/API access | Only the approved external model/automation APIs (`203.0.113.10`, `203.0.113.11`, tcp 443) and the approved internal inference server (`10.10.0.25` tcp 443) are reachable | `ai_trust_zone.approved_egress` and `ai_trust_zone.approved_internal_services` in `topologies/02-segmented/intent.json`, rendered into `VLAN50_IN` by `ai_acl()` | `test_ai_controlled_egress`, `test_ai_approved_internal_service` |
| Unauthorized model/API access | Adding an unapproved destination requires changing `intent.json` and the golden models; unauthorized additions surface as drift | `ansible/golden/*.yml`; `audit_only.yml` (report) and `enforce.yml` (remediate with `change_ticket`) | `docs/validation.md` "Drift recovery"; `python scripts/validate.py`; `python scripts/render.py --check` fails on stale generated files |

## 9. Agent-to-Agent Compromise

One compromised autonomous workload attempts to communicate with or control another, via a shared segment, shared credentials, or shared tool servers.

| Threat | Control | Enforcement point | Validation method |
|---|---|---|---|
| Agent-to-agent compromise | Explicit limitation: `VLAN50_IN` is an SVI ingress ACL and only inspects traffic routed through the SVI. Traffic between two hosts on VLAN 50 stays at Layer 2 and never traverses the ACL. Intra-zone isolation needs additional controls (host firewalls, per-service segmentation, workload identity) | (reference architecture; not implemented by this repository) | Lab procedure: confirm two AI-zone hosts can reach each other directly; do not claim the repository prevents it |
| Agent-to-agent compromise | An entire AI zone cannot be silently re-homed or bridged into another trust zone: trunk allowed lists and access-port VLAN assignment are golden-state managed | `roles/vlan_enforce` L2 reconciliation | Playbook checks "Every trunk carries the AI VLAN", "AI access ports are assigned to VLAN 50", and "Verify redundant cores share identical AI desired state" |

## What this document does not cover

- This is a network-trust-zone threat model, not an application-security review of the agents themselves. It does not assess prompt handling, tool-schema design, model behavior, agent frameworks, or prompt-injection defenses inside the model.
- It does not define secret management for AI workloads; service principals, managed identities, and automation accounts with short-lived credentials are reference architecture only.
- It does not implement or claim a stateful firewall on the SVIs; SVI ingress ACLs are stateless, and stateful inspection plus TLS proxying are reference architecture.
- It does not cover endpoint detection, agent execution auditing, or SIEM correlation beyond what Ansible drift findings and `show` command evidence provide.
- All values in this document are fictional examples (documentation addresses, example subnets). Replace every `ai_trust_zone` value with approved enterprise values before production, then re-run `render.py`, `validate.py`, the test suite, and `validate-ai-trust-zone.yml`.
