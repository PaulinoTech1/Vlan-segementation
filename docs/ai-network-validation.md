# AI/Automation trust zone validation

This document complements the [acceptance runbook](validation.md). The runbook covers
repository-wide offline checks; this document covers boundary validation specific to
the AI/Automation trust zone (VLAN 50, `AI_AUTOMATION`, 10.50.0.0/24) in the Segmented
Wired Star (topology 2) and the High-Availability Segmented Star (topology 3).

Topology 1 is the intentionally flat baseline and has no AI zone. Example AI
workloads there share VLAN 10 with ordinary corporate endpoints, with no inter-zone
ACL to constrain them. Keep it that way when running this validation: the flat
topology is the control case that shows what the segmented topologies protect
against.

VLAN50_IN is deny-by-default. Every permit ACE names an explicit destination and
port; there is intentionally no broad `permit ip 10.50.0.0 0.0.0.255 any` rule.
Policy source of truth: `scripts/render.py` (`ai_acl()` / `acl_model()`), rendered
from the `ai_trust_zone` policy inputs in `topologies/02-segmented/intent.json`.
All addresses below are fictional example values (TEST-NET-3 and RFC1918/private
ranges); replace with approved enterprise values before deployment.

## Boundary test matrix

Each row assumes the intent examples in the repository. `ALLOW` means the path is
expected to work end to end through VLAN50_IN and the destination policy;
`DENY` means the first-hop ACL is expected to block it.

| # | Source -> Destination | Port/proto | Expected | Notes |
|---|---|---|---|---|
| 1 | AI host (10.50.0.x) -> approved external model API (203.0.113.10) | tcp/443 | ALLOW | Controlled egress, named destination only. 203.0.113.10 is a documentation address, not a real endpoint. |
| 2 | AI host (10.50.0.x) -> approved DNS resolver (10.99.0.53) | udp+tcp/53 | ALLOW | Only the approved resolver. Other resolvers (for example 10.99.0.54) deny. |
| 3 | AI host (10.50.0.x) -> approved internal inference/API server (10.10.0.25) | tcp/443 | ALLOW | Narrow exception to the private-space deny. Other hosts (for example 10.10.0.26) deny. |
| 4 | AI host (10.50.0.x) -> user workstation (10.10.0.50) | any | DENY | No AI-to-user initiation. User-to-AI is limited to row 10. |
| 5 | AI host (10.50.0.x) -> management interface (10.99.0.10), fresh connection | tcp/443 | DENY | `established` return traffic only; AI-initiated sessions to management always deny. |
| 6 | AI host (10.50.0.x) -> domain controller administrative services | tcp/445, 389, 636, 9389 | DENY | No DC admin exception is declared in the current intent. If a site requires one, add it as an explicit `approved_internal_services` entry and re-validate. |
| 7 | AI host (10.50.0.x) -> guest network (10.20.0.50) | any | DENY | AI has no business reaching Guest. |
| 8 | AI host (10.50.0.x) -> arbitrary RFC1918 (192.168.1.1) | any | DENY | Explicit RFC1918 denies precede the final deny-all. |
| 9 | AI host (10.50.0.x) -> unapproved external host (203.0.113.80) | tcp/443 | DENY | Egress is a named allowlist, not general HTTPS egress. 203.0.113.80 is a documentation address. |
| 10 | Corporate user (10.10.0.x) -> AI application gateway (10.50.0.10) | tcp/443 | ALLOW | The single narrow exception in VLAN10_IN. Port 22 to the same host denies. |
| 11 | Corporate user (10.10.0.x) -> other AI host (10.50.0.11) | tcp/443 | DENY | Users reach the gateway only, never AI hosts directly. |
| 12 | Guest (10.20.0.x) -> AI infrastructure (10.50.0.10) | tcp/443 | DENY | No Guest-to-AI path exists in any zone policy. |
| 13 | Management-initiated SSH to AI host, return traffic | tcp, established | ALLOW | Management (10.99.0.0/24) can administer the zone; the ACE matches return traffic only, verified by the `established` flag. |

## Validation tools

Use the tool that matches the traffic you are validating. Do not depend on ICMP
alone to validate segmentation: VLAN50_IN permits no ICMP at all, so a failed ping
proves nothing about TCP segmentation, and elsewhere ICMP may pass while TCP is
blocked. Test the actual protocols and ports named in the policy.

* `ping`: limited value here (no ICMP permits in VLAN50_IN); use only to confirm
  expected-drop behavior, never to claim a path is open.
