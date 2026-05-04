#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 Tony (hardlygospel) — https://github.com/hardlygospel
"""
Tony's Sysadmin Swiss Army Knife — TUI (Linux / macOS / Windows --tui)
Rich + prompt_toolkit terminal interface.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ── prompt_toolkit ────────────────────────────────────────────────────────────
try:
    from prompt_toolkit import prompt as _pt_raw
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.styles import Style as PtStyle
    _HAS_PT = True
except ImportError:
    _HAS_PT = False

_PT_STYLE = None
if _HAS_PT:
    _PT_STYLE = PtStyle.from_dict({
        "prompt":      "bold #cba6f7",
        "completion-menu.completion":          "bg:#313244 #cdd6f4",
        "completion-menu.completion.current":  "bg:#cba6f7 #1e1e2e",
        "scrollbar.background": "bg:#45475a",
        "scrollbar.button":     "bg:#cba6f7",
    })

_HISTORIES: dict[str, InMemoryHistory] = {}


def _pt_ask(label: str, *, completer=None, default: str = "",
            placeholder: str = "", history_key: str = "default") -> str:
    if not _HAS_PT:
        return input(label)
    if history_key not in _HISTORIES:
        _HISTORIES[history_key] = InMemoryHistory()
    kw: dict[str, Any] = {
        "history":              _HISTORIES[history_key],
        "style":                _PT_STYLE,
        "complete_while_typing": True,
    }
    if completer:
        kw["completer"] = completer
    if placeholder:
        from prompt_toolkit.formatted_text import HTML
        kw["placeholder"] = HTML(f"<ansigray>{placeholder}</ansigray>")
    try:
        val = _pt_raw(label, **kw).strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        return default


# ── palette helpers ───────────────────────────────────────────────────────────

STATUS_COLORS = {
    "ok":   "bright_green",
    "warn": "yellow",
    "fail": "bright_red",
    "skip": "dim",
    "info": "cyan",
}

STATUS_ICONS = {
    "ok":   "✓",
    "warn": "⚠",
    "fail": "✗",
    "skip": "·",
    "info": "●",
}

MODULE_COLORS = {
    "morning":  "bright_cyan",
    "ad":       "bright_blue",
    "azure":    "blue",
    "health":   "bright_green",
    "network":  "bright_yellow",
    "cleanup":  "bright_magenta",
    "ssh":      "cyan",
    "settings": "bright_white",
}


def _status_text(status: str, detail: str = "") -> Text:
    color = STATUS_COLORS.get(status, "white")
    icon  = STATUS_ICONS.get(status, "?")
    t = Text()
    t.append(f" {icon} ", style=f"bold {color}")
    if detail:
        t.append(detail, style="white")
    return t


# ── banner ────────────────────────────────────────────────────────────────────

def print_banner() -> None:
    console.print()
    # Gradient title
    colors = ["bold bright_white", "bold bright_cyan", "bold cyan",
              "bold blue", "bold bright_blue"]
    title_chars = list("Tony's Sysadmin Swiss Army Knife")
    t = Text()
    for i, ch in enumerate(title_chars):
        t.append(ch, style=colors[min(i * len(colors) // len(title_chars), len(colors)-1)])
    console.print(Padding(Panel(
        t,
        subtitle="[dim]v1.0.0  ·  Morning Checklist · AD · Azure · Health · Network · Cleanup · SSH[/dim]",
        border_style="bright_cyan",
        box=box.DOUBLE_EDGE,
        padding=(0, 4),
    ), (0, 2)))
    console.print()


# ── help screen ───────────────────────────────────────────────────────────────

def print_help() -> None:
    console.print()
    console.print(Rule("[bold bright_cyan]Help — Tony's Sysadmin Swiss Army Knife[/bold bright_cyan]"))
    console.print()

    # Navigation table
    nav = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
                border_style="dim", expand=True)
    nav.add_column("Command / Key", style="bold yellow", no_wrap=True)
    nav.add_column("Action")
    rows = [
        ("1–8",        "Select module from main menu"),
        ("h  /  help", "Show this help screen"),
        ("q  /  quit", "Exit the tool"),
        ("Tab",        "Autocomplete current input (when available)"),
        ("↑ / ↓",      "Scroll through input history"),
        ("Ctrl+C",     "Cancel current operation / return to menu"),
        ("Enter",      "Confirm selection"),
    ]
    for cmd, action in rows:
        nav.add_row(cmd, action)

    # Modules table
    mods = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
                 border_style="dim", expand=True)
    mods.add_column("Module", style="bold", no_wrap=True)
    mods.add_column("What it does")
    mod_rows = [
        ("[bright_cyan]1  Morning Checklist[/]", "Disk, RAM, CPU, swap, services, updates, pings, TLS certs, backups, ports, uptime"),
        ("[bright_blue]2  Active Directory[/]",  "Search/unlock/reset/enable/disable AD accounts, list groups, add/remove members"),
        ("[blue]3  Azure AD[/]",                 "List/enable/disable Azure users, list groups, MFA status, list devices & apps"),
        ("[bright_green]4  System Health[/]",     "Live CPU%, memory, disk usage, top processes, network I/O, service status"),
        ("[bright_yellow]5  Network[/]",          "Ping hosts, port check, DNS lookup, traceroute, bandwidth snapshot"),
        ("[bright_magenta]6  Cleanup[/]",         "Temp files, log rotation, old cores, package cache, Trash/Recycle Bin"),
        ("[cyan]7  SSH Manager[/]",              "Saved SSH shortcuts — connect, add, remove, list hosts"),
        ("[bright_white]8  Settings[/]",          "Configure AD, Azure, SSH hosts, morning check thresholds, theme"),
    ]
    for mod, desc in mod_rows:
        mods.add_row(mod, desc)

    console.print(Columns([
        Panel(nav,  title="[bold]Navigation[/bold]", border_style="bright_cyan", expand=True),
        Panel(mods, title="[bold]Modules[/bold]",    border_style="bright_cyan", expand=True),
    ]))
    console.print()

    # Tips
    tips = Table(box=box.SIMPLE, show_header=False, border_style="dim", expand=True)
    tips.add_column("", style="yellow", no_wrap=True, width=3)
    tips.add_column("")
    tips_rows = [
        ("★", "Run [bold]--check[/bold] for a non-interactive morning checklist (CI-friendly, exit 1 on issues)"),
        ("★", "Run [bold]--module morning[/bold] to jump straight to the morning checklist"),
        ("★", "All passwords/secrets stored base64-encoded in [bold]~/.sysknife/config.json[/bold]"),
        ("★", "AD and Azure modules require optional deps: [bold]ldap3[/bold] / [bold]msal[/bold] (auto-prompted)"),
        ("★", "SSH module requires [bold]paramiko[/bold] — install with [bold]pip install paramiko[/bold]"),
    ]
    for icon, tip in tips_rows:
        tips.add_row(icon, tip)
    console.print(Panel(tips, title="[bold]Tips[/bold]", border_style="dim"))
    console.print()


# ── result rendering ──────────────────────────────────────────────────────────

def _render_results(results: list, title: str = "Results") -> None:
    """Render a list of CheckResult objects in a Rich table."""
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
              border_style="dim", expand=True, padding=(0, 1))
    t.add_column("Check",  style="bold", min_width=18)
    t.add_column("Status", no_wrap=True, min_width=6)
    t.add_column("Detail")

    for r in results:
        color = STATUS_COLORS.get(r.status, "white")
        icon  = STATUS_ICONS.get(r.status, "?")
        status_cell = Text(f"{icon} {r.status.upper()}", style=f"bold {color}")
        t.add_row(r.name, status_cell, r.detail)

    console.print(Panel(t, title=f"[bold]{title}[/bold]", border_style="bright_cyan"))


def _render_dict_table(data: dict, title: str, key_label: str = "Field",
                       val_label: str = "Value") -> None:
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
              border_style="dim", expand=True, padding=(0, 1))
    t.add_column(key_label, style="bold cyan", min_width=20)
    t.add_column(val_label)
    for k, v in data.items():
        t.add_row(str(k), str(v) if v is not None else "[dim]—[/dim]")
    console.print(Panel(t, title=f"[bold]{title}[/bold]", border_style="bright_cyan"))


def _render_list_table(rows: list[dict], title: str, columns: list[tuple[str, str]]) -> None:
    """columns: list of (key, label) tuples."""
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
              border_style="dim", expand=True, padding=(0, 1))
    for _, label in columns:
        t.add_column(label)
    for row in rows:
        t.add_row(*[str(row.get(k, "")) for k, _ in columns])
    console.print(Panel(t, title=f"[bold]{title}[/bold]", border_style="bright_cyan"))


# ── shared menu sub-prompt ────────────────────────────────────────────────────

def _sub_prompt(module_name: str, choices: list[str]) -> str:
    comp = WordCompleter(choices + ["back", "help"], ignore_case=True) if _HAS_PT else None
    return _pt_ask(
        f"[{module_name}] › ",
        completer=comp,
        history_key=f"sub_{module_name}",
        placeholder="back · help · Tab complete",
    ).lower().strip()


def _pause() -> None:
    try:
        input("\n  [dim]Press Enter to continue…[/dim]")
    except (KeyboardInterrupt, EOFError):
        pass
    console.print()


# ── 1. Morning Checklist ──────────────────────────────────────────────────────

def _tui_morning(cfg: dict) -> None:
    from modules import run_morning_checks
    console.print(Rule("[bold bright_cyan]Morning Checklist[/bold bright_cyan]"))
    console.print("[dim]Running all checks…[/dim]")
    results = run_morning_checks(cfg)
    _render_results(results, "Morning Checklist")
    fails  = [r for r in results if r.status == "fail"]
    warns  = [r for r in results if r.status == "warn"]
    if fails:
        console.print(f"[bold bright_red]  ✗  {len(fails)} failure(s)[/bold bright_red]")
    if warns:
        console.print(f"[bold yellow]  ⚠  {len(warns)} warning(s)[/bold yellow]")
    if not fails and not warns:
        console.print("[bold bright_green]  ✓  All checks passed[/bold bright_green]")
    _pause()


# ── 2. Active Directory ───────────────────────────────────────────────────────

def _tui_ad(cfg: dict) -> None:
    from modules import (
        ad_search_user, ad_unlock_account, ad_reset_password,
        ad_set_account_enabled, ad_list_groups, ad_add_to_group,
        ad_remove_from_group,
    )
    from sysknife import ad_configured

    if not ad_configured(cfg):
        console.print(Panel(
            "[yellow]AD not configured. Go to Settings → AD to add server/credentials.[/yellow]",
            border_style="yellow", title="Active Directory"))
        _pause()
        return

    AD_CHOICES = ["search", "unlock", "reset", "enable", "disable",
                  "groups", "addgroup", "removegroup", "back"]

    while True:
        console.print(Rule("[bold bright_blue]Active Directory[/bold bright_blue]"))
        console.print("""  [bold]search[/bold]      Search user by sAMAccountName or display name
  [bold]unlock[/bold]      Unlock locked-out account
  [bold]reset[/bold]       Reset account password
  [bold]enable[/bold]      Enable disabled account
  [bold]disable[/bold]     Disable account
  [bold]groups[/bold]      List all groups (optionally filter)
  [bold]addgroup[/bold]    Add user to group
  [bold]removegroup[/bold] Remove user from group
  [bold]back[/bold]        Return to main menu
