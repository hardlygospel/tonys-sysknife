#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 Tony (hardlygospel) — https://github.com/hardlygospel
"""
Tony's Sysadmin Swiss Army Knife — TUI (Linux / macOS / Windows --tui).
Rich + prompt_toolkit terminal interface.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
import webbrowser
from typing import Any, Callable

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.progress_bar import ProgressBar
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

_HISTORIES: dict[str, "InMemoryHistory"] = {}


def _pt_ask(label: str, *, completer=None, default: str = "",
            placeholder: str = "", history_key: str = "default") -> str:
    if not _HAS_PT:
        try:
            return input(label).strip() or default
        except (KeyboardInterrupt, EOFError):
            return default
    if history_key not in _HISTORIES:
        _HISTORIES[history_key] = InMemoryHistory()
    kw: dict[str, Any] = {
        "history":               _HISTORIES[history_key],
        "style":                  _PT_STYLE,
        "complete_while_typing":  True,
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


# ── palette ───────────────────────────────────────────────────────────────────

STATUS_COLORS = {"ok": "bright_green", "warn": "yellow", "fail": "bright_red",
                 "skip": "dim", "info": "cyan"}
STATUS_ICONS  = {"ok": "✓", "warn": "⚠", "fail": "✗", "skip": "·", "info": "●"}


# ── banner & status bar ───────────────────────────────────────────────────────

def _gradient_text(text: str, colors: list[str]) -> Text:
    t = Text()
    for i, ch in enumerate(text):
        idx = min(i * len(colors) // max(len(text), 1), len(colors) - 1)
        t.append(ch, style=colors[idx])
    return t


def print_banner() -> None:
    console.print()
    title = _gradient_text(
        " ⚔  Tony's Sysadmin Swiss Army Knife ",
        ["bold bright_white", "bold bright_cyan", "bold cyan",
         "bold blue", "bold bright_blue", "bold magenta"],
    )
    sub = Text(
        "v2.0.0  ·  Morning · AD · Azure · Health · Network · Cleanup · SSH · Procs · Logs",
        style="dim",
    )
    panel = Panel(
        Align.center(Group(title, Align.center(sub))),
        border_style="bright_cyan",
        box=box.DOUBLE_EDGE,
        padding=(0, 2),
        width=min(console.width, 92),
    )
    console.print(Align.center(panel))
    console.print()


def _status_bar() -> Text:
    """Compact one-line status bar shown above the main menu."""
    import socket
    bits: list[str] = []
    bits.append(f"[bright_cyan]{socket.gethostname()}[/]")
    bits.append(f"[white]{sys.platform}[/]")
    try:
        import psutil
        boot = time.time() - psutil.boot_time()
        d, rem = divmod(int(boot), 86400)
        h, rem = divmod(rem, 3600)
        m, _   = divmod(rem, 60)
        up = (f"{d}d " if d else "") + f"{h:02d}h{m:02d}"
        bits.append(f"[dim]up[/dim] [white]{up}[/]")
        bits.append(f"[dim]cpu[/dim] [white]{psutil.cpu_percent(interval=None):.0f}%[/]")
        bits.append(f"[dim]mem[/dim] [white]{psutil.virtual_memory().percent:.0f}%[/]")
        if hasattr(os, "getloadavg"):
            l1, l5, l15 = os.getloadavg()
            bits.append(f"[dim]load[/dim] [white]{l1:.2f}/{l5:.2f}/{l15:.2f}[/]")
    except Exception:
        pass
    bits.append(f"[dim]{time.strftime('%Y-%m-%d %H:%M')}[/]")
    return Text.from_markup("  ·  ".join(bits))


# ── help ──────────────────────────────────────────────────────────────────────

def print_help() -> None:
    console.print()
    console.print(Rule("[bold bright_cyan]Help — Tony's Sysadmin Swiss Army Knife[/bold bright_cyan]"))
    console.print()

    nav = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
                border_style="dim", expand=True)
    nav.add_column("Key / Command", style="bold yellow", no_wrap=True)
    nav.add_column("Action")
    for cmd, action in [
        ("1 – 9",      "Pick a module by number"),
        ("module name","e.g. 'morning', 'health', 'procs'"),
        ("h / help",   "Show this help screen"),
        ("q / quit",   "Exit the tool"),
        ("Tab",        "Autocomplete current input"),
        ("↑ / ↓",      "Scroll input history"),
        ("Ctrl+C",     "Cancel / return to menu"),
    ]:
        nav.add_row(cmd, action)

    mods = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
                 border_style="dim", expand=True)
    mods.add_column("Module", style="bold", no_wrap=True)
    mods.add_column("What it does")
    for mod, desc in [
        ("[bright_cyan]1  Morning Checklist[/]",
         "Disk · RAM · CPU · services · pings · TLS certs · backups → HTML report"),
        ("[bright_blue]2  Active Directory[/]",
         "Search · unlock · reset · enable/disable · groups · group membership"),
        ("[blue]3  Azure AD[/]",
         "Users · groups · devices · enterprise apps · MFA registration"),
        ("[bright_green]4  System Health[/]",
         "Live watch · CPU · memory · disk · top procs · battery · temps · load"),
        ("[bright_yellow]5  Network[/]",
         "Ping · port · DNS · trace · HTTP · SSL · WHOIS · public IP · port scan"),
        ("[bright_magenta]6  Cleanup[/]",
         "Temp · logs · cores · pkg cache · trash · big files · downloads · APPLY"),
        ("[cyan]7  SSH Manager[/]",
         "List · connect · run command · add · remove SSH host shortcuts"),
        ("[orange1]8  Processes[/]",
         "List · search · kill · find by port · process tree"),
        ("[medium_purple]9  Logs[/]",
         "View recent journal / Console / Event Log entries with filtering"),
        ("[bright_white]10 Settings[/]",
         "Configure AD · Azure · ping hosts · thresholds · theme"),
    ]:
        mods.add_row(mod, desc)

    console.print(Columns([
        Panel(nav,  title="[bold]Navigation[/bold]", border_style="bright_cyan", expand=True),
        Panel(mods, title="[bold]Modules[/bold]",    border_style="bright_cyan", expand=True),
    ]))
    console.print()

    tips = Table(box=box.SIMPLE, show_header=False, border_style="dim", expand=True)
    tips.add_column("", style="yellow", no_wrap=True, width=3)
    tips.add_column("")
    for t in [
        "[bold]--check[/bold]   Run morning checklist non-interactively (exit 1 on failure)",
        "[bold]--report[/bold]  Save morning checklist as HTML/JSON/txt — open in browser when done",
        "[bold]--module[/bold]  Open a module directly: morning, ad, azure, health, network, cleanup, ssh, procs, logs",
        "[bold]--watch[/bold]   Live-refreshing system health dashboard (combine with --module health)",
        "Cleanup is [bold]dry-run[/bold] by default; [bold]apply[/bold] inside the panel actually deletes (asks first)",
        "Passwords/secrets are base64-encoded in [bold]~/.sysknife/config.json[/bold]",
    ]:
        tips.add_row("★", t)
    console.print(Panel(tips, title="[bold]Tips[/bold]", border_style="dim"))
    console.print()


# ── render helpers ────────────────────────────────────────────────────────────

def _render_results(results: list, title: str = "Results") -> None:
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
              border_style="dim", expand=True, padding=(0, 1))
    t.add_column("Check",  style="bold", min_width=18)
    t.add_column("Status", no_wrap=True, min_width=6)
    t.add_column("Detail")
    for r in results:
        color = STATUS_COLORS.get(r.status, "white")
        icon  = STATUS_ICONS.get(r.status, "?")
        t.add_row(r.name,
                  Text(f"{icon} {r.status.upper()}", style=f"bold {color}"),
                  r.detail)
    console.print(Panel(t, title=f"[bold]{title}[/bold]", border_style="bright_cyan"))


def _render_dict_table(data: dict, title: str,
                       key_label: str = "Field", val_label: str = "Value") -> None:
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
              border_style="dim", expand=True, padding=(0, 1))
    t.add_column(key_label, style="bold cyan", min_width=20)
    t.add_column(val_label)
    for k, v in data.items():
        t.add_row(str(k), str(v) if v not in (None, "") else "[dim]—[/dim]")
    console.print(Panel(t, title=f"[bold]{title}[/bold]", border_style="bright_cyan"))


def _render_list_table(rows: list[dict], title: str,
                       columns: list[tuple[str, str]]) -> None:
    t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold bright_cyan",
              border_style="dim", expand=True, padding=(0, 1))
    for _, label in columns:
        t.add_column(label)
    for row in rows:
        t.add_row(*[str(row.get(k, "")) for k, _ in columns])
    console.print(Panel(t, title=f"[bold]{title}[/bold]", border_style="bright_cyan"))


def _sub_prompt(module_name: str, choices: list[str]) -> str:
    comp = (WordCompleter(choices + ["back", "help"], ignore_case=True)
            if _HAS_PT else None)
    return _pt_ask(
        f"[{module_name}] › ",
        completer=comp,
        history_key=f"sub_{module_name}",
        placeholder="back · help · Tab complete",
    ).lower().strip()


def _pause() -> None:
    try:
        input("\n  Press Enter to continue… ")
    except (KeyboardInterrupt, EOFError):
        pass
    console.print()


def _confirm(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    a = _pt_ask(prompt + suffix + " › ", history_key="confirm").lower().strip()
    if not a:
        return default
    return a.startswith("y")


# ── 1. Morning Checklist ──────────────────────────────────────────────────────

def _tui_morning(cfg: dict) -> None:
    from modules import (run_morning_checks, report_morning_html,
                         report_morning_text, report_morning_json, save_report)

    MORNING_CHOICES = ["run", "report", "json", "txt", "back"]
    last_results: list = []

    while True:
        console.print(Rule("[bold bright_cyan]Morning Checklist[/bold bright_cyan]"))
        console.print("""  [bold]run[/bold]      Execute all configured checks
  [bold]report[/bold]   Save HTML report and open in browser
  [bold]json[/bold]     Save JSON report (CI / scripting friendly)
  [bold]txt[/bold]      Save plain-text report
  [bold]back[/bold]     Return to main menu