* `Test-NetConnection` (for example `-ComputerName 10.10.0.25 -Port 443`, `-Port 445`)
  from a Windows lab host to check rows 3, 4 and 6.
* `curl -v https://<host>:443` from an AI lab host for rows 1, 3 and 9; expect
  connection refused or timeout on rows 9 and 10's negative ports.
* `nc -zv <host> <port>` for quick TCP reachability probes against rows 3, 10 and 11.
* `traceroute` / `tracert` to confirm routed (Layer-3, ACL-enforced) paths rather
  than assumed direct L2 reachability.
* Ansible assertions: `ansible/playbooks/validate-ai-trust-zone.yml` (offline
  golden-model checks: VLAN 50 naming, trunk membership, ACL ordering, broad-permit
  rejection, ha-core1 vs ha-core2 consistency) and `ansible/playbooks/audit_only.yml`
  (device drift; results land in `artifacts/ansible/drift.json`).
* IOS evidence on the core switches:

```text
show vlan brief
show interfaces trunk
show access-lists
show ip interface Vlan50
show standby brief
```

## Offline checks vs lab tests

These checks run without hardware and verify that the declared desired state
matches the policy intent. They are not live certification: passing them proves
the configuration model is correct, not that real traffic is blocked on real
hardware. Every ALLOW/DENY expectation in the matrix above must also be exercised
in a lab before rollout.

| Matrix row | Offline check (no hardware) | Lab (required) |
|---|---|---|
| 1 | `test_ai_controlled_egress`; playbook: reject broad permits, no shadowing | `curl` from AI host to 203.0.113.10:443 through the firewall path |
| 2 | `test_ai_approved_dns_ntp_only` | `nslookup`/`dig` against 10.99.0.53; also confirm 10.99.0.54 fails |
| 3 | `test_ai_approved_internal_service` | `Test-NetConnection` or `curl` to 10.10.0.25:443 from AI host |
| 4 | `test_ai_deny_by_default` (includes 10.10.0.50) | Attempt AI-to-workstation connection; confirm deny and log entry |
| 5 | `test_ai_management_admin_return_only`; playbook: reject permissive AI-to-management rules | Fresh AI-initiated TCP to 10.99.0.10 fails; management-initiated SSH session to AI host works and its return traffic passes |
| 6 | `test_ai_deny_by_default` (covers 10.99.0.x) | `Test-NetConnection` to DC ports from AI host; expect deny |
| 7 | `test_ai_deny_by_default` (includes 10.20.0.50) | AI-to-guest connection attempt; confirm deny |
| 8 | `test_ai_deny_by_default` (includes 192.168.1.1) | Route/probe to unlisted RFC1918 from AI host; confirm deny |
| 9 | `test_ai_controlled_egress`; `test_ai_deny_by_default` | `curl` to unapproved external host on 443; confirm deny at egress policy |
| 10 | `test_user_to_ai_application_interface_only` | HTTPS to 10.50.0.10:443 from corporate host succeeds; port 22 fails |
| 11 | `test_user_to_ai_application_interface_only` | HTTPS to 10.50.0.11:443 from corporate host fails |
| 12 | `test_guest_to_ai_denied` | HTTPS to 10.50.0.10:443 from guest host fails |
| 13 | `test_ai_management_admin_return_only`; playbook: established-return-only check | Management-initiated SSH session completes; spoofed AI-initiated SSH to 10.99.0.x fails |

Additional offline coverage: `test_ai_dhcp_and_hsrp` (DHCP bootstrap and HSRP
224.0.0.102:1985), `test_ai_no_broad_permit_in_model` (no `permit ip ... any` in
VLAN50_IN), and the playbook checks that VLAN50_IN ends with an explicit deny-all
and is bound to `Vlan50` on every core.

## HA considerations (topology 3)

The AI/Automation trust zone must exist consistently on both redundant cores:

* Gateway: HSRP virtual IP 10.50.0.1; ha-core1 uses .2, ha-core2 uses .3.
* Run `ansible/playbooks/validate-ai-trust-zone.yml` to assert ha-core1 and
  ha-core2 share identical AI desired state (VLAN 50, trunk membership, VLAN50_IN
  ACEs and ordering).
* Failure testing (primary gateway failure, uplink failure, ACL drift between
  peers, AI VLAN missing from one trunk, split configuration) follows
  [docs/ha.md](ha.md). Repeat the lab rows above from each core after a
  failover to confirm the standby path enforces the same policy.
