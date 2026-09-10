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

from statusline import account_state, bar, cache_row, clean, last_usage, pool, read_status, render, session_log
from unittest.mock import patch


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
    assert account_state({"capacityCooling": {"gpt-6-astra": (now + 300) * 1000}}, now) == "cool"
    assert account_state({"capacityCooling": {"gpt-6-astra": (now - 1) * 1000}}, now) == "ready"
    assert account_state({"capacityRecovered": {"gpt-6-astra": (now - 60) * 1000}}, now) == "back"
    assert account_state({"capacityRecovered": {"gpt-6-astra": (now - 3600) * 1000}}, now) == "ready"
    assert account_state({"inflight": 1, "capacityCooling": {"m": (now + 300) * 1000}}, now) == "busy"
    cooling = copy.deepcopy(data)
    cooling["accounts"][1]["capacityCooling"] = {"gpt-6-astra": (now + 300) * 1000}
    assert "cool " in "\n".join(render(cooling, now=now))
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
        log = Path(temporary) / "rollout-test.jsonl"
        usage = {"input_tokens": 150566, "cached_input_tokens": 148864}
        record = json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": usage}}})
        log.write_text(json.dumps({"type": "session_meta", "payload": {"source": "cli"}}) + "\n" + record + "\n")
        assert last_usage(log) == usage
        assert cache_row(usage) == "Cache last: 98.9% | 148,864/150,566 in | new 1,702"
        with log.open("a") as stream:
            stream.write(json.dumps({"padding": "x" * 70000}) + '\n{"type":"event_msg","payload":{"type":"token_count"')
        assert last_usage(log) == usage
        assert "0.0%" in cache_row({"input_tokens": 100, "cached_input_tokens": 0})
        assert "unavailable" in cache_row({"input_tokens": 0, "cached_input_tokens": 0})
        assert "unavailable" in cache_row({"input_tokens": 10})
        child_log = Path(temporary) / "rollout-child.jsonl"
        child_log.write_text(json.dumps({"type": "session_meta", "payload": {"source": {"subagent": {}}}}) + "\n")
        with patch("statusline.subprocess.check_output", side_effect=["10", "10 1 sh\n11 10 node\n12 11 /bin/codex\n99 1 /bin/codex"]), patch("statusline.subprocess.run") as opened:
            opened.return_value.stdout = f"n{child_log}\nn{log}\n"
            assert session_log("%0") == log
            assert opened.call_args.args[0][4] == "12"
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
            subprocess.run([sys.executable, str(installer), "--hud-only"], env=env, check=True, capture_output=True)
        link = prefix / "bin/tcodex"
        assert link.is_symlink()
        link.unlink()
        link.write_text("user-owned command")
        result = subprocess.run([sys.executable, str(installer), "--hud-only"], env=env, capture_output=True)
        assert result.returncode != 0 and link.read_text() == "user-owned command"
    print("PASS: rendering, account switch, missing quota, auth headers, local-only HTTP, offline state")


if __name__ == "__main__":
    check()
