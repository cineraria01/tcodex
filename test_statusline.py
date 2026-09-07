"""Small offline check: python3 test_statusline.py. No account login or inference."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError

from statusline import account_state, bar, clean, pool, read_status, render


def check():
    now = 1_800_000_000
    accounts = [
        {"name": "one", "accountUuid": "a", "enabled": True, "planType": "pro", "usable": True,
         "quota": {"unified7d": 0.8, "unified7dReset": (now + 3600) * 1000}},
        {"name": "two", "accountUuid": "b", "enabled": True, "planType": "plus", "usable": True,
         "quota": {"unified7d": 0, "unified7dReset": (now + 7200) * 1000}},
        {"name": "off", "enabled": False, "quota": {"unified7d": 1}},
    ]
    data = {"accounts": accounts, "currentAccountUuid": "a", "switchThreshold": 0.98}
    output = "\n".join(render(data, now=now))
    assert "40%" in output and "> 1.one" in output and "off" in output
    assert "-" in bar(None, None, now) and "0%" in bar(0, None, now)
    assert "nan" not in bar(float("nan"), None, now)
    assert pool([accounts[0], {"quota": {}}], "unified7d")[0] == 0.8
    changed = copy.deepcopy(data)
    changed["currentAccountUuid"] = "b"
    changed["accounts"][0]["enabled"] = False
    assert "> 2.two" in "\n".join(render(changed, now=now))
    assert account_state({"inflight": 1}, now) == "busy"
    assert account_state({"rateLimitedUntil": (now - 1) * 1000}, now) == "ready"
    assert "\033" not in clean("evil\033[2J\nname", 30)
    assert all(len(line) <= 80 for line in render(data, now=now, width=80))

    class Handler(BaseHTTPRequestHandler):
        redirect = False
        def do_GET(self):
            assert self.headers.get("x-api-key") == "local-test-key"
            assert self.headers.get("x-teamcodex-status-identity") == "1"
            if self.redirect:
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/do-not-follow")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
        def log_message(self, *args):
            pass

    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary) / "config.json"
        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            config.write_text(json.dumps({"proxy": {"port": server.server_port, "apiKey": "local-test-key"}}))
            try:
                assert read_status(config) == data
                Handler.redirect = True
                try:
                    read_status(config)
                except HTTPError as error:
                    assert error.code == 302
                else:
                    raise AssertionError("redirect must be rejected")
                config.write_text('{"proxy":{"port":"3457/unsafe"}}')
                try:
                    read_status(config)
                    raise AssertionError("port must be validated")
                except ValueError:
                    pass
            finally:
                server.shutdown()
                worker.join()
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("statusline.py")),
                                 "--config", str(Path(temporary) / "missing"), "--plain"], capture_output=True, text=True)
        assert result.returncode == 1 and "config missing" in result.stdout
        prefix = Path(temporary) / "install"
        env = {**os.environ, "TEAMCODEX_HUD_PREFIX": str(prefix)}
        installer = Path(__file__).with_name("install.py")
        for _ in range(2):
            subprocess.run([sys.executable, str(installer)], env=env, check=True, capture_output=True)
        link = prefix / "bin/tcodex"
        assert link.is_symlink()
        link.unlink()
        link.write_text("user-owned command")
        result = subprocess.run([sys.executable, str(installer)], env=env, capture_output=True)
        assert result.returncode != 0 and link.read_text() == "user-owned command"
    print("PASS: rendering, account switch, missing quota, auth headers, local-only HTTP, offline state")


if __name__ == "__main__":
    check()
