"""Portable offline checks; never connects to switches or Graph."""
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [p for folder in ('topologies', 'ansible', 'intune_entra_id', '.github')
             for p in (ROOT / folder).rglob('*') if p.is_file()]
    for path in files:
        if path.suffix == '.json':
            json.loads(path.read_text(encoding='utf-8'))
        elif path.suffix in ('.yml', '.yaml'):
            yaml.safe_load(path.read_text(encoding='utf-8'))
    for intent in (ROOT / 'topologies').glob('*/intent.json'):
        data = json.loads(intent.read_text())
        ids = [v['id'] for v in data['vlans']]
        assert len(ids) == len(set(ids)), f'Duplicate VLAN in {intent}'
        assert all(1 < vid < 4095 for vid in ids)
        for device in data['devices']:
            ports = device['trunks'] + [p['name'] for p in device['ports']]
            if device['core']:
                ports += [device['wan_port']]
            assert len(ports) == len(set(ports)), 'Port role collision'
            assert all(p['vlan'] in ids for p in device['ports'])
    for config in (ROOT / 'topologies').glob('*/configs/*.cfg'):
        text = config.read_text()
        assert '{{' not in text and '{%' not in text, f'Unrendered Jinja: {config}'
        assert 'switchport mode dynamic' not in text
        assert 'interface Vlan999' not in text
        assert 'REPLACE_WITH_VAULT_SECRET' in text
        for match in re.finditer(r'switchport trunk allowed vlan (.+)', text):
            assert '999' not in match.group(1).split(',')
    # AI/Automation trust zone: present in segmented topologies, absent from flat.
    flat_vlans = {v['id']: v['name'] for v in
                  json.loads((ROOT / 'topologies/01-flat/intent.json').read_text())['vlans']}
    assert 50 not in flat_vlans, 'Topology 1 must remain flat: no AI VLAN'
    for topology in ('02-segmented', '03-ha'):
        intent = json.loads((ROOT / 'topologies' / topology / 'intent.json').read_text())
        vlans = {v['id']: v['name'] for v in intent['vlans']}
        assert vlans.get(50) == 'AI_AUTOMATION', f'{topology}: VLAN 50 must be AI_AUTOMATION'
        assert 'ai_trust_zone' in intent, f'{topology}: missing ai_trust_zone policy inputs'
        for config in (ROOT / 'topologies' / topology / 'configs').glob('*.cfg'):
            text = config.read_text()
            if 'interface Vlan50' in text:
                assert 'ip access-group VLAN50_IN in' in text, f'{config}: Vlan50 missing ACL binding'
                assert 'permit ip 10.50.0.0 0.0.0.255 any' not in text, \
                    f'{config}: broad AI permit violates deny-by-default'
        golden_dir = ROOT / 'ansible/golden'
        prefixes = {'02-segmented': ('seg-',), '03-ha': ('ha-',)}[topology]
        for golden_path in golden_dir.glob('*.yml'):
            if not golden_path.stem.startswith(prefixes):
                continue
            golden = yaml.safe_load(golden_path.read_text(encoding='utf-8'))
            names = {v['vlan_id']: v['name'] for v in golden.get('golden_vlans', [])}
            assert names.get(50) == 'AI_AUTOMATION', f'{golden_path.name}: VLAN 50 drift'
            for iface in golden.get('golden_l2_interfaces', []):
                allowed = str((iface.get('trunk') or {}).get('allowed_vlans', ''))
                if allowed:
                    assert '50' in allowed.split(','), \
                        f'{golden_path.name}: trunk missing VLAN 50'
    # Local documentation links must resolve; external URLs are intentionally not fetched.
    for doc in [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md')]:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                assert (doc.parent / target.split('#')[0]).exists(), f'Broken link: {doc}: {target}'
    subprocess.run([sys.executable, str(ROOT / 'scripts/render.py'), '--check'], check=True)
    print(f'Validated {len(files)} configuration/support files and documentation links.')


if __name__ == '__main__':
    main()