""")
        cmd = _sub_prompt("Morning", MORNING_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd in ("run", "r"):
            console.print("[dim]Running checks…[/dim]")
            last_results = run_morning_checks(cfg)
            _render_results(last_results, "Morning Checklist")
            fails = sum(1 for r in last_results if r.status == "fail")
            warns = sum(1 for r in last_results if r.status == "warn")
            if fails:
                console.print(f"[bold bright_red]  ✗  {fails} failure(s)[/bold bright_red]")
            if warns:
                console.print(f"[bold yellow]  ⚠  {warns} warning(s)[/bold yellow]")
            if not fails and not warns:
                console.print("[bold bright_green]  ✓  All checks passed[/bold bright_green]")

        elif cmd in ("report", "html"):
            if not last_results:
                last_results = run_morning_checks(cfg)
            html = report_morning_html(cfg, last_results)
            path = save_report(html, "html")
            console.print(f"[bright_green]  ✓  Report saved to:[/bright_green] [bold]{path}[/bold]")
            try:
                webbrowser.open(f"file://{path}")
                console.print("[dim]  Opened in browser.[/dim]")
            except Exception:
                pass

        elif cmd == "json":
            if not last_results:
                last_results = run_morning_checks(cfg)
            data = report_morning_json(cfg, last_results)
            path = save_report(data, "json")
            console.print(f"[bright_green]  ✓  JSON saved to:[/bright_green] [bold]{path}[/bold]")

        elif cmd == "txt":
            if not last_results:
                last_results = run_morning_checks(cfg)
            txt = report_morning_text(cfg, last_results)
            path = save_report(txt, "txt")
            console.print(f"[bright_green]  ✓  Text report saved to:[/bright_green] [bold]{path}[/bold]")
            console.print()
            console.print(txt)

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print(f"[yellow]  Unknown: '{cmd}'.[/yellow]")

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
            "[yellow]AD not configured. Settings → AD to add server/credentials.[/yellow]",
            border_style="yellow", title="Active Directory"))
        _pause()
        return

    AD_CHOICES = ["search", "unlock", "reset", "enable", "disable",
                  "groups", "addgroup", "removegroup", "back"]

    while True:
        console.print(Rule("[bold bright_blue]Active Directory[/bold bright_blue]"))
        console.print("""  [bold]search[/bold]      Search user by sAMAccountName / display name / mail
  [bold]unlock[/bold]      Unlock locked-out account
  [bold]reset[/bold]       Reset account password
  [bold]enable[/bold]      Enable disabled account
  [bold]disable[/bold]     Disable account
  [bold]groups[/bold]      List groups (optionally filter)
  [bold]addgroup[/bold]    Add user to group
  [bold]removegroup[/bold] Remove user from group
  [bold]back[/bold]        Return to main menu
