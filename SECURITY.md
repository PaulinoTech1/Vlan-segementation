# Security reporting

Do not publish credentials, private keys, compliance snapshots or exploitable deployment details in an issue. Use GitHub private vulnerability reporting if enabled; otherwise contact the repository owner through an established private channel before disclosure.

The repository contains example addresses and explicit secret markers. Treat generated configs as review artifacts. Production operators own platform qualification, secret storage, certificate trust, NAC adapter integrity, monitoring and recovery. See `docs/deployment.md` for drift ownership and `docs/identity-integration.md` for authentication boundaries.