""")
        cmd = _sub_prompt("AD", AD_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "search":
            q = _pt_ask("  Username / display name › ", history_key="ad_search")
            if not q:
                continue
            res = ad_search_user(cfg, q)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("users"):
                _render_list_table(res["users"], f"AD Search: {q}", [
                    ("sAMAccountName", "Username"),
                    ("displayName",    "Display Name"),
                    ("mail",           "Email"),
                    ("enabled",        "Enabled"),
                    ("locked",         "Locked"),
                    ("lastLogon",      "Last Logon"),
                ])
            else:
                console.print("[yellow]  No users found.[/yellow]")

        elif cmd == "unlock":
            user = _pt_ask("  sAMAccountName to unlock › ", history_key="ad_user")
            if not user:
                continue
            res = ad_unlock_account(cfg, user)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]")

        elif cmd == "reset":
            user = _pt_ask("  sAMAccountName › ", history_key="ad_user")
            if not user:
                continue
            import getpass
            pwd = getpass.getpass("  New password: ")
            if not pwd:
                continue
            force = _pt_ask("  Must change at next logon? [y/N] › ",
                            history_key="ad_yn").lower().startswith("y")
            res = ad_reset_password(cfg, user, pwd, must_change=force)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]")

        elif cmd in ("enable", "disable"):
            enabled = cmd == "enable"
            user = _pt_ask(f"  sAMAccountName to {cmd} › ", history_key="ad_user")
            if not user:
                continue
            res = ad_set_account_enabled(cfg, user, enabled)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]")

        elif cmd == "groups":
            flt = _pt_ask("  Filter (leave blank for all) › ", history_key="ad_group")
            res = ad_list_groups(cfg, flt or None)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("groups"):
                _render_list_table(res["groups"], "AD Groups", [
                    ("name", "Group Name"),
                    ("description", "Description"),
                    ("members", "Members"),
                ])
            else:
                console.print("[yellow]  No groups found.[/yellow]")

        elif cmd == "addgroup":
            user  = _pt_ask("  sAMAccountName › ", history_key="ad_user")
            group = _pt_ask("  Group CN › ",       history_key="ad_group")
            if not user or not group:
                continue
            res = ad_add_to_group(cfg, user, group)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]")

        elif cmd == "removegroup":
            user  = _pt_ask("  sAMAccountName › ", history_key="ad_user")
            group = _pt_ask("  Group CN › ",       history_key="ad_group")
            if not user or not group:
                continue
            res = ad_remove_from_group(cfg, user, group)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command. Try Tab or type 'help'.[/yellow]")

        _pause()


# ── 3. Azure AD ───────────────────────────────────────────────────────────────

def _tui_azure(cfg: dict) -> None:
    from modules import (
        az_list_users, az_set_user_enabled, az_list_groups,
        az_list_group_members, az_list_devices, az_list_apps,
        az_user_mfa_status,
    )
    from sysknife import az_configured

    if not az_configured(cfg):
        console.print(Panel(
            "[yellow]Azure AD not configured. Go to Settings → Azure to add tenant/client credentials.[/yellow]",
            border_style="yellow", title="Azure AD"))
        _pause()
        return

    AZ_CHOICES = ["users", "enable", "disable", "mfa", "groups",
                  "members", "devices", "apps", "back"]

    while True:
        console.print(Rule("[bold blue]Azure AD[/bold blue]"))
        console.print("""  [bold]users[/bold]    List users (optionally filter by name/UPN)
  [bold]enable[/bold]   Enable Azure user by UPN or object ID
  [bold]disable[/bold]  Disable Azure user
  [bold]mfa[/bold]      Show MFA registration status for a user
  [bold]groups[/bold]   List Azure AD groups
  [bold]members[/bold]  List members of a group
  [bold]devices[/bold]  List Azure AD joined / registered devices
  [bold]apps[/bold]     List Enterprise Applications / Service Principals
  [bold]back[/bold]     Return to main menu
