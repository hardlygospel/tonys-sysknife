#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 Tony (hardlygospel) — https://github.com/hardlygospel
"""
Tony's Sysadmin Swiss Army Knife
Morning checklist · AD · Azure · System Health · Network · Cleanup · SSH
Entry point: bootstrap deps, load config, dispatch to GUI (Windows) or TUI.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

# ── constants ─────────────────────────────────────────────────────────────────
APP_NAME    = "Tony's Sysadmin Swiss Army Knife"
APP_SLUG    = "sysknife"
APP_VERSION = "1.0.0"
CONFIG_DIR  = Path.home() / ".sysknife"
CONFIG_FILE = CONFIG_DIR / "config.json"

IS_WINDOWS  = sys.platform == "win32"
IS_LINUX    = sys.platform.startswith("linux")
IS_MAC      = sys.platform == "darwin"

_DEFAULT_CFG: dict = {
    "ad": {"server": "", "base_dn": "", "user": "", "password_enc": ""},
    "azure": {"tenant_id": "", "client_id": "", "client_secret_enc": ""},
    "ssh_hosts": [],
    "morning": {
        "ping_hosts":       [],
        "cert_paths":       [],
        "backup_paths":     [],
        "disk_warn_pct":    85,
        "mem_warn_pct":     90,
        "cert_warn_days":   30,
        "checks":           ["disk","memory","cpu","swap","services",
                             "updates","ping","certs","backups","ports","uptime"],
    },
    "theme": "dark",
}


# ── auto-install ──────────────────────────────────────────────────────────────

def _pip_install(packages: list[str]) -> None:
    import subprocess
    for extra in ([], ["--user"], ["--user", "--break-system-packages"]):
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet"] + extra + packages,
                stderr=subprocess.DEVNULL,
            )
            return
        except subprocess.CalledProcessError:
            continue
    print(f"[!] Could not auto-install: {' '.join(packages)}")
    sys.exit(1)


def _ensure_deps() -> None:
    missing = []
    for pkg, mod in [
        ("rich>=13.7.0",          "rich"),
        ("prompt_toolkit>=3.0.0", "prompt_toolkit"),
        ("psutil>=5.9.0",         "psutil"),
        ("requests>=2.31.0",      "requests"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Installing: {', '.join(missing)} …")
        _pip_install(missing)


# ── config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            stored = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # deep-merge defaults so new keys appear on upgrade
            cfg = json.loads(json.dumps(_DEFAULT_CFG))
            for k, v in stored.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    cfg = json.loads(json.dumps(_DEFAULT_CFG))
    save_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def cfg_encode(plain: str) -> str:
    """Very light obfuscation — not real encryption. Keeps plain text off screen."""
    return base64.b64encode(plain.encode()).decode()


def cfg_decode(enc: str) -> str:
    try:
        return base64.b64decode(enc.encode()).decode()
    except Exception:
        return enc


def cfg_get_ad_password(cfg: dict) -> str:
    return cfg_decode(cfg["ad"].get("password_enc", ""))


def cfg_get_az_secret(cfg: dict) -> str:
    return cfg_decode(cfg["azure"].get("client_secret_enc", ""))


def ad_configured(cfg: dict) -> bool:
    return bool(cfg["ad"].get("server") and cfg["ad"].get("user"))


def az_configured(cfg: dict) -> bool:
    return bool(cfg["azure"].get("tenant_id") and cfg["azure"].get("client_id"))


# ── platform detection ────────────────────────────────────────────────────────

def _wants_gui(args: argparse.Namespace) -> bool:
    """True when on Windows and --tui not specified."""
    return IS_WINDOWS and not getattr(args, "tui", False)


# ── arg parser ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=APP_SLUG,
        description=f"{APP_NAME} v{APP_VERSION}",
    )
    p.add_argument("--tui",     action="store_true", help="Force TUI even on Windows")
    p.add_argument("--module",  metavar="NAME",      help="Open module directly (morning/ad/azure/health/network/cleanup/ssh/settings)")
    p.add_argument("--check",   action="store_true", help="Run morning checklist non-interactively, exit 0=all-ok 1=issues")
    p.add_argument("--version", action="version",    version=f"{APP_NAME} v{APP_VERSION}")
    return p.parse_args()


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    _ensure_deps()
    args = parse_args()
    cfg  = load_config()

    if _wants_gui(args):
        try:
            from gui import run_gui
            run_gui(cfg, args)
        except Exception as e:
            print(f"[!] GUI failed ({e}), falling back to TUI.")
            from tui import run_tui
            run_tui(cfg, args)
    else:
        from tui import run_tui
        run_tui(cfg, args)


if __name__ == "__main__":
    main()