""")
        cmd = _sub_prompt("AD", AD_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "search":
            q = _pt_ask("  Username / display name / mail › ", history_key="ad_search")
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
            force = _confirm("  Must change at next logon?", default=False)
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
            console.print(
                f"[bright_red]  ✗  {res['error']}[/bright_red]" if res.get("error")
                else f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]"
            )

        elif cmd == "groups":
            flt = _pt_ask("  Filter (blank for all) › ", history_key="ad_group")
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

        elif cmd in ("addgroup", "removegroup"):
            user  = _pt_ask("  sAMAccountName › ", history_key="ad_user")
            group = _pt_ask("  Group CN › ",       history_key="ad_group")
            if not user or not group:
                continue
            fn = ad_add_to_group if cmd == "addgroup" else ad_remove_from_group
            res = fn(cfg, user, group)
            console.print(
                f"[bright_red]  ✗  {res['error']}[/bright_red]" if res.get("error")
                else f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]"
            )

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

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
            "[yellow]Azure AD not configured. Settings → Azure for tenant/client.[/yellow]",
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
  [bold]apps[/bold]     List Enterprise Applications
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
            console.print(
                f"[bright_red]  ✗  {res['error']}[/bright_red]" if res.get("error")
                else f"[bright_green]  ✓  {res.get('message', 'Done')}[/bright_green]"
            )

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
                    ("displayName",            "Name"),
                    ("operatingSystem",        "OS"),
                    ("operatingSystemVersion", "Version"),
                    ("isManaged",              "Managed"),
                    ("isCompliant",            "Compliant"),
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


# ── 4. System Health (with watch mode) ────────────────────────────────────────

def _watch_renderable(snapshot: dict) -> Panel:
    """Build the live dashboard renderable for one tick."""
    cpu_pct = snapshot["cpu_pct"]
    mem_pct = snapshot["mem_pct"]
    swap_pct = snapshot["swap_pct"]
    procs = snapshot["procs"]

    def _bar(pct: float, width: int = 40) -> Text:
        filled = int(width * pct / 100)
        color = "bright_green" if pct < 60 else ("yellow" if pct < 85 else "bright_red")
        bar = Text()
        bar.append("█" * filled, style=color)
        bar.append("░" * (width - filled), style="dim")
        return bar

    body = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    body.add_column(style="bold cyan", no_wrap=True, width=8)
    body.add_column(width=42)
    body.add_column(no_wrap=True, width=22)

    body.add_row("CPU",   _bar(cpu_pct),
                 Text(f"{cpu_pct:>5.1f}%   {snapshot['cores']} cores",
                      style="white"))
    body.add_row("MEM",   _bar(mem_pct),
                 Text(f"{mem_pct:>5.1f}%   {snapshot['mem_used']} / {snapshot['mem_total']}",
                      style="white"))
    body.add_row("SWAP",  _bar(swap_pct),
                 Text(f"{swap_pct:>5.1f}%   {snapshot['swap_used']} / {snapshot['swap_total']}"
                      if snapshot["swap_total"] != "0 B"
                      else "no swap", style="white"))

    pt = Table(box=box.SIMPLE, show_header=True, header_style="bold bright_cyan",
               border_style="dim", expand=True)
    pt.add_column("PID", style="dim", width=8)
    pt.add_column("Name", style="white", min_width=22)
    pt.add_column("CPU%", width=8)
    pt.add_column("Mem%", width=8)
    for p in procs[:10]:
        cpu = float(p.get("cpu", 0))
        col = "bright_green" if cpu < 30 else ("yellow" if cpu < 70 else "bright_red")
        pt.add_row(str(p.get("pid", "")), p.get("name", "?"),
                   Text(f"{cpu:.1f}", style=col),
                   f"{float(p.get('mem', 0)):.1f}")

    title = Text.from_markup(
        f"[bold bright_cyan]Sysknife Watch[/bold bright_cyan]  "
        f"·  [white]{snapshot['hostname']}[/]  "
        f"·  [dim]up[/] [white]{snapshot['uptime']}[/]  "
        f"·  [dim]{snapshot['now']}[/]"
    )
    return Panel(
        Group(body, Padding(pt, (1, 0, 0, 0))),
        title=title,
        subtitle="[dim]Press Ctrl+C to exit[/dim]",
        border_style="bright_cyan",
        padding=(1, 2),
    )


def _watch_snapshot() -> dict:
    import psutil
    import socket
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    boot = time.time() - psutil.boot_time()
    d, rem = divmod(int(boot), 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)

    def _fmt(b: int) -> str:
        n = float(b)
        for u in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {u}"
            n /= 1024
        return f"{n:.1f} PB"

    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            procs.append({
                "pid":  p.info["pid"],
                "name": (p.info.get("name") or "?")[:24],
                "cpu":  p.cpu_percent(None),
                "mem":  float(p.info.get("memory_percent") or 0),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)

    return {
        "hostname":   socket.gethostname(),
        "uptime":     (f"{d}d " if d else "") + f"{h:02d}h{m:02d}m",
        "cpu_pct":    cpu,
        "cores":      psutil.cpu_count() or 1,
        "mem_pct":    mem.percent,
        "mem_used":   _fmt(mem.used),
        "mem_total":  _fmt(mem.total),
        "swap_pct":   swap.percent,
        "swap_used":  _fmt(swap.used),
        "swap_total": _fmt(swap.total),
        "procs":      procs,
        "now":        time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _tui_health_watch() -> None:
    """Live auto-refreshing dashboard. Ctrl+C exits."""
    import psutil
    psutil.cpu_percent(None)
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.5)
    try:
        with Live(_watch_renderable(_watch_snapshot()),
                  refresh_per_second=2, screen=True, console=console) as live:
            while True:
                time.sleep(0.5)
                live.update(_watch_renderable(_watch_snapshot()))
    except KeyboardInterrupt:
        pass
    console.print("[dim]Watch exited.[/dim]\n")


def _tui_health(cfg: dict) -> None:
    from modules import (
        health_cpu, health_memory, health_disk, health_top_processes,
        health_network_io, health_services, health_battery, health_load_avg,
        health_temperatures,
    )
    HEALTH_CHOICES = ["watch", "cpu", "memory", "disk", "procs",
                      "netio", "services", "battery", "temps", "load",
                      "all", "back"]

    while True:
        console.print(Rule("[bold bright_green]System Health[/bold bright_green]"))
        console.print("""  [bold]watch[/bold]     Live auto-refreshing dashboard (Ctrl+C exits)
  [bold]cpu[/bold]       CPU usage per core
  [bold]memory[/bold]    RAM and swap breakdown
  [bold]disk[/bold]      Disk usage across mounted partitions
  [bold]procs[/bold]     Top 10 processes by CPU
  [bold]netio[/bold]     Network interface I/O counters
  [bold]services[/bold]  Critical service status
  [bold]battery[/bold]   Battery / power status
  [bold]temps[/bold]     Hardware temperature sensors
  [bold]load[/bold]      Load average (1/5/15 min)
  [bold]all[/bold]       Run a full snapshot
  [bold]back[/bold]      Return to main menu
