# Addressing and traffic boundaries

All addresses are examples; reserve actual ranges through IPAM.

| VLAN | Subnet | Gateway | Allowed access |
|---|---|---|---|
| 10 Corporate | 10.10.0.0/24 | 10.10.0.1 | DNS, NTP, PKI/remediation proxy, Internet |
| 20 Guest | 10.20.0.0/24 | 10.20.0.1 | DNS, NTP, Internet |
| 30 IoT | 10.30.0.0/24 | 10.30.0.1 | DNS, NTP; add reviewed controller exceptions |
| 40 Quarantine | 10.40.0.0/24 | 10.40.0.1 | DNS, NTP, HTTPS remediation proxy |
| 99 Management | 10.99.0.0/24 | 10.99.0.1 | Trusted administration and infrastructure |
| 999 Unused native | No SVI | None | Parking/native VLAN; excluded from trunks |

Management services: RADIUS `.10` and `.11`, DHCP `.20`, PKI/remediation proxy `.25`, admin jump host `.50`, DNS `.53`, NTP `.123`. The proxy must allow required Intune, Entra, enrollment and revocation destinations; this repository does not maintain Microsoft's changing endpoint list. Guest DNS should expose only approved public zones. Management is a trusted zone without an ingress ACL here; host firewalls and restricted physical access remain necessary.

Core Gi1/0/1 connects to access Gi1/0/23. Core Gi1/0/24 is the firewall transit. HA core2 Gi1/0/1 connects to access Gi1/0/24, and core Gi1/0/2 links the cores. Access Gi1/0/1 is EAP-TLS (static VLAN 40 until authorized), Gi1/0/2 Guest, Gi1/0/3 IoT. In segmented examples, Gi1/0/4–10 are physically secured Management ports for NAC1, NAC2, DHCP, proxy, jump host, DNS and NTP respectively. These are single-MAC server ports, not hypervisor trunks. Spread redundant services across independent infrastructure switches in production. Unused ports are shut. Flat management uses access 10.10.0.12; the external admin source 10.99.0.50 must be routed through the firewall.

DHCP: reserve `.1–.20`, set option 3 to gateway `.1` and option 6 to 10.99.0.53. Configure one scope per routed VLAN and verify relay `giaddr`. Management services use static/reserved addresses. Flat DHCP at 10.99.0.20 requires firewall routing to that service.

Each core transit is 172.31.<core index>.2/30 toward firewall `.1`. Configure firewall return routes for each VLAN through the core transit IP. HA requires tracked primary/backup routes or a validated routing protocol for return-path failover. Validate NAT and asymmetric flow handling; HSRP does not change firewall routes.

Ingress SVI ACLs allow only named infrastructure before RFC1918 denies. Only expected subnet sources receive Internet access. The DHCP exception permits UDP 68 to 67 including broadcasts. This is not DHCP server protection: deploy validated snooping, DAI and IP Source Guard after mapping trust ports and static bindings. HA ACLs permit HSRPv2 multicast.

Corporate-to-IoT and Corporate-to-Management are denied except named services. Bidirectional applications require reviewed return rules or a stateful firewall. Same-VLAN traffic bypasses SVI ACLs: use private VLANs/protected ports or host controls if isolation is required. IPv6 routing is absent; disable IPv6 on managed endpoints or add RA Guard and equivalent IPv6 policy before enabling service. IPv4 ACLs alone do not provide dual-stack isolation.
