# Acceptance and validation

Offline checks cover file syntax, deterministic rendering, topology invariants and authorization policy behavior. They are not live certification. Use a lab matching the target IOS release, Windows version, tenant, CA and NAC before rollout.

| Test | Evidence / expected result |
|---|---|
| Template generation | `python scripts/render.py --check` passes |
| Repository structure/data | `python scripts/validate.py` passes |
| Policy/ACL tests | `python -m unittest discover -s tests -v` passes |
| Ansible parsing | Both playbooks pass `--syntax-check` on Linux |
| Cisco schemas and rendering | `scripts/validate-ansible-models.py` validates every resource; `validate-models.yml` renders switchports and ACLs offline |
| PowerShell parsing | Parser check passes; Graph pilot operations additionally required |
| Flat baseline | Corporate, Guest and IoT share VLAN10; demonstrate absence of isolation |
| Segmentation | Guest cannot reach Corporate/IoT/management except listed infrastructure |
| IoT and quarantine | No general Internet or private-network access; named services work |
| Routing | DHCP, DNS, return paths and firewall NAT succeed where intended |
| Spoofing / IPv6 | Validate snooping/DAI and IPv6 controls separately before claiming protection |
| EAP-TLS success | Valid eligible compliant device receives VLAN10 and DHCP lease |
| Compliance transition | Known noncompliant device receives VLAN40 on reauth |
| Trust failures | Revoked, expired, wrong-issuer and unknown-device certificates rejected |
| State failures | Stale snapshot, duplicate device and Graph outage eventually reject |
| Graph contract | Multiple pages, throttling, access denied, zero devices; no partial overwrite |
| Drift recovery | Change owned VLAN name, add trunk VLAN and unauthorized ACL permit; audit reports, enforce restores |
| Binding drift | Remove/replace an SVI ACL attachment; enforcement restores golden binding |
| Idempotence | Second audit after enforcement reports no owned drift |
| Ownership | Unrelated VLANs/interfaces preserved; manually review out-of-scope drift |
| HA | Access/core/uplink failure and restoration stay within agreed loss budget |
| Rollback | Console recovery restores known-good config and access |

Suggested IOS evidence:

```text
show vlan brief
show interfaces trunk
show spanning-tree vlan 10
show ip interface Vlan10
show ip route
show access-lists
show authentication sessions interface GigabitEthernet1/0/1 details
show radius statistics
show standby brief
show track
```

Record actual test dates, model, software versions, anonymized results, outage times and approver in a private deployment record. Do not put running configs, device identity snapshots, packet captures with credentials or tenant tokens in public GitHub issues.

Cisco IOS collection 11.5.1's VLAN module probes the device type before checking `state: rendered`. To avoid that connection, offline VLAN validation uses its complete argument schema rather than invoking the module. Switchport and ACL modules are additionally exercised in rendered state. Actual VLAN remediation still requires the lab switch test.
