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
