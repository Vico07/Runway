---
title: Home Assistant and home server
description: Native amd64 Ingress add-on and authenticated standalone Linux deployment.
sidebar:
  order: 5
---

Family Finance Hub includes a native **amd64 Home Assistant OS add-on/app**, suitable for a Dell Tiny PC. It opens the complete responsive Runway application through Home Assistant Ingress; no TV dashboard or parallel Lovelace finance interface is required. Home Assistant OS is not treated as an ordinary Compose host.

See the repository's [add-on installation and backup guide](https://github.com/Vico07/Runway/blob/feat/family-finance-hub-home/addons/family_finance_hub/DOCS.md) for the custom repository URL, sidebar setup, authenticated Ingress, optional read-only sensors, cold HA backups and restore procedure. The branch must exist on GitHub before installation. Native amd64 container builds and an Ingress simulation are validated; an actual HA OS installation must still be checked on your own device. ARM support is not advertised as tested.

For a **separate home Linux server**, see the [Compose guide](https://github.com/Vico07/Runway/blob/feat/family-finance-hub-home/deploy/home/README.md). It builds this fork, persists SQLite and Caddy data, uses HTTPS on a configured LAN address and retains Runway's mandatory OIDC sign-in. The dashboard URL is `https://<RUNWAY_HOSTNAME>/#family`. Supply your identity provider, local DNS and trusted local CA; no credentials are provided in the repository. Do not use a public unauthenticated port.

Both deployment profiles are manual-only: automatic bank sync, manual bank sync and bank-connection endpoints are disabled. The ordinary existing Runway deployment remains available. No personal financial records or real credentials are part of the package. Synthetic demo/test data is kept separate from household storage.

From Family Finance Hub, open [Budget & Spending](/Runway/using/spending/) for imports, budgets and transaction drill-down, or [Smart Card Planner](/Runway/using/card-planner/) for hypothetical card and purchase comparisons. [Family Finance Hub](/Runway/using/family/) documents manual balances and the November/December 2026 comparison.