""")
        cmd = _sub_prompt("Health", HEALTH_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "watch":
            _tui_health_watch()
            continue

        elif cmd == "cpu":
            _render_dict_table(health_cpu(), "CPU Usage")

        elif cmd == "memory":
            _render_dict_table(health_memory(), "Memory")

        elif cmd == "disk":
            _render_list_table(health_disk(), "Disk Usage", [
                ("mountpoint", "Mount"),
                ("device",     "Device"),
                ("fstype",     "FS"),
                ("total",      "Total"),
                ("used",       "Used"),
                ("free",       "Free"),
                ("percent",    "Use%"),
            ])

        elif cmd == "procs":
            _render_list_table(health_top_processes(10), "Top 10 Processes (CPU)", [
                ("pid", "PID"), ("name", "Name"),
                ("cpu", "CPU%"), ("mem", "Mem%"), ("status", "Status"),
            ])

        elif cmd == "netio":
            _render_list_table(health_network_io(), "Network I/O", [
                ("iface", "Interface"),
                ("bytes_sent",   "Sent"),
                ("bytes_recv",   "Received"),
                ("packets_sent", "Pkts Sent"),
                ("packets_recv", "Pkts Recv"),
                ("errin",  "Err In"),
                ("errout", "Err Out"),
            ])

        elif cmd == "services":
            _render_results(health_services(), "Service Status")

        elif cmd == "battery":
            _render_dict_table(health_battery(), "Battery")

        elif cmd == "temps":
            temps = health_temperatures()
            if not temps:
                console.print("[yellow]  Temperature sensors not available on this system.[/yellow]")
            else:
                _render_list_table(temps, "Temperatures", [
                    ("sensor", "Sensor"), ("label", "Label"),
                    ("current", "Current"), ("high", "High"), ("critical", "Critical"),
                ])

        elif cmd == "load":
            _render_dict_table(health_load_avg(), "Load Average")

        elif cmd == "all":
            _render_dict_table(health_cpu(),    "CPU")
            _render_dict_table(health_memory(), "Memory")
            _render_dict_table(health_load_avg(), "Load")
            _render_list_table(health_disk(), "Disk", [
                ("mountpoint", "Mount"), ("used", "Used"),
                ("free", "Free"), ("percent", "Use%"),
            ])
            _render_results(health_services(), "Services")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 5. Network ────────────────────────────────────────────────────────────────

def _tui_network(cfg: dict) -> None:
    from modules import (
        net_ping, net_port_check, net_dns_lookup, net_traceroute,
        net_whois, net_http_check, net_ssl_check, net_public_ip,
        net_my_ips, net_port_scan, COMMON_PORTS,
    )
    NET_CHOICES = ["ping", "port", "dns", "trace", "http", "ssl",
                   "whois", "pubip", "myips", "scan", "back"]

    while True:
        console.print(Rule("[bold bright_yellow]Network[/bold bright_yellow]"))
        console.print("""  [bold]ping[/bold]    Ping a host (or 'all' for morning hosts)
  [bold]port[/bold]    TCP port reachability check
  [bold]dns[/bold]     DNS lookup (A / AAAA / MX / TXT)
  [bold]trace[/bold]   Traceroute to a host
  [bold]http[/bold]    HTTP(S) check — status, redirect chain, timing, headers
  [bold]ssl[/bold]     TLS certificate inspection (issuer, expiry, SANs)
  [bold]whois[/bold]   Domain WHOIS lookup
  [bold]pubip[/bold]   Show public IP (via ipify / ifconfig.me / icanhazip)
  [bold]myips[/bold]   Show local interface IPs
  [bold]scan[/bold]    Scan common ports on a host
  [bold]back[/bold]    Return to main menu