""")
        cmd = _sub_prompt("Azure", AZ_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "users":
            flt = _pt_ask("  Filter (blank for all) › ", history_key="az_search")
            res = az_list_users(cfg, flt or None)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("users"):
                _render_list_table(res["users"], "Azure Users", [
                    ("displayName",       "Name"),
                    ("userPrincipalName", "UPN"),
                    ("accountEnabled",    "Enabled"),
                    ("jobTitle",          "Job Title"),
                    ("department",        "Dept"),
                ])
            else:
                console.print("[yellow]  No users found.[/yellow]")

        elif cmd in ("enable", "disable"):
            enabled = cmd == "enable"
            upn = _pt_ask(f"  UPN or object ID to {cmd} › ", history_key="az_upn")
            if not upn:
                continue
            res = az_set_user_enabled(cfg, upn, enabled)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]")

        elif cmd == "mfa":
            upn = _pt_ask("  UPN or object ID › ", history_key="az_upn")
            if not upn:
                continue
            res = az_user_mfa_status(cfg, upn)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _render_dict_table(res, f"MFA Status: {upn}")

        elif cmd == "groups":
            flt = _pt_ask("  Filter (blank for all) › ", history_key="az_group")
            res = az_list_groups(cfg, flt or None)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("groups"):
                _render_list_table(res["groups"], "Azure Groups", [
                    ("displayName",  "Name"),
                    ("description",  "Description"),
                    ("id",           "Object ID"),
                ])
            else:
                console.print("[yellow]  No groups found.[/yellow]")

        elif cmd == "members":
            gid = _pt_ask("  Group display name or object ID › ", history_key="az_group")
            if not gid:
                continue
            res = az_list_group_members(cfg, gid)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("members"):
                _render_list_table(res["members"], f"Members: {gid}", [
                    ("displayName",       "Name"),
                    ("userPrincipalName", "UPN"),
                    ("accountEnabled",    "Enabled"),
                ])
            else:
                console.print("[yellow]  No members found.[/yellow]")

        elif cmd == "devices":
            res = az_list_devices(cfg)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("devices"):
                _render_list_table(res["devices"], "Azure Devices", [
                    ("displayName",       "Name"),
                    ("operatingSystem",   "OS"),
                    ("operatingSystemVersion", "Version"),
                    ("isManaged",         "Managed"),
                    ("isCompliant",       "Compliant"),
                ])
            else:
                console.print("[yellow]  No devices found.[/yellow]")

        elif cmd == "apps":
            res = az_list_apps(cfg)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            elif res.get("apps"):
                _render_list_table(res["apps"], "Enterprise Applications", [
                    ("displayName", "Name"),
                    ("appId",       "App ID"),
                    ("enabled",     "Enabled"),
                ])
            else:
                console.print("[yellow]  No apps found.[/yellow]")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 4. System Health ──────────────────────────────────────────────────────────

def _tui_health(cfg: dict) -> None:
    from modules import (
        health_cpu, health_memory, health_disk,
        health_top_processes, health_network_io, health_services,
    )

    HEALTH_CHOICES = ["cpu", "memory", "disk", "procs", "netio", "services", "all", "back"]

    while True:
        console.print(Rule("[bold bright_green]System Health[/bold bright_green]"))
        console.print("""  [bold]cpu[/bold]       CPU usage per core
  [bold]memory[/bold]    RAM and swap breakdown
  [bold]disk[/bold]      Disk usage across all mounted partitions
  [bold]procs[/bold]     Top 10 processes by CPU usage
  [bold]netio[/bold]     Network interface I/O counters
  [bold]services[/bold]  Check critical service status (systemd / launchd)
  [bold]all[/bold]       Run all health checks at once
  [bold]back[/bold]      Return to main menu
