# SIEM Integration and Security Telemetry

This directory defines the **integration boundary** between this repository's network and identity controls and an external SIEM platform. It answers: what telemetry the controls produce, how that telemetry is normalized and exported, and where this repository's responsibility ends.

**Explicit scope.** This repository defines SIEM integration points and example telemetry formats. It does not deploy, configure, or operate a SIEM platform. Detection engineering, dashboards, threat hunting, case management, and SOC workflows are outside the primary scope of this repository and are the responsibility of the organization operating the external SIEM.

## The five-layer model

Every integration point in this directory is described in terms of five distinct layers. Keep them separate when reading, reviewing, or implementing.

| # | Layer | What it is | Repository role |
|---|-------|------------|-----------------|
| 1 | **Telemetry source** | The device, service, or job that generates an event (firewall, switch, RADIUS/NPS, Entra ID, Intune, Ansible drift job, AI trust zone workload) | Documented here; the repo produces these through its controls |
| 2 | **Transport** | How the event leaves the source (syslog, syslog over TLS, Windows Event Forwarding, HTTPS API, Microsoft Graph API, structured JSON files, stdout) | Example configurations only; site-specific choice |
| 3 | **Normalization** | Conversion into a consistent structured event format (see [docs/event-normalization.md](docs/event-normalization.md)) | Schemas and examples provided; parsing rules live in the external SIEM |
| 4 | **SIEM ingestion boundary** | The point where normalized events cross into the external SIEM | This is the line this repository draws and stops at |
| 5 | **Detection and correlation** | Rules, correlation, investigation, and alerting on ingested events | External SIEM responsibility; this repo only provides [detection-use-cases.md](docs/detection-use-cases.md) as integration examples |

## Telemetry flow

```text
Control
    |
    v
Telemetry Generated          (layer 1: sources in docs/telemetry-sources.md)
    |
    v
Normalization                (layer 3: schemas and field rules in docs/event-normalization.md)
    |
    v
Secure Transport             (layer 2: syslog/README.md, rsyslog example, Ansible local JSON export)
    |
    v
External SIEM                (layer 4: ingestion boundary, intentionally out of scope)
    |
    v
Correlation / Detection      (layer 5: integration examples in docs/detection-use-cases.md)
```

The following vendors and platforms are mentioned only as **possible downstream consumers** of this telemetry. None of them are required, and this repository implements no vendor-specific integrations: Microsoft Sentinel, Splunk, Elastic, Wazuh, Axiom, QRadar, Graylog.

## Contents

- [docs/telemetry-sources.md](docs/telemetry-sources.md): every telemetry source, example events, security value, suggested transports
- [docs/event-normalization.md](docs/event-normalization.md): common event baseline, required vs optional fields, redaction rules
- [docs/detection-use-cases.md](docs/detection-use-cases.md): integration examples only, not a detection framework
- [syslog/README.md](syslog/README.md): how to use the example rsyslog forwarding configuration
- [syslog/rsyslog-forwarding.example.conf](syslog/rsyslog-forwarding.example.conf): generic rsyslog forwarding snippet with TLS
- `ansible/`: Ansible-side drift telemetry export (see [ansible/README.md](ansible/README.md))

## Non-goals

- No SIEM platform is deployed, configured, or required by this repository.
- No SIEM-specific dashboards, parsing rules, or detection content are shipped.
- No agent platform audit pipeline is integrated; AI agent and MCP audit events are documented as "when available."
- No production values appear anywhere: all addresses are fictional example ranges (`10.50.0.0/24`, `10.99.0.0/24`, `203.0.113.0/24` TEST-NET-3) and all hostnames use `.example`.
- SIEM export from Ansible is disabled by default and transmits nothing unless explicitly enabled.
