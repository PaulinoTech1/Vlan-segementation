"""Evaluate generated ACL intent against independent expected packet boundaries."""
import importlib.util
import ipaddress
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render', ROOT / 'scripts/render.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
PORTS = {'domain': 53, 'ntp': 123, 'bootpc': 68, 'bootps': 67}
SEG_INTENT = json.loads((ROOT / 'topologies/02-segmented/intent.json').read_text())


def vlan_intent(vlan_id):
    for vlan in SEG_INTENT['vlans']:
        if vlan['id'] == vlan_id:
            return vlan
    raise AssertionError(f'VLAN {vlan_id} missing from segmented intent')


def is_established(ace):
    return bool(ace.get('protocol_options', {}).get('tcp', {}).get('established'))


def allowed(vlan, destination, protocol='tcp', dport=443, source=None, sport=50000,
            established=False):
    source = source or f'10.{vlan}.0.50'
    acl = render.acl_model(SEG_INTENT, vlan_intent(vlan))
    for ace in acl['aces']:
        if ace['protocol'] not in ('ip', protocol):
            continue
        if established and not is_established(ace):
            continue
        if not established and is_established(ace):
            continue
        src_ok = endpoint_matches(ace['source'], source, sport)
        dst_ok = endpoint_matches(ace['destination'], destination, dport)
        if src_ok and dst_ok:
            return ace['grant'] == 'permit'
    return False


def endpoint_matches(endpoint, address, port):
    if 'host' in endpoint and address != endpoint['host']:
        return False
    if 'address' in endpoint:
        net = ipaddress.IPv4Network(endpoint['address'] + '/' + endpoint['wildcard_bits'])
        if ipaddress.IPv4Address(address) not in net:
            return False
    if 'port_protocol' in endpoint:
        expected = endpoint['port_protocol']['eq']
        if port != PORTS.get(expected, expected) and str(port) != expected:
            return False
    return True


class BoundaryTests(unittest.TestCase):
    def test_guest_private_destinations_denied(self):
        for dest in ['10.10.0.20', '10.30.0.20', '10.99.0.10', '172.16.1.1', '192.168.1.1']:
            with self.subTest(dest=dest): self.assertFalse(allowed(20, dest))

    def test_guest_public_web(self):
        self.assertTrue(allowed(20, '203.0.113.80'))

    def test_iot_and_quarantine_no_public_web(self):
        for vlan in (30, 40): self.assertFalse(allowed(vlan, '203.0.113.80'))

    def test_dns_only_named_service(self):
        for vlan in (10, 20, 30, 40):
            self.assertTrue(allowed(vlan, '10.99.0.53', 'udp', 53))
            self.assertFalse(allowed(vlan, '10.99.0.54', 'udp', 53))

    def test_quarantine_proxy(self):
        self.assertTrue(allowed(40, '10.99.0.25'))
        self.assertFalse(allowed(40, '10.99.0.25', dport=22))

    def test_corporate_lateral_denied(self):
        self.assertFalse(allowed(10, '10.30.0.50'))
        self.assertFalse(allowed(10, '10.99.0.50'))

    def test_spoofed_internet_source_denied(self):
        self.assertFalse(allowed(20, '203.0.113.80', source='10.10.0.50'))

    def test_dhcp_bootstrap(self):
        self.assertTrue(allowed(40, '255.255.255.255', 'udp', 67, '0.0.0.0', 68))

    def test_ai_deny_by_default(self):
        # No broad 'permit ip <ai-subnet> any' rule may exist: every
        # cross-zone destination not explicitly approved must deny.
        for dest in ['10.10.0.50', '10.20.0.50', '10.30.0.50', '10.40.0.50',
                     '10.99.0.10', '10.99.0.50', '172.16.1.1', '192.168.1.1',
                     '203.0.113.80']:
            with self.subTest(dest=dest):
                self.assertFalse(allowed(50, dest))

    def test_ai_approved_dns_ntp_only(self):
        self.assertTrue(allowed(50, '10.99.0.53', 'udp', 53))
        self.assertTrue(allowed(50, '10.99.0.53', 'tcp', 53))
        self.assertFalse(allowed(50, '10.99.0.54', 'udp', 53))
        self.assertTrue(allowed(50, '10.99.0.123', 'udp', 123))
        self.assertFalse(allowed(50, '10.99.0.124', 'udp', 123))

    def test_ai_controlled_egress(self):
        self.assertTrue(allowed(50, '203.0.113.10', 'tcp', 443))
        self.assertTrue(allowed(50, '203.0.113.11', 'tcp', 443))
        self.assertFalse(allowed(50, '203.0.113.10', 'tcp', 22))
        self.assertFalse(allowed(50, '203.0.113.80', 'tcp', 443))

    def test_ai_approved_internal_service(self):
        self.assertTrue(allowed(50, '10.10.0.25', 'tcp', 443))
        self.assertFalse(allowed(50, '10.10.0.25', 'tcp', 22))
        self.assertFalse(allowed(50, '10.10.0.26', 'tcp', 443))

    def test_ai_management_admin_return_only(self):
        # Fresh AI-initiated connections to management deny ...
        self.assertFalse(allowed(50, '10.99.0.50', 'tcp', 22))
        self.assertFalse(allowed(50, '10.99.0.10', 'tcp', 443))
        # ... while return traffic of management-initiated sessions is allowed.
        self.assertTrue(allowed(50, '10.99.0.50', 'tcp', 50000,
                                source='10.50.0.20', sport=22, established=True))

    def test_ai_dhcp_and_hsrp(self):
        self.assertTrue(allowed(50, '255.255.255.255', 'udp', 67, '0.0.0.0', 68))
        self.assertTrue(allowed(50, '224.0.0.102', 'udp', 1985))

    def test_user_to_ai_application_interface_only(self):
        self.assertTrue(allowed(10, '10.50.0.10', 'tcp', 443))
        self.assertFalse(allowed(10, '10.50.0.10', 'tcp', 22))
        self.assertFalse(allowed(10, '10.50.0.11', 'tcp', 443))

    def test_guest_to_ai_denied(self):
        self.assertFalse(allowed(20, '10.50.0.10', 'tcp', 443))
        self.assertFalse(allowed(20, '10.50.0.11', 'tcp', 443))

    def test_ai_no_broad_permit_in_model(self):
        acl = render.acl_model(SEG_INTENT, vlan_intent(50))
        for ace in acl['aces']:
            dest = ace['destination']
            broad = (ace['grant'] == 'permit' and ace['protocol'] == 'ip'
                     and dest.get('any'))
            self.assertFalse(broad, f"broad permit ACE: {ace}")