""")
        cmd = _sub_prompt("Health", HEALTH_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "cpu":
            r = health_cpu()
            _render_dict_table(r, "CPU Usage")

        elif cmd == "memory":
            r = health_memory()
            _render_dict_table(r, "Memory")

        elif cmd == "disk":
            rows = health_disk()
            _render_list_table(rows, "Disk Usage", [
                ("mountpoint",  "Mount"),
                ("device",      "Device"),
                ("fstype",      "FS"),
                ("total",       "Total"),
                ("used",        "Used"),
                ("free",        "Free"),
                ("percent",     "Use%"),
            ])

        elif cmd == "procs":
            rows = health_top_processes(n=10)
            _render_list_table(rows, "Top 10 Processes (CPU)", [
                ("pid",    "PID"),
                ("name",   "Name"),
                ("cpu",    "CPU%"),
                ("mem",    "Mem%"),
                ("status", "Status"),
            ])

        elif cmd == "netio":
            rows = health_network_io()
            _render_list_table(rows, "Network I/O", [
                ("iface",     "Interface"),
                ("bytes_sent", "Sent"),
                ("bytes_recv", "Received"),
                ("packets_sent", "Pkts Sent"),
                ("packets_recv", "Pkts Recv"),
                ("errin",  "Err In"),
                ("errout", "Err Out"),
            ])

        elif cmd == "services":
            rows = health_services()
            _render_results(rows, "Service Status")

        elif cmd == "all":
            _render_dict_table(health_cpu(),    "CPU")
            _render_dict_table(health_memory(), "Memory")
            _render_list_table(health_disk(), "Disk", [
                ("mountpoint","Mount"),("used","Used"),("free","Free"),("percent","Use%"),
            ])
            _render_results(health_services(), "Services")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 5. Network ────────────────────────────────────────────────────────────────

def _tui_network(cfg: dict) -> None:
    from modules import net_ping, net_port_check, net_dns_lookup, net_traceroute

    NET_CHOICES = ["ping", "port", "dns", "trace", "back"]

    while True:
        console.print(Rule("[bold bright_yellow]Network[/bold bright_yellow]"))
        console.print("""  [bold]ping[/bold]   Ping a host or all configured morning hosts
  [bold]port[/bold]   Check if a TCP port is open
  [bold]dns[/bold]    DNS lookup (A / AAAA / MX / TXT)
  [bold]trace[/bold]  Traceroute to a host
  [bold]back[/bold]   Return to main menu
