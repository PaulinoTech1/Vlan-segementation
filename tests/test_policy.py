import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'intune_entra_id/radius/evaluate.py'
spec = importlib.util.spec_from_file_location('policy', path)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
ID = '12345678-1234-4234-8234-123456789abc'


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 17, tzinfo=timezone.utc)
        self.snapshot = {'schemaVersion': 1, 'generatedAt': self.now.isoformat(),
                         'eligibleDeviceIds': [ID], 'devices': [
                             {'deviceId': ID, 'complianceState': 'compliant',
                              'lastSyncDateTime': self.now.isoformat()}]}

    def result(self):
        return policy.decision(self.snapshot, ID, self.now)

    def test_compliant_and_member(self):
        self.assertEqual(self.result()['vlan'], 10)

    def test_all_noncompliant_states_restricted(self):
        for state in ['unknown', 'noncompliant', 'inGracePeriod', 'error', 'conflict', 'configManager']:
            with self.subTest(state=state):
                self.snapshot['devices'][0]['complianceState'] = state
                self.assertEqual(self.result()['vlan'], 40)

    def test_outside_group(self):
        self.snapshot['eligibleDeviceIds'] = []
        self.assertEqual(self.result()['vlan'], 40)

    def test_stale_device(self):
        self.snapshot['devices'][0]['lastSyncDateTime'] = (self.now - timedelta(hours=25)).isoformat()
        self.assertEqual(self.result()['vlan'], 40)

    def test_expired_snapshot(self):
        self.snapshot['generatedAt'] = (self.now - timedelta(minutes=16)).isoformat()
        with self.assertRaises(ValueError): self.result()

    def test_future_snapshot(self):
        self.snapshot['generatedAt'] = (self.now + timedelta(minutes=1)).isoformat()
        with self.assertRaises(ValueError): self.result()

    def test_duplicate_device_rejected(self):
        self.snapshot['devices'].append(self.snapshot['devices'][0].copy())
        with self.assertRaises(ValueError): self.result()

    def test_missing_device_rejected(self):
        self.snapshot['devices'] = []
        with self.assertRaises(ValueError): self.result()

    def test_malformed_sync_rejected(self):
        self.snapshot['devices'][0]['lastSyncDateTime'] = 'not-a-date'
        with self.assertRaises(ValueError): self.result()

    def test_case_normalized_guid(self):
        self.assertEqual(policy.decision(self.snapshot, ID.upper(), self.now)['vlan'], 10)


if __name__ == '__main__':
    unittest.main()
