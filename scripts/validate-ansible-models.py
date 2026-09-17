"""Validate golden data against installed Cisco argspecs without network I/O.

Run in the same Linux environment as Ansible, after installing collections.
"""
from pathlib import Path
import yaml
from ansible.plugins.loader import init_plugin_loader
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator

init_plugin_loader()
from ansible_collections.cisco.ios.plugins.module_utils.network.ios.argspec.vlans.vlans import VlansArgs
from ansible_collections.cisco.ios.plugins.module_utils.network.ios.argspec.l2_interfaces.l2_interfaces import L2_interfacesArgs
from ansible_collections.cisco.ios.plugins.module_utils.network.ios.argspec.acls.acls import AclsArgs

root = Path(__file__).resolve().parents[1]
count = 0
for path in sorted((root / 'ansible/golden').glob('*.yml')):
    golden = yaml.safe_load(path.read_text())
    for key, spec in [('golden_vlans', VlansArgs),
                      ('golden_l2_interfaces', L2_interfacesArgs),
                      ('golden_acls', AclsArgs)]:
        if not golden[key]:
            continue
        result = ArgumentSpecValidator(spec.argument_spec).validate(
            {'config': golden[key], 'state': 'rendered'})
        if result.error_messages:
            raise SystemExit(f'{path.name} {key}: {result.error_messages}')
        count += 1
print(f'Cisco argument schemas validated for {count} resource models.')
