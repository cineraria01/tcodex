#!/usr/bin/env python3
"""Read-only TeamCodex quota HUD. Rendering adapted from teamclaude-statusline (MIT)."""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def read_status(config_path):
    config = json.loads(config_path.read_text())
    proxy = config.get("proxy") or {}
    port = proxy.get("port", 3457)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid local proxy port")
    headers = {"x-teamcodex-status-identity": "1"}
    if proxy.get("apiKey"):
        headers["x-api-key"] = proxy["apiKey"]
    # Never send the local proxy key through an environment proxy or redirect.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(f"http://127.0.0.1:{port}/teamclaude/status", headers=headers)
    with opener.open(request, timeout=2) as response:
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("status response too large")
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("accounts"), list):
        raise ValueError("invalid status response")
    if any(not isinstance(account, dict) for account in data["accounts"]):
        raise ValueError("invalid account response")
    return data


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return value


def timestamp(value):
    if number(value) is not None:
        return value / 1000
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError):
            pass
    return None


def remaining(value, now):
    reset = timestamp(value)
    if reset is None:
        return ""
    seconds = reset - now
    if seconds <= 0:
        return "now"
    minutes = int(seconds // 60)
    if not minutes:
        return "<1m"
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d{hours}h"
    return f"{hours}h{minutes}m" if hours else f"{minutes}m"


def clean(value, width):
    # Fixed ASCII cells also prevent terminal-control injection in account names.
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in str(value or "-"))[:width]


def paint(text, color, enabled):
    return f"\033[{color}m{text}\033[0m" if enabled else text


def bar(value, reset, now, color=False, width=13):
    ratio = number(value)
    if ratio is None:
        text = "-".center(width)
        return paint(text, "100;37", color) if color else f"[{text}]"
    ratio = min(1, max(0, ratio))
    text = f"{ratio * 100:.0f}% {remaining(reset, now)}".strip()[:width].center(width)
    if not color:
        return f"[{text}]"
    filled = round(ratio * width)
    bg = 42 if ratio < 0.7 else 43 if ratio < 0.9 else 41
    return paint(text[:filled], f"{bg};97", True) + paint(text[filled:], "100;37", True)


def pool(accounts, key):
    values, resets = [], []
    for account in accounts:
        quota = account.get("quota") or {}
        value = number(quota.get(key))
        if value is not None:
            values.append(min(1, max(0, value)))
            reset = timestamp(quota.get(key + "Reset"))
            if reset is not None:
                resets.append(reset * 1000)
    return (sum(values) / len(values) if values else None,
            min(resets) if resets else None)


def account_state(account, now):
    if account.get("enabled") is False:
        return "off"
    if account.get("status") == "error":
        return "error"
    reset = timestamp(account.get("rateLimitedUntil"))
    if reset is not None and reset > now:
        return "wait"
    if number(account.get("inflight")) and account["inflight"] > 0:
        return "busy"
    if account.get("usable") is False:
        return "limit"
    return "ready"


def session_log(pane):
    """Find this pane's CLI log, excluding subagents and other terminal windows."""
    pid = int(subprocess.check_output(
        ["tmux", "-L", "teamcodex-hud", "display-message", "-p", "-t", pane, "#{pane_pid}"],
        text=True, timeout=2).strip())
    processes = subprocess.check_output(["ps", "-axo", "pid=,ppid=,comm="], text=True, timeout=2)
    entries = [line.split(None, 2) for line in processes.splitlines() if line.strip()]
    descendants = {pid}
    while True:
        children = {int(p) for p, parent, _ in entries if int(parent) in descendants}
        if children <= descendants:
            break
        descendants |= children
    codex = [p for p, _, command in entries if int(p) in descendants and Path(command).name == "codex"]
    if len(codex) != 1:
        return None
    opened = subprocess.run(["lsof", "-n", "-P", "-p", codex[0], "-Fn"],
                            capture_output=True, text=True, timeout=2)
    candidates = set()
    for line in opened.stdout.splitlines():
        if line.startswith("n/") and Path(line[1:]).name.startswith("rollout-") and line.endswith(".jsonl"):
            path = Path(line[1:])
            with path.open() as log:
                meta = json.loads(log.readline())
            if meta.get("type") == "session_meta" and meta.get("payload", {}).get("source") == "cli":
                candidates.add(path)
    # Never guess by directory or modification time when multiple sessions are open.
    return candidates.pop() if len(candidates) == 1 else None