""")
        cmd = _sub_prompt("Network", NET_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "ping":
            morning_hosts = cfg.get("morning", {}).get("ping_hosts", [])
            comp = (WordCompleter(morning_hosts + ["all"], ignore_case=True)
                    if _HAS_PT else None)
            host = _pt_ask("  Host (or 'all' for morning hosts) › ",
                           completer=comp, history_key="net_host")
            if not host:
                continue
            targets = (morning_hosts if morning_hosts else ["8.8.8.8", "1.1.1.1"]
                       if host.lower() == "all" else [host])
            _render_results([net_ping(h) for h in targets], "Ping Results")

        elif cmd == "port":
            host = _pt_ask("  Host › ", history_key="net_host")
            port = _pt_ask("  Port › ", history_key="net_port")
            if not host or not port:
                continue
            try:
                _render_results([net_port_check(host, int(port))],
                                f"Port Check {host}:{port}")
            except ValueError:
                console.print("[yellow]  Port must be a number.[/yellow]")

        elif cmd == "dns":
            host = _pt_ask("  Hostname › ", history_key="net_host")
            comp = (WordCompleter(["A", "AAAA", "MX", "TXT", "NS", "CNAME"],
                                  ignore_case=True) if _HAS_PT else None)
            rtype = _pt_ask("  Record type [A] › ", completer=comp,
                            history_key="net_dns", default="A")
            if not host:
                continue
            res = net_dns_lookup(host, rtype.upper())
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                t = Table(box=box.SIMPLE, show_header=False, border_style="dim")
                t.add_column("", style="cyan")
                for item in res.get("records", []):
                    t.add_row(str(item))
                console.print(Panel(t, title=f"DNS {rtype.upper()} → {host}",
                                    border_style="bright_yellow"))

        elif cmd == "trace":
            host = _pt_ask("  Host › ", history_key="net_host")
            if not host:
                continue
            res = net_traceroute(host)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                console.print(Panel(res.get("output", ""),
                                    title=f"Traceroute → {host}",
                                    border_style="bright_yellow"))

        elif cmd == "http":
            url = _pt_ask("  URL (https:// optional) › ", history_key="net_url")
            if not url:
                continue
            res = net_http_check(url)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _render_dict_table(res, f"HTTP {url}")

        elif cmd == "ssl":
            host = _pt_ask("  Host (e.g. github.com) › ", history_key="net_host")
            port = _pt_ask("  Port [443] › ", history_key="net_sslport", default="443")
            if not host:
                continue
            try:
                res = net_ssl_check(host, int(port))
            except ValueError:
                console.print("[yellow]  Port must be a number.[/yellow]")
                continue
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _render_dict_table(res, f"TLS Certificate — {host}:{port}")

        elif cmd == "whois":
            domain = _pt_ask("  Domain › ", history_key="net_whois")
            if not domain:
                continue
            res = net_whois(domain)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _render_dict_table(res.get("summary", {}),
                                   f"WHOIS — {domain}")

        elif cmd == "pubip":
            res = net_public_ip()
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _render_dict_table(res, "Public IP")

        elif cmd == "myips":
            _render_list_table(net_my_ips(), "Local Interfaces", [
                ("iface", "Interface"), ("ipv4", "IPv4"),
                ("ipv6", "IPv6"), ("mac", "MAC"),
                ("is_up", "Up"), ("speed", "Speed"),
            ])

        elif cmd == "scan":
            host = _pt_ask("  Host › ", history_key="net_host")
            if not host:
                continue
            ports_raw = _pt_ask(
                "  Ports (comma-separated, blank=common) › ",
                history_key="net_scanports",
            )
            try:
                ports = ([int(p.strip()) for p in ports_raw.split(",") if p.strip()]
                         if ports_raw else COMMON_PORTS)
            except ValueError:
                console.print("[yellow]  Ports must be numbers.[/yellow]")
                continue
            console.print(f"[dim]Scanning {len(ports)} ports on {host}…[/dim]")
            results = net_port_scan(host, ports)
            open_ports = [r for r in results if r["status"] == "open"]
            _render_list_table(results, f"Port Scan — {host}", [
                ("port", "Port"), ("status", "Status"),
            ])
            console.print(f"[bright_green]  ✓  {len(open_ports)} open[/bright_green]"
                          f"  ·  [dim]{len(results) - len(open_ports)} closed[/dim]")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 6. Cleanup ────────────────────────────────────────────────────────────────

def _tui_cleanup(cfg: dict) -> None:
    from modules import (
        cleanup_temp_files, cleanup_old_logs, cleanup_cores,
        cleanup_package_cache, cleanup_trash, cleanup_old_downloads,
        cleanup_apply, cleanup_big_files,
    )
    CLEAN_CHOICES = ["scan", "temp", "logs", "cores", "pkgcache", "trash",
                     "downloads", "big", "apply", "back"]
    last_result = None       # most recent CheckResult
    last_label  = ""

    while True:
        console.print(Rule("[bold bright_magenta]Cleanup[/bold bright_magenta]"))
        console.print("""  [bold]scan[/bold]       Scan ALL categories (dry-run summary)
  [bold]temp[/bold]       Temp files (>/tmp on Linux/Mac, %TEMP% on Windows)
  [bold]logs[/bold]       Rotated/compressed logs older than 7 days
  [bold]cores[/bold]      Core dumps / crash reports
  [bold]pkgcache[/bold]   apt / dnf / pip / brew package caches
  [bold]trash[/bold]      Trash / Recycle Bin contents
  [bold]downloads[/bold]  ~/Downloads files older than N days
  [bold]big[/bold]        Find large files in a directory (top 25 by size)
  [bold]apply[/bold]      DELETE the files from the most recent scan (confirm)
  [bold]back[/bold]       Return to main menu
