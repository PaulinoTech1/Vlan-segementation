# Ansible drift telemetry example

`emit_drift_event.yml` is a standalone example that converts the Ansible
configuration-drift artifacts produced by an audit run into structured,
SIEM-ready JSON events. It does not change any enforcement behavior and it
never configures network devices. It uses only `ansible.builtin` modules, so
it can be syntax checked offline with no network collections installed.

## What it does

1. Reads every `drift.json` under the audit artifact directory. These files
   are written by the `vlan_enforce` role (`ansible/roles/vlan_enforce/`)
   at `{{ artifact_dir }}/{{ inventory_hostname }}/drift.json` and are
   secret-free by design: each file holds only booleans (`host`, `vlans`,
   `switchports`, `acls`, `bindings`) indicating which object classes
   drifted from the golden model.
2. Prints a human-readable drift summary to stdout on every run.
3. Optionally writes one structured JSON event file per drifted object
   class under the local export directory, for the site's own SIEM
   collector to pick up.

Conceptual workflow:

```text
Ansible Audit (ansible/playbooks/audit_only.yml)
     |
     v
Drift Detected (per-host drift.json)
     |
     +---- Human-readable output (stdout, always)
     |
     +---- Structured JSON event (one file per drifted object class,
     |      only when export is enabled)
                 |
                 v
           SIEM Collector (site-owned)
```

## Variables

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `artifact_dir` | `/path/to/audit/artifacts` (placeholder) | Audit artifact directory from the audit run. Pass with `-e`. The run fails closed if it does not exist. |
| `siem_export_enabled` | `false` | Master switch. Export is disabled by default. |
| `siem_export_method` | `local_json` | Only supported value in this example. Any other value fails the run when export is enabled. |
| `siem_export_dir` | `{{ playbook_dir }}/../../artifacts/siem` | Local directory for emitted JSON event files. |
| `siem_export_endpoint` | `""` (empty) | Reserved for a future https method. Must be non-empty before any https delivery is attempted. |

## Invocation

Run an audit first, then emit events from its artifacts:

```bash
# 1. Audit (writes per-host drift.json artifacts, never changes config)
ansible-playbook ansible/playbooks/audit_only.yml

# 2a. Report only (default): stdout summary, nothing written or transmitted
ansible-playbook siem_integration/ansible/emit_drift_event.yml \
  -e artifact_dir=/path/to/audit/artifacts

# 2b. Report plus local JSON export for the site collector
ansible-playbook siem_integration/ansible/emit_drift_event.yml \
  -e artifact_dir=/path/to/audit/artifacts \
  -e siem_export_enabled=true
```

Each emitted event carries `timestamp` (UTC), `event_type`
(`configuration_drift`), `severity`, `device`, `configuration_object`,
`expected_state`, `observed_state`, `remediation` (`not_performed`, because
this example never remediates), `correlation_id`, and `message`. Files are
named `<device>-<object>-<timestamp>.json` with mode `0600` inside a
`0700` directory.

## Fail-closed behavior

- Export is disabled by default. With defaults the playbook prints the
  stdout summary and writes nothing.
- If `siem_export_enabled=true` and `siem_export_method` is anything other
  than `local_json` or `https`, the run fails with a clear message.
- If the method is `https` and `siem_export_endpoint` is empty, the run
  fails rather than guessing a destination.
- `https` delivery is intentionally not implemented here; the run fails
  with a message directing the operator to use `local_json` and let the
  site collector forward the files.
- A missing `artifact_dir` fails the run instead of silently producing an
  empty report.

## Security notes

- No SIEM token, API key, endpoint, or credential is hard-coded. There is
  nothing to redact because nothing secret is ever configured.
- `drift.json` artifacts contain booleans only; this playbook reads and
  reports those booleans and never handles authentication material.
- Event files are written with restrictive permissions (`0600` files in a
  `0700` directory).
- External SIEM transmission is disabled by default and is left to the
  site's collector, which owns transport security (TLS, authentication,
  least-privilege credentials).