def last_usage(path):
    """Read backwards in blocks; ignore an unfinished final JSONL record."""
    with path.open("rb") as log:
        position = log.seek(0, 2)
        pending = b""
        while position:
            size = min(position, 65536)
            position -= size
            log.seek(position)
            lines = (log.read(size) + pending).split(b"\n")
            pending = lines.pop(0) if position else b""
            for line in reversed(lines):
                if b'"token_count"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                payload = event.get("payload") or {}
                if event.get("type") == "event_msg" and payload.get("type") == "token_count" and payload.get("info"):
                    return payload["info"].get("last_token_usage")
    return None


def cache_row(usage):
    if not isinstance(usage, dict):
        return "Cache last: waiting for usage"
    total, cached = number(usage.get("input_tokens")), number(usage.get("cached_input_tokens"))
    if total is None or cached is None or total <= 0 or not 0 <= cached <= total:
        return "Cache last: unavailable"
    return (f"Cache last: {cached / total:.1%} | {cached:,.0f}/{total:,.0f} in"
            f" | new {total - cached:,.0f}")


def render(data, now=None, color=False, width=100):
    now = time.time() if now is None else now
    accounts = data["accounts"]
    threshold = number(data.get("switchThreshold"))
    threshold_label = f"{threshold * 100:.0f}%" if threshold is not None else "-"
    rows = [paint(f"TeamCodex | {len(accounts)} accounts | switch {threshold_label} | > selected, * busy", "1;36", color)]
    if not accounts:
        return rows + ["No accounts. Run: teamcodex login --name codex-1"]
    eligible = [a for a in accounts if a.get("enabled") is not False and a.get("status") != "error"]
    name_width = 10 if width < 85 else 15
    bar_width = 10 if width < 85 else 13

    def row(marker, label, plan, state, five, week, accent="36"):
        prefix = f"{marker} {clean(label, name_width):<{name_width}} {clean(plan, 8):<8} {state:<5}"
        return (paint(prefix, accent, color) + " 5h " + bar(*five, now, color, bar_width)
                + " 7d " + bar(*week, now, color, bar_width))

    # Arithmetic mean of measured enabled accounts, not pooled token capacity.
    if len(accounts) > 1:
        rows.append(row(" ", "FLEET", f"x{len(eligible)}", "avg",
                        pool(eligible, "unified5h"), pool(eligible, "unified7d"), "1"))
    indexed = list(enumerate(accounts, 1))
    indexed.sort(key=lambda item: timestamp((item[1].get("quota") or {}).get("unified7dReset")) or float("inf"))
    for index, account in indexed:
        quota = account.get("quota") or {}
        current_id = data.get("currentAccountUuid")
        selected = (account.get("accountUuid") == current_id if current_id
                    else bool(data.get("currentAccount")) and account.get("name") == data["currentAccount"])
        state = account_state(account, now)
        marker = "*" if state == "busy" else ">" if selected else " "
        name = account.get("name") or f"account-{index}"
        rows.append(row(marker, f"{index}.{name}", account.get("planType"), state,
                        (quota.get("unified5h"), quota.get("unified5hReset")),
                        (quota.get("unified7d"), quota.get("unified7dReset")),
                        "31" if state == "error" else ("36", "32", "33", "35")[index % 4]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path.home() / ".config/teamcodex.json")
    parser.add_argument("--watch", action="store_true", help="refresh every two seconds")
    parser.add_argument("--plain", action="store_true", help="disable ANSI colors")
    parser.add_argument("--codex-pane", help="tmux pane whose latest request cache usage is shown")
    args = parser.parse_args()
    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ and not args.plain
    watching = args.watch and sys.stdout.isatty()
    try:
        while True:
            failed = False
            try:
                rows = render(read_status(args.config), color=color, width=shutil.get_terminal_size().columns)
            except FileNotFoundError:
                rows = ["TeamCodex: config missing. Run: teamcodex login --name codex-1"]
                failed = True
            except Exception:
                # Keep account credentials and HTTP exception details out of the display.
                rows = ["TeamCodex: proxy unavailable or invalid status. Run: teamcodex server"]
                failed = True
            if args.codex_pane:
                try:
                    path = session_log(args.codex_pane)
                    cache = cache_row(last_usage(path)) if path else "Cache last: session unavailable"
                except (OSError, ValueError, subprocess.SubprocessError):
                    cache = "Cache last: unavailable"
                rows.append(cache[:shutil.get_terminal_size().columns])
            if watching:
                sys.stdout.write("\033[H\033[J" + "\n".join(rows))
                sys.stdout.flush()
            else:
                print("\n".join(rows), flush=True)
            if not watching:
                return 1 if failed else 0
            time.sleep(2)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