""")
        cmd = _sub_prompt("Cleanup", CLEAN_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "scan":
            results = [
                cleanup_temp_files(),
                cleanup_old_logs(),
                cleanup_cores(),
                cleanup_package_cache(),
                cleanup_trash(),
                cleanup_old_downloads(30),
            ]
            _render_results(results, "Cleanup Scan (dry-run)")
            last_result = None  # apply needs a single category

        elif cmd == "temp":
            last_result = cleanup_temp_files();    last_label = "Temp Files"
            _render_results([last_result], last_label)

        elif cmd == "logs":
            last_result = cleanup_old_logs();      last_label = "Old Logs"
            _render_results([last_result], last_label)

        elif cmd == "cores":
            last_result = cleanup_cores();         last_label = "Core Dumps"
            _render_results([last_result], last_label)

        elif cmd == "pkgcache":
            last_result = cleanup_package_cache(); last_label = "Package Cache"
            _render_results([last_result], last_label)

        elif cmd == "trash":
            last_result = cleanup_trash();         last_label = "Trash / Recycle Bin"
            _render_results([last_result], last_label)

        elif cmd == "downloads":
            days = _pt_ask("  Older than N days [30] › ",
                           history_key="cleanup_days", default="30")
            try:
                last_result = cleanup_old_downloads(int(days))
                last_label  = "Old Downloads"
                _render_results([last_result], last_label)
            except ValueError:
                console.print("[yellow]  Days must be a number.[/yellow]")

        elif cmd == "big":
            d = _pt_ask("  Directory [~] › ",
                        history_key="cleanup_big", default=str(os.path.expanduser("~")))
            min_mb = _pt_ask("  Min size MB [50] › ",
                             history_key="cleanup_big_mb", default="50")
            try:
                files = cleanup_big_files(d, top_n=25, min_size_mb=int(min_mb))
            except ValueError:
                console.print("[yellow]  Min size must be a number.[/yellow]")
                continue
            if files and "error" in files[0]:
                console.print(f"[bright_red]  ✗  {files[0]['error']}[/bright_red]")
            elif not files:
                console.print(f"[yellow]  No files ≥ {min_mb} MB found in {d}.[/yellow]")
            else:
                _render_list_table(files, f"Top {len(files)} Big Files in {d}", [
                    ("size_human", "Size"),
                    ("mtime",      "Modified"),
                    ("path",       "Path"),
                ])

        elif cmd == "apply":
            if not last_result or not last_result.items:
                console.print("[yellow]  Nothing scanned. Run a category first "
                              "(temp / logs / cores / pkgcache / trash / downloads).[/yellow]")
                continue
            n = len(last_result.items)
            console.print(f"[bold yellow]  ⚠  About to delete {n} files from "
                          f"'{last_label}'.[/bold yellow]")
            console.print(f"[dim]  Examples: {last_result.items[0].get('path', '?')}"
                          f"{' …' if n > 1 else ''}[/dim]")
            if not _confirm("  Delete these files?", default=False):
                console.print("[dim]  Cancelled.[/dim]")
                continue
            res = cleanup_apply(last_result.items)
            console.print(f"[bright_green]  ✓  Deleted {res['deleted']} files, "
                          f"freed {res['freed_human']}.[/bright_green]")
            if res["errors"]:
                console.print(f"[yellow]  ⚠  {len(res['errors'])} errors:[/yellow]")
                for e in res["errors"][:5]:
                    console.print(f"    [dim]{e}[/dim]")
            last_result = None

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
  [bold]connect[/bold]   Test connection (uname/ver) on a saved host
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
                    ("alias", "Alias"), ("hostname", "Host"),
                    ("port", "Port"), ("username", "User"), ("key_path", "Key"),
                ])

        elif cmd == "connect":
            if not aliases:
                console.print("[yellow]  No hosts saved. Use 'add' first.[/yellow]")
            else:
                comp = (WordCompleter(aliases, ignore_case=True) if _HAS_PT else None)
                alias = _pt_ask("  Alias › ", completer=comp, history_key="ssh_alias")
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
                comp = (WordCompleter(aliases, ignore_case=True) if _HAS_PT else None)
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
                    console.print(Panel(res.get("stdout", "") or "(no output)",
                                        title=f"stdout — exit {res.get('exit_code', 0)}",
                                        border_style="cyan"))
                    if res.get("stderr"):
                        console.print(Panel(res["stderr"],
                                            title="stderr", border_style="yellow"))

        elif cmd == "add":
            alias    = _pt_ask("  Alias (short name) › ",        history_key="ssh_add")
            hostname = _pt_ask("  Hostname or IP › ",            history_key="ssh_add")
            port_s   = _pt_ask("  Port [22] › ",                 history_key="ssh_add", default="22")
            username = _pt_ask("  Username › ",                  history_key="ssh_add")
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
                comp = (WordCompleter(aliases, ignore_case=True) if _HAS_PT else None)
                alias = _pt_ask("  Alias to remove › ", completer=comp, history_key="ssh_alias")
                if not alias:
                    continue
                if _confirm(f"  Remove '{alias}'?", default=False):
                    cfg = ssh_remove_host(cfg, alias)
                    console.print(f"[bright_green]  ✓  '{alias}' removed.[/bright_green]")
                else:
                    console.print("[dim]  Cancelled.[/dim]")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 8. Processes ──────────────────────────────────────────────────────────────

def _tui_processes(cfg: dict) -> None:
    from modules import proc_list, proc_tree, proc_find_by_port, proc_kill

    P_CHOICES = ["list", "search", "mem", "tree", "port", "kill", "back"]

    while True:
        console.print(Rule("[bold orange1]Processes[/bold orange1]"))
        console.print("""  [bold]list[/bold]    Top 30 processes by CPU
  [bold]search[/bold]  Filter processes by name / cmdline
  [bold]mem[/bold]     Top 30 processes by memory
  [bold]tree[/bold]    ASCII process tree
  [bold]port[/bold]    Find process listening on a port
  [bold]kill[/bold]    Kill a process by PID or name (TERM, or 'force' for KILL)
  [bold]back[/bold]    Return to main menu