""")
        cmd = _sub_prompt("Network", NET_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "ping":
            morning_hosts = cfg.get("morning", {}).get("ping_hosts", [])
            comp_vals = morning_hosts + ["all"]
            comp = WordCompleter(comp_vals, ignore_case=True) if _HAS_PT else None
            host = _pt_ask(
                "  Host (or 'all' for morning list) › ",
                completer=comp, history_key="net_host",
            )
            if not host:
                continue
            if host.lower() == "all":
                targets = morning_hosts if morning_hosts else ["8.8.8.8", "1.1.1.1"]
            else:
                targets = [host]
            results = [net_ping(h) for h in targets]
            _render_results(results, "Ping Results")

        elif cmd == "port":
            host = _pt_ask("  Host › ", history_key="net_host")
            port = _pt_ask("  Port › ", history_key="net_port")
            if not host or not port:
                continue
            try:
                r = net_port_check(host, int(port))
                _render_results([r], f"Port Check {host}:{port}")
            except ValueError:
                console.print("[yellow]  Port must be a number.[/yellow]")

        elif cmd == "dns":
            host  = _pt_ask("  Hostname › ", history_key="net_host")
            rtype = _pt_ask(
                "  Record type [A/AAAA/MX/TXT] › ",
                completer=WordCompleter(["A","AAAA","MX","TXT"], ignore_case=True) if _HAS_PT else None,
                history_key="net_dns", default="A",
            )
            if not host:
                continue
            res = net_dns_lookup(host, rtype.upper() or "A")
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                t = Table(box=box.SIMPLE, show_header=False, border_style="dim")
                t.add_column("", style="cyan")
                for item in res.get("records", []):
                    t.add_row(str(item))
                console.print(Panel(t, title=f"DNS {rtype} → {host}", border_style="bright_yellow"))

        elif cmd == "trace":
            host = _pt_ask("  Host › ", history_key="net_host")
            if not host:
                continue
            res = net_traceroute(host)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(Panel(
                    res.get("output", ""),
                    title=f"Traceroute → {host}",
                    border_style="bright_yellow",
                ))

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 6. Cleanup ────────────────────────────────────────────────────────────────

def _tui_cleanup(cfg: dict) -> None:
    from modules import (
        cleanup_temp_files, cleanup_old_logs, cleanup_cores,
        cleanup_package_cache, cleanup_trash,
    )

    CLEAN_CHOICES = ["temp", "logs", "cores", "pkgcache", "trash", "all", "back"]

    while True:
        console.print(Rule("[bold bright_magenta]Cleanup[/bold bright_magenta]"))
        console.print("""  [bold]temp[/bold]      Remove temp files (>/tmp on Linux/Mac, %TEMP% on Windows)
  [bold]logs[/bold]      Rotate / compress logs older than 7 days
  [bold]cores[/bold]     Remove core dump files
  [bold]pkgcache[/bold]  Clear apt / yum / dnf / pip package caches
  [bold]trash[/bold]     Empty Trash / Recycle Bin
  [bold]all[/bold]       Run all cleanup tasks
  [bold]back[/bold]      Return to main menu
