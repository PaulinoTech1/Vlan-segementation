"""Render reviewable IOS examples and Ansible owned resource models; no device I/O."""
from pathlib import Path
import argparse
import json
from jinja2 import Environment, FileSystemLoader, StrictUndefined
import yaml

ROOT = Path(__file__).resolve().parents[1]


def ai_acl(ai_zone, src, entries, ace, rfc1918_denies):
    """Deny-by-default ingress policy for the AI/Automation trust zone.

    A VLAN alone does not protect privileged autonomous workloads: every ACE
    below names an explicit destination and port. There is intentionally no
    broad 'permit ip <ai-subnet> any' rule.
    """
    for protocol in ('udp', 'tcp'):
        ace('permit', protocol, src, {'host': ai_zone.get('approved_dns', '10.99.0.53'),
                                      'port_protocol': {'eq': 'domain'}})
    ace('permit', 'udp', src, {'host': ai_zone.get('approved_ntp', '10.99.0.123'),
                               'port_protocol': {'eq': 'ntp'}})
    # Management-initiated administration (from 10.99.0.0/24) needs a return
    # path through this stateless ingress ACL. 'established' permits only
    # return traffic; AI-initiated connections to management still deny.
    ace('permit', 'tcp', src, {'address': '10.99.0.0', 'wildcard_bits': '0.0.0.255'},
        established=True)
    # Explicitly approved internal services: narrow exceptions to the
    # private-space deny below.
    for service in ai_zone.get('approved_internal_services', []):
        ace('permit', 'tcp', src, {'host': service['host'],
                                   'port_protocol': {'eq': str(service['port'])}})
    # Controlled egress: named external destinations and ports only.
    for destination in ai_zone.get('approved_egress', []):
        ace('permit', 'tcp', src, {'host': destination['host'],
                                   'port_protocol': {'eq': str(destination['port'])}})
    rfc1918_denies()
    ace('deny', 'ip', {'any': True}, {'any': True})
    return {'name': 'VLAN50_IN', 'acl_type': 'extended', 'aces': entries}


def acl_model(topology, vlan):
    """Source validation plus restricted infrastructure before private-space denies.

    Stateless ingress policy: no unsolicited cross-zone traffic is intended.
    Internet return traffic arrives on the separately controlled firewall transit.
    VLAN 50 (AI_AUTOMATION) uses the deny-by-default ai_acl() policy instead of
    the endpoint policy below.
    """
    vid, subnet = vlan['id'], vlan['prefix'] + '.0'
    src = {'address': subnet, 'wildcard_bits': '0.0.0.255'}
    ai_zone = topology.get('ai_trust_zone', {})
    entries = []

    def ace(grant, protocol, source, destination, established=False):
        entry = {'sequence': (len(entries) + 1) * 10, 'grant': grant,
                 'protocol': protocol, 'source': source, 'destination': destination}
        if established:
            entry['protocol_options'] = {'tcp': {'established': True}}
        entries.append(entry)

    def rfc1918_denies():
        for address, wildcard in [('10.0.0.0', '0.255.255.255'),
                                  ('172.16.0.0', '0.15.255.255'),
                                  ('192.168.0.0', '0.0.255.255')]:
            ace('deny', 'ip', {'any': True}, {'address': address, 'wildcard_bits': wildcard})

    # DHCP bootstrap is common to every endpoint VLAN.
    ace('permit', 'udp', {'any': True, 'port_protocol': {'eq': 'bootpc'}},
        {'any': True, 'port_protocol': {'eq': 'bootps'}})
    # First-hop redundancy messages traverse these SVIs in HA.
    ace('permit', 'udp', src, {'host': '224.0.0.102', 'port_protocol': {'eq': '1985'}})

    if vid == 50:
        return ai_acl(ai_zone, src, entries, ace, rfc1918_denies)

    for protocol in ('udp', 'tcp'):
        ace('permit', protocol, src, {'host': '10.99.0.53', 'port_protocol': {'eq': 'domain'}})
    ace('permit', 'udp', src, {'host': '10.99.0.123', 'port_protocol': {'eq': 'ntp'}})
    # PKI enrollment/remediation proxy is deliberately distinct from management.
    if vid in (10, 40):
        ace('permit', 'tcp', src, {'host': '10.99.0.25', 'port_protocol': {'eq': '443'}})
    # Corporate users reach only the approved AI application interface, never
    # AI hosts or AI infrastructure directly.
    if vid == 10:
        for iface in ai_zone.get('user_facing_interfaces', []):
            ace('permit', 'tcp', src, {'host': iface['host'],
                                       'port_protocol': {'eq': str(iface['port'])}})
    rfc1918_denies()
    if vid in (10, 20):
        ace('permit', 'ip', src, {'any': True})
    ace('deny', 'ip', {'any': True}, {'any': True})
    return {'name': f'VLAN{vid}_IN', 'acl_type': 'extended', 'aces': entries}


def endpoint(value):
    address = ('any' if value.get('any') else 'host ' + value['host']
               if 'host' in value else value['address'] + ' ' + value['wildcard_bits'])
    if 'port_protocol' in value:
        address += ' eq ' + value['port_protocol']['eq']
    return address


def ace_line(ace):
    line = (f"{ace['sequence']} {ace['grant']} {ace['protocol']} "
            f"{endpoint(ace['source'])} {endpoint(ace['destination'])}")
    if ace.get('protocol_options', {}).get('tcp', {}).get('established'):
        line += ' established'
    return line


def outputs():
    env = Environment(loader=FileSystemLoader(ROOT / 'topologies/templates'),
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True,
                      keep_trailing_newline=True)
    template = env.get_template('switch.ios.j2')
    result = {}
    for path in sorted((ROOT / 'topologies').glob('*/intent.json')):
        topology = json.loads(path.read_text())
        topology['allowed'] = ','.join(str(v['id']) for v in topology['vlans'] if v['id'] != 999)
        for device in topology['devices']:
            models = [acl_model(topology, v) for v in topology['vlans']
                      if topology['segmented'] and device['core'] and v['id'] not in (99, 999)]
            acls = [{'name': acl['name'], 'lines': [ace_line(a) for a in acl['aces']]}
                    for acl in models]
            rendered = template.render(topology=topology, device=device, acls=acls)
            result[path.parent / 'configs' / (device['name'] + '.cfg')] = rendered
            golden = {
                'golden_vlans': [{'vlan_id': v['id'], 'name': v['name'], 'state': 'active',
                                  'shutdown': 'disabled'} for v in topology['vlans']],
                'golden_l2_interfaces': [
                    {'name': p, 'mode': 'trunk', 'trunk': {'native_vlan': 999,
                     'allowed_vlans': topology['allowed']}} for p in device['trunks']] + [
                    {'name': p['name'], 'mode': 'access', 'access': {'vlan': p['vlan']}}
                    for p in device['ports']],
                'golden_acls': [{'afi': 'ipv4', 'acls': models}] if models else [],
                'golden_bindings': [{'interface': 'Vlan' + str(v['id']),
                                     'acl': f"VLAN{v['id']}_IN"}
                                    for v in topology['vlans'] if models and v['id'] not in (99, 999)]}
            result[ROOT / 'ansible/golden' / (device['name'] + '.yml')] = yaml.safe_dump(golden, sort_keys=False)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    mismatches = []
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8', newline='\n')
    if mismatches:
        raise SystemExit('Stale generated files: ' + ', '.join(mismatches))
    print('Golden configuration check passed.' if args.check else 'Rendered topology and golden resource files.')


if __name__ == '__main__':
    main()