""")
        cmd = _sub_prompt("Procs", P_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "list":
            rows = proc_list(limit=30)
            _render_list_table(rows, "Top 30 by CPU", [
                ("pid", "PID"), ("name", "Name"), ("user", "User"),
                ("cpu", "CPU%"), ("mem", "Mem%"), ("status", "Status"),
                ("started", "Started"),
            ])

        elif cmd == "search":
            q = _pt_ask("  Name / cmdline contains › ", history_key="proc_q")
            if not q:
                continue
            rows = proc_list(query=q, limit=50)
            if not rows:
                console.print(f"[yellow]  No processes matched '{q}'.[/yellow]")
            else:
                _render_list_table(rows, f"Processes matching '{q}'", [
                    ("pid", "PID"), ("name", "Name"), ("user", "User"),
                    ("cpu", "CPU%"), ("mem", "Mem%"), ("cmd", "Command"),
                ])

        elif cmd == "mem":
            rows = proc_list(sort_by="mem", limit=30)
            _render_list_table(rows, "Top 30 by Memory", [
                ("pid", "PID"), ("name", "Name"), ("user", "User"),
                ("mem", "Mem%"), ("cpu", "CPU%"), ("status", "Status"),
            ])

        elif cmd == "tree":
            root = _pt_ask("  Root PID (blank = all) › ", history_key="proc_root")
            try:
                pid = int(root) if root else None
            except ValueError:
                pid = None
            tree = proc_tree(pid)
            console.print(Panel(tree[:6000] + ("\n…" if len(tree) > 6000 else ""),
                                title="Process Tree", border_style="orange1"))

        elif cmd == "port":
            port = _pt_ask("  Port › ", history_key="proc_port")
            if not port:
                continue
            try:
                rows = proc_find_by_port(int(port))
            except ValueError:
                console.print("[yellow]  Port must be a number.[/yellow]")
                continue
            if not rows:
                console.print(f"[yellow]  Nothing listening on port {port}.[/yellow]")
            elif "error" in rows[0]:
                console.print(f"[bright_red]  ✗  {rows[0]['error']}[/bright_red]")
            else:
                _render_list_table(rows, f"Listening on :{port}", [
                    ("pid", "PID"), ("name", "Name"),
                    ("user", "User"), ("addr", "Address"), ("cmd", "Command"),
                ])

        elif cmd == "kill":
            target = _pt_ask("  PID or process name › ", history_key="proc_kill")
            if not target:
                continue
            force = _confirm("  Use SIGKILL (force)?", default=False)
            if not _confirm(f"  Send {'SIGKILL' if force else 'SIGTERM'} to '{target}'?",
                            default=False):
                console.print("[dim]  Cancelled.[/dim]")
                continue
            res = proc_kill(target, force=force)
            for k in res["killed"]:
                console.print(f"[bright_green]  ✓  Killed PID {k['pid']} "
                              f"({k['name']})[/bright_green]")
            for e in res["errors"]:
                console.print(f"[bright_red]  ✗  {e}[/bright_red]")

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


# ── 9. Logs ───────────────────────────────────────────────────────────────────

def _tui_logs(cfg: dict) -> None:
    from modules import log_recent, log_list_units

    L_CHOICES = ["recent", "errors", "unit", "list", "back"]

    while True:
        console.print(Rule("[bold medium_purple]Logs[/bold medium_purple]"))
        if sys.platform == "win32":
            console.print("[dim]  Source: Windows Event Log (System / Application / Security / Setup)[/dim]")
        elif sys.platform == "darwin":
            console.print("[dim]  Source: macOS unified log (last 30 minutes)[/dim]")
        else:
            console.print("[dim]  Source: systemd-journald (journalctl)[/dim]")
        console.print("""
  [bold]recent[/bold]   Last 100 log lines from the system log
  [bold]errors[/bold]   Last 100 ERROR-level entries
  [bold]unit[/bold]     Last 100 entries for a specific service / source
  [bold]list[/bold]     List active services / log sources
  [bold]back[/bold]     Return to main menu
