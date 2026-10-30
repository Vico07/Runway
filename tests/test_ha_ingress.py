"""Supervisor boundary, prefix safety, iframe policy and scoped read-only sensor authorization."""
import json
import os
from unittest import mock

from runway.server import ingress
from runway.server.handler import Handler, SensorHandler, Server
from tests.shared import LedgerCase, fetch, serve

BASE = "/api/hassio_ingress/example_session"
TOKEN = "synthetic-test-token-not-a-real-secret-0123456789"


class GatewayHandler(Handler):
    def _route(self, method):
        self.client_address = (ingress.GATEWAY, self.client_address[1])
        return super()._route(method)


def gateway_server(address, _handler):
    return Server(address, GatewayHandler)


def sensor_server(address, _handler):
    return Server(address, SensorHandler)


class IngressTests(LedgerCase):
    def setUp(self):
        super().setUp()
        self.acct("chk", "checking", 5000, provider="manual")
        self.conn.commit()
        patch = mock.patch.dict(os.environ, {"RUNWAY_HA_INGRESS": "1", "RUNWAY_HA_SENSOR_TOKEN": TOKEN})
        patch.start(); self.addCleanup(patch.stop)

    def test_gateway_and_valid_prefix_are_both_required(self):
        self.assertIsNone(ingress.base_path("127.0.0.1", {"X-Ingress-Path": BASE}))
        for path in ("//evil.example", "/api/hassio_ingress/../other", '/api/hassio_ingress/a\"x', "/api/hassio_ingress/a?x"):
            self.assertIsNone(ingress.base_path(ingress.GATEWAY, {"X-Ingress-Path": path}))
        self.assertEqual(ingress.base_path(ingress.GATEWAY, {"X-Ingress-Path": BASE}), BASE)
        base = serve(self)
        self.assertEqual(fetch(base, "GET", "/api/accounts", headers={"X-Ingress-Path": BASE})[0], 403)

    def test_gateway_can_edit_manual_data_but_cross_site_and_bank_requests_are_refused(self):
        base = serve(self, gateway_server)
        headers = {"X-Ingress-Path": BASE, "Content-Type": "application/json", "X-Runway": "1"}
        body = json.dumps({"name": "Synthetic checking", "kind": "checking", "balance": 100, "balance_date": "2026-01-01"}).encode()
        status, response_headers, _ = fetch(base, "POST", "/api/family/accounts", body, headers)
        self.assertEqual(status, 200)
        self.assertEqual(response_headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", response_headers["Content-Security-Policy"])
        self.assertEqual(fetch(base, "POST", "/api/family/accounts", body, {**headers, "Origin": "https://foreign.example"})[0], 403)
        self.assertEqual(fetch(base, "POST", "/api/sync", b"{}", headers)[0], 403)
        self.assertEqual(fetch(base, "POST", "/api/plaid/link-token", b"{}", headers)[0], 403)
        self.assertEqual(fetch(base, "GET", "/api/accounts")[0], 403)

    def test_ingress_page_and_resource_urls_stay_below_the_session_prefix(self):
        self.assertEqual(ingress.resource_paths({"logo": "/api/merchants/demo/logo", "amount": 10, "site": "https://example.com"}, BASE),
                         {"logo": BASE + "/api/merchants/demo/logo", "amount": 10, "site": "https://example.com"})
        base = serve(self, gateway_server)
        status, _, body = fetch(base, "GET", "/", headers={"X-Ingress-Path": BASE})
        if status == 200:
            self.assertIn(b'name="runway-base-path"', body)
            self.assertIn((BASE + "/fonts/").encode(), body)
        else:
            self.assertEqual(status, 404)  # CI's Python-only job has no built web app; pure prefix tests still execute.

    def test_sensor_listener_cannot_write_or_read_unscoped_endpoints(self):
        base = serve(self, sensor_server)
        headers = {"Authorization": "Bearer " + TOKEN}
        self.assertEqual(fetch(base, "GET", "/api/ha/summary")[0], 401)
        self.assertEqual(fetch(base, "GET", "/api/ha/summary", headers={"Authorization": "Bearer wrong"})[0], 401)
        status, _, raw = fetch(base, "GET", "/api/ha/summary", headers=headers)
        self.assertEqual(status, 200)
        data = json.loads(raw)["data"]
        self.assertEqual(data["checking_balance"], 5000)
        self.assertFalse(data["verified"])
        self.assertNotIn("account_id", raw.decode())
        self.assertEqual(fetch(base, "GET", "/api/accounts", headers=headers)[0], 403)
        self.assertEqual(fetch(base, "POST", "/api/ha/summary", b"{}", headers)[0], 403)
        self.assertEqual(fetch(base, "GET", "/api/backup", headers=headers)[0], 403)
