# Syslog Forwarding Example

This directory contains a generic rsyslog forwarding configuration snippet: [rsyslog-forwarding.example.conf](rsyslog-forwarding.example.conf).

## How it is meant to be used

- It is a **starting example**, not a drop-in configuration. Copy it, adapt it to your site, and test it before relying on it for security telemetry.
- It forwards selected facilities and severities (auth, authpriv, daemon, and local0 through local7, which is where most network devices send their logs) to a central collector over TLS.
- It uses an in-memory assisted queue so that a brief collector outage does not silently drop security events. Queue size and disk-assisted behavior should be tuned to the site's tolerance for loss.

## TLS notes

- The example uses the `gtls` driver with certificate validation enabled. Do not disable certificate validation (`StreamDriver.AuthMode="anon"` or equivalent) in production; unauthenticated TLS does not protect against a man-in-the-middle between the device and the collector.
- You must provide your own CA certificate, client certificate, and client key. The paths in the example are placeholders and are marked as such.
- rsyslog TLS behavior varies by version and distribution. Verify the driver name (`gtls` vs `ossl`) and permitted-peer settings against your installed rsyslog version.

## What to replace

Every site-specific value in the example is marked with a `# REPLACE:` comment. At minimum, replace:

1. `siem-collector.example` with your collector hostname (fictional `.example` name in the snippet; use your real collector).
2. The CA, certificate, and key file paths with your PKI-issued files.
3. The permitted peer name with your collector's certificate identity.
4. Facility, severity, and queue parameters to match your log volume and loss tolerance.

The collector itself, and anything downstream of it (parsing, correlation, alerting), is the external SIEM and is intentionally out of scope for this repository.