""")
        cmd = _sub_prompt("Cleanup", CLEAN_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "temp":
            r = cleanup_temp_files()
            _render_results([r], "Temp Files")

        elif cmd == "logs":
            r = cleanup_old_logs()
            _render_results([r], "Log Rotation")

        elif cmd == "cores":
            r = cleanup_cores()
            _render_results([r], "Core Dumps")

        elif cmd == "pkgcache":
            r = cleanup_package_cache()
            _render_results([r], "Package Cache")

        elif cmd == "trash":
            r = cleanup_trash()
            _render_results([r], "Trash / Recycle Bin")

        elif cmd == "all":
            results = [
                cleanup_temp_files(),
                cleanup_old_logs(),
                cleanup_cores(),
                cleanup_package_cache(),
                cleanup_trash(),
            ]
            _render_results(results, "All Cleanup Tasks")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 7. SSH Manager ────────────────────────────────────────────────────────────

def _tui_ssh(cfg: dict) -> None:
    from modules import ssh_connect, ssh_run_command, ssh_add_host, ssh_remove_host

    SSH_CHOICES = ["list", "connect", "run", "add", "remove", "back"]

    while True:
        hosts = cfg.get("ssh_hosts", [])
        aliases = [h["alias"] for h in hosts]

        console.print(Rule("[bold cyan]SSH Manager[/bold cyan]"))
        console.print("""  [bold]list[/bold]      Show all saved SSH hosts
  [bold]connect[/bold]   Open interactive SSH session to a saved host
  [bold]run[/bold]       Run a single command on a saved host
  [bold]add[/bold]       Add a new SSH host shortcut
  [bold]remove[/bold]    Remove a saved SSH host
  [bold]back[/bold]      Return to main menu
""")
        cmd = _sub_prompt("SSH", SSH_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "list":
            if not hosts:
                console.print("[yellow]  No SSH hosts configured. Use 'add' to add one.[/yellow]")
            else:
                _render_list_table(hosts, "Saved SSH Hosts", [
                    ("alias",    "Alias"),
                    ("hostname", "Host"),
                    ("port",     "Port"),
                    ("username", "User"),
                    ("key_path", "Key"),
                ])

        elif cmd == "connect":
            if not aliases:
                console.print("[yellow]  No hosts saved. Use 'add' first.[/yellow]")
            else:
                comp = WordCompleter(aliases, ignore_case=True) if _HAS_PT else None
                alias = _pt_ask(
                    "  Alias › ",
                    completer=comp, history_key="ssh_alias",
                )
                if not alias:
                    continue
                console.print(f"[dim]Connecting to [bold]{alias}[/bold]…[/dim]")
                import getpass
                pw = getpass.getpass("  Password (blank for key auth): ") or None
                res = ssh_connect(cfg, alias, password=pw)
                if res.get("error"):
                    console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
                else:
                    console.print(f"[bright_green]  ✓  {res.get('message', 'Connected')}[/bright_green]")

        elif cmd == "run":
            if not aliases:
                console.print("[yellow]  No hosts saved.[/yellow]")
            else:
                comp = WordCompleter(aliases, ignore_case=True) if _HAS_PT else None
                alias = _pt_ask("  Alias › ", completer=comp, history_key="ssh_alias")
                cmd2  = _pt_ask("  Command to run › ", history_key="ssh_cmd")
                if not alias or not cmd2:
                    continue
                import getpass
                pw = getpass.getpass("  Password (blank for key auth): ") or None
                res = ssh_run_command(cfg, alias, cmd2, password=pw)
                if res.get("error"):
                    console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
                else:
                    console.print(Panel(
                        res.get("stdout", ""),
                        title=f"Output: {cmd2}",
                        border_style="cyan",
                    ))
                    if res.get("stderr"):
                        console.print(Panel(
                            res["stderr"],
                            title="stderr",
                            border_style="yellow",
                        ))

        elif cmd == "add":
            alias    = _pt_ask("  Alias (short name) › ",   history_key="ssh_add")
            hostname = _pt_ask("  Hostname or IP › ",        history_key="ssh_add")
            port_s   = _pt_ask("  Port [22] › ",             history_key="ssh_add", default="22")
            username = _pt_ask("  Username › ",              history_key="ssh_add")
            key_path = _pt_ask("  SSH key path (blank=none) › ", history_key="ssh_add")
            if not alias or not hostname or not username:
                console.print("[yellow]  alias, hostname, and username are required.[/yellow]")
                continue
            try:
                port = int(port_s)
            except ValueError:
                port = 22
            cfg = ssh_add_host(cfg, alias, hostname, port, username, key_path or "")
            console.print(f"[bright_green]  ✓  Host '{alias}' saved.[/bright_green]")

        elif cmd == "remove":
            if not aliases:
                console.print("[yellow]  No hosts saved.[/yellow]")
            else:
                comp = WordCompleter(aliases, ignore_case=True) if _HAS_PT else None
                alias = _pt_ask("  Alias to remove › ", completer=comp, history_key="ssh_alias")
                if not alias:
                    continue
                confirm = _pt_ask(f"  Remove '{alias}'? [y/N] › ", history_key="ssh_yn")
                if confirm.lower().startswith("y"):
                    cfg = ssh_remove_host(cfg, alias)
                    console.print(f"[bright_green]  ✓  '{alias}' removed.[/bright_green]")
                else:
                    console.print("[dim]  Cancelled.[/dim]")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 8. Settings ───────────────────────────────────────────────────────────────

def _tui_settings(cfg: dict) -> None:
    from sysknife import save_config, cfg_encode

    SET_CHOICES = ["ad", "azure", "morning", "theme", "show", "back"]

    while True:
        console.print(Rule("[bold bright_white]Settings[/bold bright_white]"))
        console.print("""  [bold]ad[/bold]       Configure Active Directory (server, base DN, user, password)
  [bold]azure[/bold]    Configure Azure AD (tenant ID, client ID, client secret)
  [bold]morning[/bold]  Configure morning checklist (hosts, thresholds, checks)
  [bold]theme[/bold]    Toggle light/dark theme
  [bold]show[/bold]     Show current configuration (passwords masked)
  [bold]back[/bold]     Return to main menu
