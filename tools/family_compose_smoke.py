#!/usr/bin/env python3
"""Opt-in home Compose smoke using its own temporary project, synthetic settings and loopback TLS only."""
from __future__ import annotations

import http.client
from pathlib import Path
import secrets
import ssl
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"Compose smoke failed: {args[0]} {args[1]}")
    return p.stdout.strip()


def main():
    project = "family-compose-smoke-" + uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix=project) as folder:
        work = Path(folder)
        env = work / "synthetic.env"
        env.write_text("RUNWAY_HOSTNAME=runway-smoke.home.arpa\nRUNWAY_BIND_IP=127.0.0.1\nTZ=America/New_York\n"
                       "OIDC_ISSUER=https://identity.invalid\nOIDC_CLIENT_ID=synthetic\nOIDC_CLIENT_SECRET=synthetic-only\n"
                       "OIDC_ALLOWED_EMAILS=synthetic@example.invalid\nRUNWAY_SECRET_KEY=" + secrets.token_hex(32) + "\n")
        compose = ["docker", "compose", "--env-file", str(env), "-p", project, "-f", str(ROOT / "deploy/home/compose.yaml")]
        try:
            run(*compose, "config", "--quiet")
            run(*compose, "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")
            cert = work / "root.crt"
            for _ in range(30):
                try:
                    run(*compose, "cp", "https:/data/caddy/pki/authorities/local/root.crt", str(cert))
                    break
                except RuntimeError:
                    time.sleep(1)
            context = ssl.create_default_context(cafile=str(cert))

            def request(path):
                # Trust the generated public CA and verify the real certificate hostname, without changing host DNS.
                import socket
                sock = socket.create_connection(("127.0.0.1", 443), timeout=10)
                tls = context.wrap_socket(sock, server_hostname="runway-smoke.home.arpa")
                c = http.client.HTTPConnection("runway-smoke.home.arpa", 443)
                c.sock = tls
                c.request("GET", path)
                r = c.getresponse()
                body = r.read()
                result = (r.status, r.getheader("Location"), body)
                c.close()
                return result

            status, redirect, body = request("/")
            assert status == 302 and redirect.startswith("/auth/login"), (status, redirect, body[:250])
            assert request("/api/accounts")[0] == 401
            assert request("/healthz")[0] == 200
            app = run(*compose, "ps", "-q", "runway")
            assert run("docker", "inspect", "--format", "{{json .HostConfig.PortBindings}}", app) in ("{}", "null")
            run(*compose, "exec", "-T", "runway", "python", "-c",
                "from pathlib import Path; Path('/data/synthetic-persistence-check').write_text('synthetic fixture')")
            run(*compose, "restart", "runway")
            run(*compose, "exec", "-T", "runway", "python", "-c",
                "from pathlib import Path; assert Path('/data/synthetic-persistence-check').read_text()=='synthetic fixture'")
            run(*compose, "stop")
            backup = work / "backup"
            run(*compose, "cp", "runway:/data/.", str(backup))
            assert (backup / "runway.db").is_file()
            assert (backup / "synthetic-persistence-check").is_file()
            run(*compose, "cp", str(backup / "synthetic-persistence-check"), "runway:/data/synthetic-restored-check")
            run(*compose, "up", "-d", "--wait")
            run(*compose, "exec", "-T", "runway", "python", "-c",
                "from pathlib import Path; assert Path('/data/synthetic-restored-check').read_text()=='synthetic fixture'")
            assert request("/api/accounts")[0] == 401
            print("PASS: home Compose config/start, verified local TLS, OIDC auth gate, no app host port, restart persistence, stopped-volume backup/copy restore. Live identity-provider login requires household configuration.")
        finally:
            # Only this disposable project, never a user's existing Compose volumes.
            subprocess.run([*compose, "down", "-v"], capture_output=True)


if __name__ == "__main__":
    main()
