# Family Finance Hub validation

All fixtures used by automated tests and screenshots are synthetic. No bank synchronization, real issuer login or household records are required. Start household deployments with an empty persistent volume; never restore the demo fixture into it.

## Application checks

Run the existing repository checks, including Python/SQLite and frontend suites, generated contracts/maps, import boundaries, Semgrep and the documentation build:

```bash
make check
# On a disposable PostgreSQL database that you own:
DATABASE_URL=postgresql://runway:runway@127.0.0.1:5432/runway make test-pg
make screenshots
```

New tests cover editable manual balances, transient scenarios, daily/month comparisons, card strategies, statement cycles, rewards valuations/caps, interest/promotion uncertainty, credit/reserve safeguards, explicit schedule save/cancel, consumption vs repayment/principal, split transactions, CSV deduplication/errors, account coverage and the Ingress authentication/CSRF boundary.

The browser verifier supplies desktop/iPhone screenshots and checks accessibility. The viewport no longer disables pinch zoom. `screenshots/` is produced only by the official verifier; ignored `artifacts/` holds diagnostic and simulated-Ingress evidence.

## Container and interactive deployment checks

Build the ordinary image from the repository root:

```bash
docker build --build-arg VERSION=family-local -t runway-family:local .
python tools/family_compose_smoke.py
```

Run the smoke tool in the repository's Python environment (`poetry run python ...` when developing with Poetry). It uses only a unique disposable Compose project and loopback port 443, validates actual local-CA certificates and unauthenticated API refusal, and tests persistent files plus stopped-volume backup/copy restore. It deletes **its own** fixture volumes at the end; never substitute a household project name. A live OIDC provider sign-in remains an installation check.

The native add-on Dockerfile takes `RUNWAY_SOURCE` (a pinned public Git source by default). For an offline/local source build, stage the committed application files under a temporary `source/` directory beside a copy of the add-on Dockerfile, then:

```bash
docker build --platform linux/amd64 --build-arg RUNWAY_SOURCE=source -t runway-family-addon:test /path/to/temporary/build-context
poetry run python tools/family_deployment_smoke.py
```

The source directory must contain `run.py`, `alembic.ini`, `pyproject.toml`, `poetry.lock`, `runway/`, `frontend/` and `extension/`, excluding `.env`, data, credentials, caches and node_modules. The same multi-stage Dockerfile builds the same application; no alternate frontend is used.

The add-on smoke creates its own 172.30.32.0/24 Docker network and temporary data volume. It verifies the documented gateway peer/prefix through a **simulated** Ingress iframe, editing accounts/payment modes, card comparison/schedule saves, CSV import, desktop/iPhone layouts, spoofed-peer refusal, scoped sensor access, restart persistence, unprivileged application uid and native portable backup/restore. The gateway is a synthetic relay and does not implement Home Assistant authentication.

Run Docker network smoke tests **before**, not concurrently with, `make verify`/`make screenshots`: Docker network interface changes can interrupt Chromium requests. Do not rebuild frontend output while browser verification is using it.

## Required installation checks

No actual Home Assistant OS/Supervisor device or household OIDC provider was available in the development environment. On the amd64 Dell Tiny PC, install the custom repository, confirm an unauthorized HA user cannot open the admin panel, open the complete app from the sidebar, edit a harmless manual entry on desktop/iPhone, then perform a backup/restore drill. These checks are required before relying on it for household decisions. See the [add-on guide](../addons/family_finance_hub/DOCS.md) and [Linux guide](home/README.md).
