# Family Finance Hub for Home Assistant OS

This is a native **amd64** Home Assistant add-on/app for a Dell Tiny PC running Home Assistant OS. It runs the existing Runway Python/Svelte application; it is not a Lovelace financial dashboard, a TV dashboard, or a Compose stack installed into HA OS. No privileged host, Docker, Supervisor or Home Assistant API access is requested.

## Install from the feature branch

The custom repository URL, once the feature branch has been pushed, is:

```text
https://github.com/Vico07/Runway#feat/family-finance-hub-home
```

1. In Home Assistant, open **Settings → Add-ons → Add-on Store → ⋮ → Repositories** (new HA versions may call these **Apps**).
2. Paste the URL above, add it, and refresh the store. If the branch is not available on GitHub yet, installation cannot succeed; do not substitute `main` and assume it contains this feature.
3. Select **Family Finance Hub** and **Install**. The initial source build can take several minutes and needs Internet access to GitHub, Docker Hub, npm and PyPI. Source and base versions are pinned by the package; the build does not copy application code into a second UI.
4. In Configuration, set your timezone. Leave `sensor_token` empty unless you want optional read-only sensors. Keep port mappings disabled.
5. Start it; enable **Start on boot**, **Watchdog**, and **Show in sidebar** if offered.
6. Open **Family Finance Hub** from the sidebar or **Open Web UI**. It opens `#family`; links inside it lead to Budget & Spending, Smart Card Planner, transactions, budgets and payment editing.

No separate Runway login is required in this add-on: **Home Assistant Ingress authenticates the session**. The panel is restricted to HA administrators. Anyone with access to this financial app has household editing rights. Read-only sensor credentials cannot edit the app. Keep HA authentication/MFA and household user permissions configured appropriately.

There is **no fixed add-on browser URL or LAN port** to bookmark. Use HA's sidebar. Its temporary URL has the form `https://<your-ha-address>/api/hassio_ingress/<session>/#family`; Supervisor creates that session. Never invent or publish a session URL. Remote access can use your existing secure HA connection or VPN; do not expose the add-on container directly.

## Why Ingress works

Only Supervisor's documented gateway address `172.30.32.2` is accepted on the application listener. `X-Ingress-Path` is accepted only from that peer and must be a valid session prefix. API calls, assets, images, downloads and navigation stay under that prefix. Framing is restricted to the same origin in Ingress mode; ordinary standalone installations retain their anti-framing policy. CSRF/custom-header checks remain enabled. The iframe does not register a service worker over Home Assistant's root.

Desktop and iPhone use Runway's responsive application, including interactive payment edits, credit card strategies, daily forecasts, hypothetical comparisons, CSV imports, budgets and transaction tools. Pinch-to-zoom is enabled. No TV/Lovelace duplication is included.

## Data, backups, restart and update

SQLite (`runway.db`), encryption key (`secret.key`), profiles, rules, schedules, imports and options live under Supervisor's persistent **`/data`** volume. The app starts empty; **no real or demo financial records are seeded automatically**. Bank synchronization and connection endpoints are disabled in the add-on. Add manual accounts and import only your own statements through the UI.

- Stop/start or host reboot retains `/data`. Enable Start on boot.
- Before updating, create a Home Assistant backup and explicitly include this add-on. The package requests **cold backups**: Supervisor stops it while copying `/data`, avoiding an inconsistent SQLite/WAL snapshot.
- Download/retain the encrypted HA backup and its recovery key off the HA machine. The backup includes the app's data and key; protect it as financial information.
- For a portable additional copy, use Runway **Settings → Data → Download backup**. Restore it through Runway's existing inspect/restore flow; retain the encryption key for encrypted provider settings even though this deployment does not enable bank sync.
- Restore a HA backup including this add-on to recover `/data`, configuration and the encryption key together. Restore only trusted backups, then check account and schedule data before relying on forecasts.
- For updates, refresh the repository/store, review the changelog, take a backup, and use HA's **Update** button when a new add-on version is offered. A branch change without a version bump is not automatically an add-on release. This feature branch has not been merged into `main`.

## Optional read-only sensors

They are optional; the main application does not need them. Generate a random token **locally**, for example `openssl rand -hex 32`, put it in the add-on `sensor_token` option, and restart. Do not paste tokens into issues, chat, Git or logs.

A separate internal listener on port **8766** then serves only:

- `GET /api/ha/summary`: checking balance, next expected paycheck, bounded upcoming bills, warnings, freshness.
- `GET /api/ha/upcoming`: next paycheck and next five scheduled cash payments.
- `GET /api/ha/cashflow`: checking forecast minimum and negative-balance warning.
- `GET /api/ha/budget`: bounded category budget progress.

Every call requires `Authorization: Bearer <sensor_token>`. Missing or wrong tokens fail; writes, backups, transactions and all other routes are refused on this listener. No token is required or transmitted to use Ingress. No financial input is claimed independently verified; schedule amounts are **expected**, not confirmed income. Checking coverage is the account selection used by Runway's forecast.

Keep the sensor port's host mapping disabled. HA Core can use the add-on's internal hostname (`<repository-id>-family-finance-hub`, shown in the add-on's information; use the actual hostname shown by your installation). Copy `sensors.example.yaml` into your HA configuration with your actual internal URL and put the Authorization value in `secrets.yaml`. Validate HA configuration before restarting/reloading. Tokens and financial attributes remain private. HA sensors and Recorder may retain financial history; disable Recorder for these entities if you do not want another financial history store.

No actual HA OS/Supervisor machine was available for integration testing in Codex. Container, simulated Ingress, read-only API, storage/restart and backup tests are documented with the implementation; complete the installation, login, iPhone interaction and a restore drill on your own HA OS instance before relying on it.

## Troubleshooting

- Store entry missing: verify the branch exists remotely and the repository URL includes `#feat/family-finance-hub-home`.
- Direct port responds 403: expected. Open through HA Ingress, not a container address.
- Sidebar entry absent: enable Show in sidebar and sign in as an HA administrator.
- UI opens but a write fails: check HA reverse proxies preserve Host/Origin and Ingress headers; direct/spoofed requests are intentionally rejected.
- Empty data after reinstall/restore: confirm the correct add-on's `/data` was restored; never replace real records with demo data.
- Unsupported CPU: this package advertises only the tested amd64 architecture, suitable for the Dell Tiny PC. ARM builds are not claimed.
