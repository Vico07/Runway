#!/usr/bin/env python3
"""Opt-in destructive-to-its-own-fixtures Docker smoke: never run against household Compose projects or data.

Run after building runway-family:local and runway-family-addon:test. Creates unique temporary containers, a private
network and a named data volume; cleans up only those objects. Does not install or emulate an actual HA Supervisor.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def command(*args, **kw):
    result = subprocess.run(args, text=True, capture_output=True, **kw)
    if result.returncode:
        # This tool runs only its own synthetic fixture; keep diagnostic output in ignored artifacts.
        diagnostic = ROOT / "artifacts/family-deployment-error.txt"
        diagnostic.parent.mkdir(exist_ok=True)
        diagnostic.write_text(result.stdout + "\n" + result.stderr)
        raise RuntimeError(f"Deployment smoke command failed: {args[0]} {args[1] if len(args)>1 else ''}")
    return result.stdout.strip()


def main():
    suffix = uuid.uuid4().hex[:8]
    app, gateway, network, volume = [f"family-smoke-{name}-{suffix}" for name in ("app", "gateway", "net", "data")]
    token = "synthetic-smoke-token-not-a-household-secret-" + suffix
    with tempfile.TemporaryDirectory(prefix="runway-deployment-") as folder:
        work = Path(folder)
        # A minimal trusted Ingress relay for tests, not a replacement for HA authentication.
        proxy = work / "gateway.py"
        proxy.write_text('''from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import http.client
BASE="/api/hassio_ingress/synthetic_session"
class H(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self): self.route()
 def do_POST(self): self.route()
 def do_DELETE(self): self.route()
 def route(self):
  if self.path=="/":
   body=('<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}</style><title>Synthetic HA Ingress fixture</title><iframe id="ingress" title="Family Finance Hub" src="'+BASE+'/#family" style="border:0;width:100%;height:100vh"></iframe>').encode()
   self.send_response(200);self.send_header("X-Runway-Test-Gateway","1");self.send_header("Content-Type","text/html");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body);return
  if not self.path.startswith(BASE+"/"): self.send_error(403);return
  body=self.rfile.read(int(self.headers.get("Content-Length",0)))
  headers={k:v for k,v in self.headers.items() if k.lower() not in ("connection","content-length","x-ingress-path")}
  headers["X-Ingress-Path"]=BASE
  c=http.client.HTTPConnection("familyapp",8765,timeout=60);c.request(self.command,self.path[len(BASE):],body=body,headers=headers);r=c.getresponse();data=r.read()
  self.send_response(r.status)
  for k,v in r.getheaders():
   if k.lower() not in ("connection","transfer-encoding","content-length"):self.send_header(k,v)
  self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data);c.close()
ThreadingHTTPServer(("0.0.0.0",8080),H).serve_forever()
''')
        try:
            command("docker", "network", "create", "--subnet", "172.30.32.0/24", network)
            command("docker", "volume", "create", volume)
            options = json.dumps({"timezone": "America/New_York", "sensor_token": token})
            command("docker", "run", "--rm", "-v", f"{volume}:/data", "--entrypoint", "python", "runway-family-addon:test", "-c",
                    "from pathlib import Path; Path('/data/options.json').write_text(" + repr(options) + ")")
            command("docker", "run", "-d", "--name", app, "--network", network, "--network-alias", "familyapp", "--ip", "172.30.32.3", "-v", f"{volume}:/data",
                    "--health-interval=2s", "--health-start-period=1s", "runway-family-addon:test")
            for _ in range(45):
                if command("docker", "inspect", "--format", "{{.State.Health.Status}}", app) == "healthy":
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Add-on did not become healthy")
            command("docker", "exec", app, "python", "-c", "from pathlib import Path; assert 'Uid:\\t1000' in Path('/proc/1/status').read_text()")
            command("docker", "run", "-d", "--name", gateway, "--network", network, "--ip", "172.30.32.2", "-p", "127.0.0.1:18888:8080",
                    "-v", f"{proxy}:/gateway.py:ro", "--entrypoint", "python", "runway-family-addon:test", "/gateway.py")
            command("node", str(ROOT / "frontend/verify/family-ingress-smoke.mjs"), "http://127.0.0.1:18888", cwd=ROOT)
            print("PASS: full UI editing and planning in a simulated Ingress iframe, desktop and iPhone")
            # No auth header from an unrelated peer may reach the Ingress application.
            check = "import urllib.request,urllib.error;\ntry: urllib.request.build_opener(urllib.request.ProxyHandler({})).open(urllib.request.Request('http://familyapp:8765/api/accounts',headers={'X-Ingress-Path':'/api/hassio_ingress/synthetic_session'})); raise AssertionError('direct access allowed')\nexcept urllib.error.HTTPError as e: assert e.code==403"
            command("docker", "run", "--rm", "--network", network, "--entrypoint", "python", "runway-family-addon:test", "-c", check)
            sensor = "import json,urllib.request,urllib.error; h={'Authorization':'Bearer '+" + repr(token) + "}; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open(urllib.request.Request('http://familyapp:8766/api/ha/summary',headers=h)); d=json.load(r)['data']; assert d['verified'] is False; assert d['checking_balance'] is not None"
            command("docker", "exec", gateway, "python", "-c", sensor)
            print("PASS: spoofed Ingress refused; separate read-only sensor API authorized")
            count = "from runway.storage import db; from runway.storage.models import Account; from sqlalchemy import select,func; db.init();\nwith db.session() as c: assert c.execute(select(func.count()).select_from(Account)).scalar() >= 2"
            command("docker", "restart", app)
            for _ in range(45):
                if command("docker", "inspect", "--format", "{{.State.Health.Status}}", app) == "healthy":
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Add-on did not recover after restart/restore")
            command("docker", "exec", app, "python", "-c", count)
            command("node", str(ROOT / "frontend/verify/family-ingress-smoke.mjs"), "http://127.0.0.1:18888", "--read-only", cwd=ROOT)
            print("PASS: persistent household fixture and UI survived container restart")
            # Native portable backup and restore, while the app is stopped for restore.
            command("docker", "exec", "--user", "1000:1000", app, "python", "run.py", "backup", "/data/synthetic-backup.json.gz")
            command("docker", "stop", app)
            command("docker", "run", "--rm", "--user", "1000:1000", "-v", f"{volume}:/data", "--entrypoint", "python", "runway-family-addon:test",
                    "run.py", "restore", "/data/synthetic-backup.json.gz", "--yes")
            command("docker", "start", app)
            for _ in range(45):
                if command("docker", "inspect", "--format", "{{.State.Health.Status}}", app) == "healthy":
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Add-on did not recover after restart/restore")
            command("docker", "exec", app, "python", "-c", count)
            print("PASS: stopped-app backup/restore round-trip retained the persisted account fixture")
            out = ROOT / "artifacts" / "family-deployment-smoke.txt"
            out.parent.mkdir(exist_ok=True)
            out.write_text("PASS: amd64 add-on runtime, trusted Ingress simulation, interactive desktop/iPhone UI, scoped sensors, restart persistence and native backup/restore. Actual HA OS device not tested.\n")
        finally:
            for name in (gateway, app):
                subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            subprocess.run(["docker", "volume", "rm", volume], capture_output=True)
            subprocess.run(["docker", "network", "rm", network], capture_output=True)


if __name__ == "__main__":
    main()
