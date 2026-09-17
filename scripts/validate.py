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
    # Local documentation links must resolve; external URLs are intentionally not fetched.
    for doc in [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md')]:
        for target in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                assert (doc.parent / target.split('#')[0]).exists(), f'Broken link: {doc}: {target}'
    subprocess.run([sys.executable, str(ROOT / 'scripts/render.py'), '--check'], check=True)
    print(f'Validated {len(files)} configuration/support files and documentation links.')


if __name__ == '__main__':
    main()
