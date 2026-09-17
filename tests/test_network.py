"""Evaluate generated ACL intent against independent expected packet boundaries."""
import importlib.util
import ipaddress
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('render', Path(__file__).resolve().parents[1] / 'scripts/render.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
PORTS = {'domain': 53, 'ntp': 123, 'bootpc': 68, 'bootps': 67}


def matches(endpoint, address, port):
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


def allowed(vlan, destination, protocol='tcp', dport=443, source=None, sport=50000):
    source = source or f'10.{vlan}.0.50'
    acl = render.acl_model({'id': vlan, 'prefix': f'10.{vlan}.0'})
    for ace in acl['aces']:
        if ace['protocol'] not in ('ip', protocol):
            continue
        if matches(ace['source'], source, sport) and matches(ace['destination'], destination, dport):
            return ace['grant'] == 'permit'
    return False


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
