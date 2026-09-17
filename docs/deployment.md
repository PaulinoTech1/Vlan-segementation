# Deployment and recovery

1. Select a topology and qualify hardware, IOS XE release, interfaces, licenses, ACL capacity and OOB recovery. The template uses classic authentication CLI; IBNS 2.0 needs a validated conversion.
2. Customize intent and template. Supply unique secrets from a secret manager, use supported encrypted secret storage, generate SSH keys on-box, and test the automation account through console. Type 7 password obfuscation is not encryption.
3. Back up running/startup configurations to encrypted storage. Bootstrap VLANs, ACLs, SVIs, STP, trunks, AAA and ports in a maintenance window. Never paste secret-bearing configs into shared logs.
4. Configure firewall routes/NAT, DHCP, DNS, PKI and redundant RADIUS. Test static boundaries first, then EAP-TLS on a pilot port.
5. Install Ansible on Linux, replace inventory addresses, load the vault and verify SSH keys. Render golden models and audit with a single-host `--limit`.
6. Review drift, enforce with a change ticket, and verify network reachability and boundaries before advancing. Serial execution stops on failure but is not data-plane verification.

For the AI/Automation trust zone (topologies 2 and 3), approve and record the `ai_trust_zone` values (approved resolver, NTP source, internal services, egress destinations) before first enforcement; an empty or wrong approved list either breaks agent workloads or silently permits nothing useful. Run `ansible-playbook playbooks/validate-ai-trust-zone.yml` before every enforce run that touches the AI boundary, and re-run the lab rows in `docs/ai-network-validation.md` after any AI policy change.

## Ownership

Listed VLAN IDs/names/active state are merged; foreign VLANs are neither removed nor declared compliant. Listed L2 interfaces are authoritative for access/trunk mode, access VLAN, native VLAN and allowed VLANs. Named ACL contents are replaced, removing extra ACEs. SVI ACL bindings are reasserted. Routing, HSRP, AAA, DTP, port-security, shutdown and STP are outside this role and require full golden-config review during lifecycle changes.

Resource modules compare parsed state but still require device qualification. ACL replacement may transiently disrupt traffic or enforcement. For zero-gap updates, implement a platform-tested shadow ACL or atomic change mechanism; multi-command IOS changes are not a transaction. Full restoration of a heavily altered device belongs to the bootstrap process.

Saving writes the entire running configuration to startup, including changes made by other administrators. Use an exclusive change window and review pre-existing unsaved changes before enforcement.

Backups can contain credentials: use restricted/encrypted controller storage, retention and separate access controls. Never upload them as public CI artifacts. Prevent overlapping jobs with a scheduler lock. Begin with daily audits; enable scheduled remediation only after qualification, using a real change reference and bounded inventory. CI intentionally has no switch credentials or automatic production workflow.

## Rollback

On failed convergence, stop and use OOB access. Restore the pre-change backup through a device-qualified `configure replace <local-backup>` procedure or reverse the reviewed commands. Recheck routes, ACLs, trunks and authentication before saving. The role does not trigger unattended reloads or broad rollback that could worsen an outage. Failed SSH means actual device state may be unknown.

Before Graph PATCH operations, export existing definitions/rules by ID. Restore those definitions to roll back; pilot assignments are managed separately in Intune. Removing a profile or group does not immediately revoke a certificate or switch session. Use CA revocation and validated NAC disconnect/reauthentication for emergency removal.
