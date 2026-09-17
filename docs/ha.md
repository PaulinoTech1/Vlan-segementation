# HA and VRRP alternative

HSRP retains the gateway; RSTP selects a loop-free L2 path. Core1 is STP root (24576) and preferred HSRP router (110); core2 is 28672/100. Link tracking subtracts 30 on uplink loss; preemption waits 60 seconds. The inter-core trunk carries endpoint and Management VLANs.

Link tracking cannot detect a failed firewall beyond an electrically-up link. Qualify IP SLA/object tracking or dynamic routing for that case. Configure firewall return-path failover too. Simultaneous path failures may partition the VLAN and create dual-active gateways. Independent power, diverse cabling, redundant DHCP/DNS/PKI/RADIUS and firewall services are site prerequisites. The access switch remains a failure domain.

Dynamic forwarding failover occurs on explicit trunks; DTP auto/desirable is disabled. Ordinary LACP across independent cores is invalid. A stack/MLAG design requires a coordinated replacement of the independent-core/RSTP design.

## VRRP option: replace HSRP, never combine on the same VIP

Vendor-neutral intent: group ID equals VLAN ID, VIP `.1`, physical addresses `.2`/`.3`, priority 110/100, preempt delay 60, tracked uplink decrement 30. Keep STP root aligned to the preferred router.

Classic Cisco IPv4 VRRP example for core1 VLAN10; confirm syntax for the target release:

```text
interface Vlan10
 ip address 10.10.0.2 255.255.255.0
 vrrp 10 ip 10.10.0.1
 vrrp 10 priority 110
 vrrp 10 preempt delay minimum 60
 vrrp 10 track 1 decrement 30
```

Repeat for VLAN20/30/40/99, use `.3` and priority 100 on core2, remove all `standby` commands, and replace the HSRP ACL exception with IP protocol 112 to 224.0.0.18 from each subnet. VRRPv3/newer address-family syntax differs. HSRP MD5 authentication does not translate directly to VRRP; qualify vendor security controls.

Test access-link loss, active-core power loss, upstream loss, inter-core loss, restoration and preemption under load. Record packet loss, gateway MAC movement, STP state, DHCP/reauth behavior and firewall session survival against an agreed outage budget.

## AI/Automation trust zone in HA

Topology 3 carries the AI/Automation trust zone (VLAN 50, 10.50.0.0/24) on both redundant paths. Each core configures `interface Vlan50` with HSRP group 50, virtual IP 10.50.0.1, physical addresses 10.50.0.2 (core1, priority 110) and 10.50.0.3 (core2, priority 100), the same uplink tracking and 60-second preemption as the other VLANs. All trunks (core uplinks to access, inter-core link) allow VLAN 50 explicitly; native VLAN remains the unused 999. Both cores apply the identical VLAN50_IN ingress ACL; any divergence is a defect, not redundancy.

Run `ansible-playbook playbooks/validate-ai-trust-zone.yml` to check the desired state offline before and after changes. It verifies VLAN 50 presence and naming, trunk membership, VLAN50_IN presence and Vlan50 binding, absence of broad permit rules, absence of non-established AI-to-management permits, deny-all ordering, and ha-core1 versus ha-core2 consistency.

Failure scenarios to exercise in the lab:

1. Primary gateway failure: power off or isolate ha-core1. HSRP group 50 must fail over to ha-core2 with the VIP 10.50.0.1 retained. AI workloads keep their gateway; verify with `show standby brief` on both cores and continuous TCP (not only ICMP) from an AI host to an approved destination.
2. Access-switch uplink failure: shut ha-access Gi1/0/23. RSTP must converge on the Gi1/0/24 path to ha-core2 without dropping VLAN 50 from the allowed list. Confirm `show interfaces trunk` still lists 50 on the surviving uplink.
3. ACL drift between redundant devices: add a test ACE to VLAN50_IN on ha-core1 only, then run `playbooks/audit_only.yml --limit ha-core2` and `validate-ai-trust-zone.yml`. Audit must report drift on the modified device and the validator must fail the consistency check. Restore with `enforce.yml` and a change ticket, then re-run both.
4. AI VLAN missing from one trunk: remove 50 from an allowed list. `validate-ai-trust-zone.yml` fails the trunk-membership check naming the device. On hardware, confirm with `show interfaces trunk`.
5. Incorrect VLAN assignment: move an AI access port to VLAN 10 in the golden model. The validator's access-port check and `scripts/validate.py` topology invariants catch the mismatch before enforcement.
6. Accidental permissive AI-to-management rule: add a non-established `permit tcp` toward 10.99.0.0/24 in the golden VLAN50_IN. The validator rejects it; only the `established` return ACE is allowed toward management.
7. Split configuration between redundant peers: apply any AI change to one core's golden file only. The ha-core1 versus ha-core2 equality assertion fails. Never enforce a split change; regenerate both cores from the same intent.json and re-validate.
