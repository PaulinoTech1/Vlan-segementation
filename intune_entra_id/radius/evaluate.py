"""Offline NAC authorization helper, invoked ONLY after successful EAP-TLS.

The caller must extract deviceId from a validated, policy-controlled certificate,
never from User-Name, a MAC address, or another untrusted RADIUS attribute.
This is an adapter contract, not an NPS plugin or a standalone RADIUS server.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from uuid import UUID


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed


def device_id(value):
    parsed = UUID(value)
    if parsed.int == 0:
        raise ValueError('Empty device identity')
    return str(parsed)


def decision(snapshot, identity, now=None, snapshot_minutes=15, sync_hours=24):
    now = now or datetime.now(timezone.utc)
    identity = device_id(identity)
    if snapshot.get('schemaVersion') != 1:
        raise ValueError('Unsupported snapshot')
    generated = timestamp(snapshot['generatedAt'])
    if not timedelta(0) <= now - generated <= timedelta(minutes=snapshot_minutes):
        raise ValueError('Stale or future snapshot')
    matches = []
    for item in snapshot['devices']:
        try:
            candidate = device_id(item['deviceId'])
        except (KeyError, ValueError, TypeError, AttributeError):
            continue  # Invalid unrelated inventory rows can never authorize.
        if candidate == identity:
            matches.append(item)
    if len(matches) != 1:
        raise ValueError('Unknown or ambiguous device')
    record = matches[0]
    last_sync = timestamp(record['lastSyncDateTime'])
    fresh = timedelta(0) <= now - last_sync <= timedelta(hours=sync_hours)
    eligible = identity in {device_id(value) for value in snapshot['eligibleDeviceIds']}
    corporate = record['complianceState'] == 'compliant' and fresh and eligible
    return {'decision': 'accept', 'vlan': 10 if corporate else 40,
            'reason': 'compliant-and-eligible' if corporate else 'restricted',
            'radius': {'Tunnel-Type': 'VLAN', 'Tunnel-Medium-Type': 'IEEE-802',
                       'Tunnel-Private-Group-Id': '10' if corporate else '40',
                       'Session-Timeout': 900, 'Termination-Action': 'RADIUS-Request'}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--verified-device-id', required=True)
    args = parser.parse_args()
    try:
        result = decision(json.loads(args.snapshot.read_text(encoding='utf-8-sig')),
                          args.verified_device_id)
    except (ValueError, KeyError, TypeError, OSError, AttributeError):
        print(json.dumps({'decision': 'reject', 'reason': 'untrusted-or-unavailable-policy'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
