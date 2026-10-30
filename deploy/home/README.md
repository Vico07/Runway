# Family Finance Hub on a home Linux server

This builds **this fork**, including Family Finance Hub, Budget & Spending and Smart Card Planner. It does not pull the upstream application in place of the feature branch. The original root `docker-compose.yml` remains available for existing Runway deployments. Home Assistant OS users should use the [native add-on](../../addons/family_finance_hub/DOCS.md) instead of trying to run Compose in HA OS.

## Prerequisites and authentication

Use a Linux server with Docker Engine, Docker Compose v2.24+ (current v2 recommended), Git, and at least 2 GB free memory for the build. The image uses Python 3.14 and Node 26 without installing those on your host. amd64 is tested; other host architectures are not claimed as validated.

Choose a static LAN IPv4 address and hostname, for example `runway.home.arpa`. Configure local DNS (router/Pi-hole/AdGuard), or each client's hosts file, to resolve that hostname to the server. On iPhone, use working local DNS; iOS does not provide a normal hosts-file editor. Do not use the documentation address in `.env.example` as your server address.

Have an existing OpenID Connect provider (Authentik, Keycloak, Pocket ID, etc.) reachable by both the server and browsers. Create a **confidential OIDC client**:

- Redirect URI: `https://runway.home.arpa/auth/callback`
- Post-logout redirect URI: `https://runway.home.arpa/auth/signed-out`
- Standard authorization-code flow; Runway handles PKCE and validates tokens.
- Set the issuer URL, client ID and secret in the local `.env` and restrict `OIDC_ALLOWED_EMAILS` to your household.

These values come from your provider; no usable credentials are supplied or committed. Everyone allowed into Runway shares the household data and editing rights. There is no auth bypass in this profile.

## Clone and configure

```bash
git clone --branch feat/family-finance-hub-home --single-branch https://github.com/Vico07/Runway.git
cd Runway/deploy/home
cp .env.example .env
chmod 600 .env
printf '\nRUNWAY_SECRET_KEY=%s\n' "$(openssl rand -hex 32)" >> .env
nano .env
```

Set `RUNWAY_BIND_IP` to your server's LAN IP, `RUNWAY_HOSTNAME` to the DNS name, OIDC values, allowed household emails, and `TZ`. Remove the earlier empty `RUNWAY_SECRET_KEY=` line so the generated key has a single definition. Keep an offline/password-manager copy of the key. `.env` is Git-ignored and excluded from the Docker build context.

## Build and start

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 runway
```

Compose starts the ordinary unprivileged Runway image and Caddy. SQLite and Runway's data persist in the `runway-family_runway_data` named volume. Caddy's private local CA and configuration persist in separate named volumes. No data is seeded automatically. Bank connection endpoints and manual/automatic bank sync are blocked by `RUNWAY_MANUAL_ONLY=1`; no bank credentials are configured. Other normal Runway installations keep their existing behavior.

The app has no published port 8765 in this profile. Caddy exposes HTTPS on the specified LAN address only, port 443. Do not forward this port from the router to the public Internet. For remote access, prefer your existing VPN; if using an existing reverse proxy, preserve HTTPS and Runway's OIDC sign-in rather than disabling auth.

## Trust HTTPS on household devices

Caddy uses a private local CA. Export **only its public root certificate**, never its private key:

```bash
docker compose cp https:/data/caddy/pki/authorities/local/root.crt ./runway-local-root.crt
```

Install this root into each device's trusted certificate store. On Debian/Ubuntu desktops:

```bash
sudo cp runway-local-root.crt /usr/local/share/ca-certificates/runway-local-root.crt
sudo update-ca-certificates
```

On iPhone, securely transfer the `.crt`, install its profile in Settings, then enable it under Settings → General → About → Certificate Trust Settings. Follow your OS's current prompts. Do not bypass certificate warnings. If your identity provider requires callback-domain verification, register this exact hostname there too.

Open **`https://runway.home.arpa/#family`** and sign in. The exact general format is **`https://<RUNWAY_HOSTNAME>/#family`** (not `http://<server-ip>:8765`). Budget & Spending is `#spending`; Smart Card Planner is `#cardplanner`.

## Stop, restart and update

```bash
# Stop without deleting persisted data:
docker compose stop
# Start again:
docker compose up -d
# Update this feature branch; inspect changes before rebuilding:
git -C ../.. pull --ff-only origin feat/family-finance-hub-home
docker compose up -d --build
docker compose ps
```

Take a backup before updating. `docker compose down` also retains named volumes, but **never use `down -v` for a household installation**: that removes the data volumes. A plain `docker compose pull` cannot update this locally built application; rebuild after pulling the Git branch.

## Back up and restore

Runway Settings → Data → Download backup provides a portable application backup; restore it through the same screen after inspecting it. Keep your encryption key separately. For a complete filesystem backup including the database, key material and Caddy CA, stop writes first:

```bash
umask 077
mkdir -p backups
docker compose stop
# A stopped service can still have files copied out with compose cp.
docker compose cp runway:/data/. backups/runway-data
docker compose cp https:/data/. backups/caddy-data
cp .env backups/runway.env
tar -czf "backups/runway-$(date +%F).tar.gz" -C backups runway-data caddy-data runway.env
rm -rf backups/runway-data backups/caddy-data backups/runway.env
docker compose up -d
```

Move that archive to encrypted storage outside the server. It contains private financial records, the OIDC client secret, encryption key and Caddy private CA: **never commit or share it**. `backups/` and certificate files are Git-ignored. If the backup command fails, fix it before removing the temporary copies or claiming a backup exists.

To restore a filesystem archive to an empty/new installation, recover the original `.env`, set DNS to the replacement server, create stopped containers/volumes, then copy the saved data back:

```bash
umask 077
mkdir restore
# Replace this filename with the actual private backup archive:
tar -xzf /secure/location/runway-YYYY-MM-DD.tar.gz -C restore
cp restore/runway.env .env
chmod 600 .env
docker compose create
docker compose cp restore/runway-data/. runway:/data
docker compose cp restore/caddy-data/. https:/data
# Restore the Runway uid/gid used by the image (1000:1000), without starting the web app:
docker compose run --rm --no-deps --user root runway chown -R 1000:1000 /data
docker compose up -d
docker compose ps
```

Use only archives you trust, inspect them in a private directory, and retain the archive until you have checked account balances and schedules after restore. Reuse the original Caddy CA, or distribute the replacement public root if it was lost. There is no automatic bank synchronization after restore.

## Troubleshooting

- Configuration refuses to start: required `.env` values are intentionally mandatory. No authentication bypass is provided.
- Browser cannot connect: confirm LAN IP binding, DNS, firewall allowance for LAN TCP 443, and that another service does not occupy that port.
- Certificate warning: install the public local CA on that device; do not disable TLS verification.
- Sign-in callback error: compare issuer and exact redirect URI, client secret, verified email and allowed-email list.
- No data: a new installation is intentionally empty. Add manual accounts/import statements; do not use synthetic demo data as household history.
- A planned purchase is not an actual transaction. Enter/import actual purchases and match schedules in Recurring; reconcile against account statements.