""")
        cmd = _sub_prompt("Logs", L_CHOICES)

        if cmd in ("back", "b", ""):
            break

        elif cmd == "recent":
            res = log_recent(lines=100)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _print_log_lines(res.get("lines", []))

        elif cmd == "errors":
            level = "err" if sys.platform.startswith("linux") else "error"
            res = log_recent(level=level, lines=100)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _print_log_lines(res.get("lines", []))

        elif cmd == "unit":
            units = log_list_units()
            comp = (WordCompleter(units, ignore_case=True)
                    if _HAS_PT and units else None)
            unit = _pt_ask("  Unit / source › ", completer=comp, history_key="log_unit")
            if not unit:
                continue
            res = log_recent(unit=unit, lines=100)
            if res.get("error"):
                console.print(f"[bright_red]  ✗  {res['error']}[/bright_red]")
            else:
                _print_log_lines(res.get("lines", []), title=f"Logs — {unit}")

        elif cmd == "list":
            units = log_list_units()
            if not units:
                console.print("[yellow]  No units / sources detected.[/yellow]")
            else:
                t = Table(box=box.SIMPLE, show_header=False, border_style="dim")
                t.add_column("", style="cyan")
                for u in units[:200]:
                    t.add_row(u)
                console.print(Panel(t, title=f"{len(units)} log unit(s)",
                                    border_style="medium_purple"))

        elif cmd in ("help", "h"):
            print_help()
        else:
            console.print("[yellow]  Unknown command.[/yellow]")

        _pause()


def _print_log_lines(lines: list[str], title: str = "Recent Log Lines") -> None:
    if not lines:
        console.print("[yellow]  No log lines returned.[/yellow]")
        return
    body = Text()
    for line in lines:
        ll = line.lower()
        if any(w in ll for w in (" error", " err ", "fatal", "critical", "panic")):
            color = "bright_red"
        elif any(w in ll for w in (" warn", " warning", " notice")):
            color = "yellow"
        elif " info" in ll or " ok " in ll:
            color = "white"
        else:
            color = "dim white"
        body.append(line + "\n", style=color)
    console.print(Panel(body, title=f"[bold]{title}[/bold]",
                        border_style="medium_purple"))


# ── 10. Settings ──────────────────────────────────────────────────────────────

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
            server  = _pt_ask("  AD Server (e.g. ldap://dc.corp.local) › ",
                              history_key="set_ad") or cfg["ad"]["server"]
            base_dn = _pt_ask("  Base DN (e.g. DC=corp,DC=local) › ",
                              history_key="set_ad") or cfg["ad"]["base_dn"]
            user    = _pt_ask("  Bind user (e.g. CORP\\svc_account) › ",
                              history_key="set_ad") or cfg["ad"]["user"]
            import getpass
            pw_raw = getpass.getpass("  Password (blank to keep existing): ")
            cfg["ad"]["server"]  = server
            cfg["ad"]["base_dn"] = base_dn
            cfg["ad"]["user"]    = user
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
            disk_s   = _pt_ask(f"  Disk warn % [{cfg['morning']['disk_warn_pct']}] › ",
                               history_key="set_morning")
            mem_s    = _pt_ask(f"  Mem warn %  [{cfg['morning']['mem_warn_pct']}] › ",
                               history_key="set_morning")
            cert_s   = _pt_ask(f"  Cert warn days [{cfg['morning']['cert_warn_days']}] › ",
                               history_key="set_morning")
            if ping_raw:
                cfg["morning"]["ping_hosts"] = [
                    h.strip() for h in ping_raw.split(",") if h.strip()
                ]
            for src, key in [(disk_s, "disk_warn_pct"),
                              (mem_s, "mem_warn_pct"),
                              (cert_s, "cert_warn_days")]:
                if src:
                    try:
                        cfg["morning"][key] = int(src)
                    except ValueError:
                        pass
            save_config(cfg)
            console.print("[bright_green]  ✓  Morning settings saved.[/bright_green]")

        elif cmd == "theme":
            cfg["theme"] = "light" if cfg.get("theme") == "dark" else "dark"
            save_config(cfg)
            console.print(f"[bright_green]  ✓  Theme set to [bold]{cfg['theme']}[/bold].[/bright_green]")

        elif cmd == "show":
            import copy, json
            display = copy.deepcopy(cfg)
            display["ad"]["password_enc"]         = "***" if display["ad"]["password_enc"] else "(not set)"
            display["azure"]["client_secret_enc"] = "***" if display["azure"]["client_secret_enc"] else "(not set)"
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
    ("1",  "morning",   "bright_cyan",    "☀  Morning Checklist", "Disk · RAM · CPU · services · ping · certs · HTML report"),
    ("2",  "ad",        "bright_blue",    "🏢  Active Directory",  "Search · unlock · reset · groups"),
    ("3",  "azure",     "blue",           "☁  Azure AD",          "Users · groups · devices · MFA · apps"),
    ("4",  "health",    "bright_green",   "💚  System Health",     "Live watch · CPU · mem · disk · battery · temps"),
    ("5",  "network",   "bright_yellow",  "🌐  Network",           "Ping · port · DNS · trace · HTTP · SSL · WHOIS · scan"),
    ("6",  "cleanup",   "bright_magenta", "🧹  Cleanup",           "Temp · logs · cores · big files · APPLY mode"),
    ("7",  "ssh",       "cyan",           "🔐  SSH Manager",       "Connect · run · add · remove hosts"),
    ("8",  "procs",     "orange1",        "⚙  Processes",         "List · search · kill · find by port · tree"),
    ("9",  "logs",      "medium_purple",  "📜  Logs",              "Journal / Console / Event Log viewer"),
    ("10", "settings",  "bright_white",   "🔧  Settings",          "AD · Azure · morning thresholds · theme"),
]

MODULE_HANDLERS = {
    "morning":   _tui_morning,
    "ad":        _tui_ad,
    "azure":     _tui_azure,
    "health":    _tui_health,
    "network":   _tui_network,
    "cleanup":   _tui_cleanup,
    "ssh":       _tui_ssh,
    "procs":     _tui_processes,
    "processes": _tui_processes,
    "logs":      _tui_logs,
    "settings":  _tui_settings,
}


def _build_menu_panel() -> Panel:
    t = Table(box=box.SIMPLE, show_header=False, border_style="dim",
              padding=(0, 1), expand=True)
    t.add_column("N",    style="bold", no_wrap=True, width=4)
    t.add_column("Name", style="bold", no_wrap=True, min_width=22)
    t.add_column("Desc", style="dim")
    for num, _, color, label, desc in MENU_ITEMS:
        t.add_row(
            Text(num, style=f"bold {color}"),
            Text(label, style=f"bold {color}"),
            Text(desc),
        )
    return Panel(t, title="[bold bright_cyan]Main Menu[/bold bright_cyan]",
                 border_style="bright_cyan",
                 width=min(console.width, 96))


def run_tui(cfg: dict, args: argparse.Namespace) -> None:
    print_banner()

    # --check: non-interactive morning checklist
    if getattr(args, "check", False):
        from modules import (run_morning_checks, report_morning_html,
                             report_morning_json, save_report)
        results = run_morning_checks(cfg)
        _render_results(results, "Morning Checklist")
        report = getattr(args, "report", None)
        if report:
            fmt = "json" if str(report).endswith(".json") else "html"
            content = (report_morning_json(cfg, results) if fmt == "json"
                       else report_morning_html(cfg, results))
            path = save_report(content, fmt, report if isinstance(report, str)
                                                       and report not in ("", "auto")
                                                       else None)
            console.print(f"[bright_green]  ✓  Report saved to:[/bright_green] {path}")
        fails = [r for r in results if r.status == "fail"]
        sys.exit(1 if fails else 0)

    # --module morning + --watch on health
    if getattr(args, "module", None):
        m = args.module.lower()
        if m in MODULE_HANDLERS:
            if m == "health" and getattr(args, "watch", False):
                _tui_health_watch()
                return
            MODULE_HANDLERS[m](cfg)
        else:
            console.print(f"[yellow]Unknown module: {args.module}[/yellow]")
        return

    nums = [n for n, *_ in MENU_ITEMS]
    names = [m for _, m, *_ in MENU_ITEMS] + ["procs", "processes"]
    comp_vals = nums + names + ["help", "h", "quit", "q"]
    comp = WordCompleter(comp_vals, ignore_case=True) if _HAS_PT else None

    while True:
        console.print(Align.center(_status_bar()))
        console.print(Align.center(_build_menu_panel()))
        console.print("[dim]  h help  ·  q quit  ·  Tab complete  ·  ↑↓ history[/dim]\n")

        try:
            choice = _pt_ask(
                "  › ",
                completer=comp,
                history_key="main_menu",
                placeholder="1-10  ·  module name  ·  h for help",
            ).lower().strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Use 'q' to quit.[/dim]")
            continue

        if not choice:
            continue
        if choice in ("q", "quit", "exit"):
            console.print("\n[bold bright_cyan]  Goodbye. Stay sane out there. ⚔[/bold bright_cyan]\n")
            sys.exit(0)
        if choice in ("h", "help"):
            print_help()
            continue

        matched = None
        for num, name, *_ in MENU_ITEMS:
            if choice == num or choice == name:
                matched = name
                break
        if not matched and choice in ("processes",):
            matched = "procs"

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
            console.print(f"[yellow]  Unknown: '{choice}'. Type 1-10 or a module name.[/yellow]")