""")
        cmd = _sub_prompt("Settings", SET_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "ad":
            console.print("[dim]  Leave blank to keep existing value.[/dim]")
            server   = _pt_ask("  AD Server (e.g. ldap://dc.corp.local) › ", history_key="set_ad") or cfg["ad"]["server"]
            base_dn  = _pt_ask("  Base DN (e.g. DC=corp,DC=local) › ",      history_key="set_ad") or cfg["ad"]["base_dn"]
            user     = _pt_ask("  Bind user (e.g. CORP\\svc_account) › ",   history_key="set_ad") or cfg["ad"]["user"]
            import getpass
            pw_raw   = getpass.getpass("  Password (blank to keep existing): ")
            cfg["ad"]["server"]       = server
            cfg["ad"]["base_dn"]      = base_dn
            cfg["ad"]["user"]         = user
            if pw_raw:
                cfg["ad"]["password_enc"] = cfg_encode(pw_raw)
            save_config(cfg)
            console.print("[bright_green]  ✓  AD settings saved.[/bright_green]")

        elif cmd == "azure":
            console.print("[dim]  Leave blank to keep existing value.[/dim]")
            tenant = _pt_ask("  Tenant ID › ", history_key="set_az") or cfg["azure"]["tenant_id"]
            client = _pt_ask("  Client ID › ", history_key="set_az") or cfg["azure"]["client_id"]
            import getpass
            secret_raw = getpass.getpass("  Client Secret (blank to keep existing): ")
            cfg["azure"]["tenant_id"] = tenant
            cfg["azure"]["client_id"] = client
            if secret_raw:
                cfg["azure"]["client_secret_enc"] = cfg_encode(secret_raw)
            save_config(cfg)
            console.print("[bright_green]  ✓  Azure settings saved.[/bright_green]")

        elif cmd == "morning":
            console.print("[dim]  Comma-separated for lists. Leave blank to keep.[/dim]")
            ping_raw = _pt_ask("  Ping hosts (comma-separated) › ", history_key="set_morning")
            disk_s   = _pt_ask(f"  Disk warn % [{cfg['morning']['disk_warn_pct']}] › ", history_key="set_morning")
            mem_s    = _pt_ask(f"  Mem warn %  [{cfg['morning']['mem_warn_pct']}] › ",  history_key="set_morning")
            cert_s   = _pt_ask(f"  Cert warn days [{cfg['morning']['cert_warn_days']}] › ", history_key="set_morning")
            if ping_raw:
                cfg["morning"]["ping_hosts"] = [h.strip() for h in ping_raw.split(",") if h.strip()]
            if disk_s:
                try: cfg["morning"]["disk_warn_pct"] = int(disk_s)
                except ValueError: pass
            if mem_s:
                try: cfg["morning"]["mem_warn_pct"] = int(mem_s)
                except ValueError: pass
            if cert_s:
                try: cfg["morning"]["cert_warn_days"] = int(cert_s)
                except ValueError: pass
            save_config(cfg)
            console.print("[bright_green]  ✓  Morning settings saved.[/bright_green]")

        elif cmd == "theme":
            cfg["theme"] = "light" if cfg.get("theme") == "dark" else "dark"
            save_config(cfg)
            console.print(f"[bright_green]  ✓  Theme set to [bold]{cfg['theme']}[/bold].[/bright_green]")

        elif cmd == "show":
            import copy, json
            display = copy.deepcopy(cfg)
            display["ad"]["password_enc"]          = "***" if display["ad"]["password_enc"] else "(not set)"
            display["azure"]["client_secret_enc"]  = "***" if display["azure"]["client_secret_enc"] else "(not set)"
            console.print(Panel(
                json.dumps(display, indent=2),
                title="[bold]Current Config[/bold]",
                border_style="bright_white",
            ))

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── main menu ─────────────────────────────────────────────────────────────────

MENU_ITEMS = [
    ("1", "morning",  "bright_cyan",    "☀  Morning Checklist",  "Disk · RAM · CPU · services · ping · certs"),
    ("2", "ad",       "bright_blue",    "🏢  Active Directory",   "Search · unlock · reset · groups"),
    ("3", "azure",    "blue",           "☁  Azure AD",           "Users · groups · devices · MFA · apps"),
    ("4", "health",   "bright_green",   "💚  System Health",      "CPU · memory · disk · processes · I/O"),
    ("5", "network",  "bright_yellow",  "🌐  Network",            "Ping · port check · DNS · traceroute"),
    ("6", "cleanup",  "bright_magenta", "🧹  Cleanup",            "Temp · logs · cores · pkg cache · trash"),
    ("7", "ssh",      "cyan",           "🔐  SSH Manager",        "Connect · run · add · remove hosts"),
    ("8", "settings", "bright_white",   "⚙  Settings",           "AD · Azure · morning thresholds · theme"),
]

MODULE_HANDLERS = {
    "morning":  _tui_morning,
    "ad":       _tui_ad,
    "azure":    _tui_azure,
    "health":   _tui_health,
    "network":  _tui_network,
    "cleanup":  _tui_cleanup,
    "ssh":      _tui_ssh,
    "settings": _tui_settings,
}


def _build_menu_panel() -> Panel:
    t = Table(box=box.SIMPLE, show_header=False, border_style="dim",
              padding=(0, 1), expand=True)
    t.add_column("N",    style="bold", no_wrap=True, width=3)
    t.add_column("Name", style="bold", no_wrap=True, min_width=22)
    t.add_column("Desc", style="dim")

    for num, _, color, label, desc in MENU_ITEMS:
        t.add_row(
            Text(num, style=f"bold {color}"),
            Text(label, style=f"bold {color}"),
            Text(desc),
        )
    return Panel(t, title="[bold bright_cyan]Main Menu[/bold bright_cyan]",
                 border_style="bright_cyan")


def run_tui(cfg: dict, args: argparse.Namespace) -> None:
    print_banner()

    # jump straight to a module if --module supplied
    if getattr(args, "module", None):
        m = args.module.lower()
        if m in MODULE_HANDLERS:
            MODULE_HANDLERS[m](cfg)
        else:
            console.print(f"[yellow]Unknown module: {args.module}[/yellow]")
        return

    # --check: non-interactive morning checklist
    if getattr(args, "check", False):
        from modules import run_morning_checks
        results = run_morning_checks(cfg)
        _render_results(results, "Morning Checklist")
        fails = [r for r in results if r.status == "fail"]
        sys.exit(1 if fails else 0)

    all_names = [m for _, m, *_ in MENU_ITEMS]
    nums      = [n for n, *_ in MENU_ITEMS]
    comp_vals = nums + all_names + ["help", "h", "quit", "q"]
    comp      = WordCompleter(comp_vals, ignore_case=True) if _HAS_PT else None

    while True:
        console.print(_build_menu_panel())
        console.print("[dim]  h  help  ·  q  quit  ·  Tab  complete  ·  ↑↓  history[/dim]\n")

        try:
            choice = _pt_ask(
                "  › ",
                completer=comp,
                history_key="main_menu",
                placeholder="1-8  ·  module name  ·  h for help",
            ).lower().strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Use 'q' to quit.[/dim]")
            continue

        if not choice:
            continue

        if choice in ("q", "quit", "exit"):
            console.print("\n[bold bright_cyan]  Goodbye. Stay sane out there.[/bold bright_cyan]\n")
            sys.exit(0)

        if choice in ("h", "help"):
            print_help()
            continue

        # match by number or name
        matched = None
        for num, name, *_ in MENU_ITEMS:
            if choice == num or choice == name:
                matched = name
                break

        if matched:
            try:
                MODULE_HANDLERS[matched](cfg)
            except KeyboardInterrupt:
                console.print("\n[dim]  Cancelled.[/dim]")
            except Exception as exc:
                console.print(f"\n[bright_red]  Error: {exc}[/bright_red]")
                if "--debug" in sys.argv:
                    traceback.print_exc()
        else:
            console.print(f"[yellow]  Unknown: '{choice}'. Type a number (1-8) or module name.[/yellow]")
