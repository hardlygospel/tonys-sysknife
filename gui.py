#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 Tony (hardlygospel) — https://github.com/hardlygospel
"""
Tony's Sysadmin Swiss Army Knife — GUI (Windows, tkinter)
Catppuccin Mocha dark theme. Sidebar nav + content panels.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Any, Callable

# ── Catppuccin Mocha palette ──────────────────────────────────────────────────
BG      = "#1e1e2e"
BG2     = "#181825"
SURFACE = "#313244"
OVERLAY = "#45475a"
TEXT    = "#cdd6f4"
SUBTEXT = "#a6adc8"
BLUE    = "#89b4fa"
CYAN    = "#89dceb"
GREEN   = "#a6e3a1"
YELLOW  = "#f9e2af"
ORANGE  = "#fab387"
RED     = "#f38ba8"
PINK    = "#f5c2e7"
MAUVE   = "#cba6f7"
TEAL    = "#94e2d5"

SIDEBAR_W = 200
HEADER_H  = 64

MODULE_COLORS = {
    "Morning":   CYAN,
    "AD":        BLUE,
    "Azure":     MAUVE,
    "Health":    GREEN,
    "Network":   YELLOW,
    "Cleanup":   PINK,
    "SSH":       TEAL,
    "Settings":  SUBTEXT,
}

MODULE_ICONS = {
    "Morning":   "☀",
    "AD":        "🏢",
    "Azure":     "☁",
    "Health":    "💚",
    "Network":   "🌐",
    "Cleanup":   "🧹",
    "SSH":       "🔐",
    "Settings":  "⚙",
}


# ── utility ────────────────────────────────────────────────────────────────────

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _run_bg(fn: Callable, *args, on_done: Callable | None = None) -> None:
    def _worker():
        result = fn(*args)
        if on_done:
            on_done(result)
    threading.Thread(target=_worker, daemon=True).start()


# ── base panel ────────────────────────────────────────────────────────────────

class BasePanel(tk.Frame):
    def __init__(self, parent: tk.Widget, cfg: dict, app: "SysknifeApp"):
        super().__init__(parent, bg=BG)
        self.cfg = cfg
        self.app = app
        self._build()

    def _build(self) -> None:
        pass

    def _section(self, title: str) -> tk.Label:
        lbl = tk.Label(self, text=title, bg=BG, fg=MAUVE,
                       font=("Segoe UI", 11, "bold"), anchor="w")
        lbl.pack(fill="x", padx=16, pady=(12, 4))
        return lbl

    def _output(self, height: int = 20) -> scrolledtext.ScrolledText:
        st = scrolledtext.ScrolledText(
            self, height=height, bg=BG2, fg=TEXT,
            font=("Cascadia Code", 9) if sys.platform == "win32" else ("Menlo", 10),
            insertbackground=TEXT, selectbackground=OVERLAY,
            relief="flat", borderwidth=0,
        )
        st.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        st.config(state="disabled")
        return st

    def _write(self, widget: scrolledtext.ScrolledText, text: str,
               color: str = TEXT, clear: bool = False) -> None:
        widget.config(state="normal")
        if clear:
            widget.delete("1.0", "end")
        widget.insert("end", text, ("col",))
        widget.tag_config("col", foreground=color)
        widget.see("end")
        widget.config(state="disabled")

    def _append(self, widget: scrolledtext.ScrolledText, text: str,
                color: str = TEXT) -> None:
        self._write(widget, text, color, clear=False)

    def _btn(self, parent: tk.Widget, label: str,
             command: Callable, color: str = BLUE) -> tk.Button:
        b = tk.Button(
            parent, text=label, command=command,
            bg=SURFACE, fg=color, activebackground=OVERLAY,
            activeforeground=color, relief="flat",
            font=("Segoe UI", 9, "bold"), padx=12, pady=6, cursor="hand2",
        )
        b.pack(side="left", padx=(0, 8))
        return b

    def _labeled_entry(self, parent: tk.Widget, label: str,
                       show: str = "") -> tuple[tk.Label, tk.Entry]:
        lbl = tk.Label(parent, text=label, bg=BG, fg=SUBTEXT,
                       font=("Segoe UI", 9), anchor="w")
        lbl.pack(fill="x")
        ent = tk.Entry(parent, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                       relief="flat", font=("Segoe UI", 10), show=show)
        ent.pack(fill="x", pady=(0, 6))
        return lbl, ent

    def _status_color(self, status: str) -> str:
        return {
            "ok":   GREEN,
            "warn": YELLOW,
            "fail": RED,
            "skip": SUBTEXT,
            "info": CYAN,
        }.get(status, TEXT)


# ── Morning Checklist ─────────────────────────────────────────────────────────

class MorningPanel(BasePanel):
    def _build(self) -> None:
        self._section("Morning Checklist")
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(btn_row, "Run All Checks", self._run, CYAN)
        self.out = self._output(22)

    def _run(self) -> None:
        self._write(self.out, "Running checks…\n", CYAN, clear=True)
        self.app.set_status("Running morning checklist…")

        def _go():
            from modules import run_morning_checks
            return run_morning_checks(self.cfg)

        def _done(results):
            self.out.config(state="normal")
            self.out.delete("1.0", "end")
            icons = {"ok": "✓", "warn": "⚠", "fail": "✗", "skip": "·", "info": "●"}
            fails = 0
            for r in results:
                color = self._status_color(r.status)
                icon  = icons.get(r.status, "?")
                line  = f" {icon}  {r.name:<22} {r.detail}\n"
                self.out.insert("end", line, ("col",))
                self.out.tag_config("col", foreground=color)
                if r.status == "fail":
                    fails += 1
            self.out.see("end")
            self.out.config(state="disabled")
            self.app.set_status(
                f"Morning checklist done — {fails} failure(s)" if fails
                else "Morning checklist — all clear ✓"
            )

        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))


# ── Active Directory ──────────────────────────────────────────────────────────

class ADPanel(BasePanel):
    def _build(self) -> None:
        from sysknife import ad_configured
        if not ad_configured(self.cfg):
            tk.Label(self, text="AD not configured. Go to Settings → AD.",
                     bg=BG, fg=YELLOW, font=("Segoe UI", 10)).pack(pady=20)
            return

        self._section("Active Directory")
        # Search row
        sf = tk.Frame(self, bg=BG)
        sf.pack(fill="x", padx=16, pady=(0, 8))
        self.search_var = tk.StringVar()
        tk.Label(sf, text="Username / Name:", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(sf, textvariable=self.search_var, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 font=("Segoe UI", 10), width=28).pack(side="left", padx=(6, 0))
        self._btn(sf, "Search", self._search, BLUE)

        # Action buttons
        ab = tk.Frame(self, bg=BG)
        ab.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(ab, "Unlock",  self._unlock,  YELLOW)
        self._btn(ab, "Enable",  self._enable,  GREEN)
        self._btn(ab, "Disable", self._disable, RED)
        self._btn(ab, "Reset PW", self._reset,  ORANGE)

        self.out = self._output(18)

    def _search(self) -> None:
        q = self.search_var.get().strip()
        if not q:
            return
        self._write(self.out, f"Searching for '{q}'…\n", CYAN, clear=True)
        from modules import ad_search_user

        def _go():
            return ad_search_user(self.cfg, q)

        def _done(res):
            self.out.config(state="normal")
            self.out.delete("1.0", "end")
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            elif res.get("users"):
                hdr = f"{'Username':<20} {'Display Name':<28} {'Email':<32} {'En':3} {'Locked':6}\n"
                self._append(self.out, hdr, MAUVE)
                self._append(self.out, "─" * len(hdr) + "\n", OVERLAY)
                for u in res["users"]:
                    line = (f"{u.get('sAMAccountName',''):<20} "
                            f"{u.get('displayName',''):<28} "
                            f"{u.get('mail',''):<32} "
                            f"{str(u.get('enabled','')):<3} "
                            f"{str(u.get('locked','')):<6}\n")
                    self._append(self.out, line, TEXT)
            else:
                self._append(self.out, "No results.\n", YELLOW)
            self.out.see("end")
            self.out.config(state="disabled")

        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _get_user(self) -> str | None:
        return simpledialog.askstring("sAMAccountName", "Enter sAMAccountName:", parent=self)

    def _unlock(self) -> None:
        user = self._get_user()
        if not user:
            return
        from modules import ad_unlock_account
        def _go(): return ad_unlock_account(self.cfg, user)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, f"✓  {res.get('message','Done')}\n", GREEN)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _enable(self) -> None:
        user = self._get_user()
        if not user:
            return
        from modules import ad_set_account_enabled
        def _go(): return ad_set_account_enabled(self.cfg, user, True)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, f"✓  {res.get('message','Done')}\n", GREEN)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _disable(self) -> None:
        user = self._get_user()
        if not user:
            return
        if not messagebox.askyesno("Disable Account", f"Disable account: {user}?"):
            return
        from modules import ad_set_account_enabled
        def _go(): return ad_set_account_enabled(self.cfg, user, False)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, f"✓  {res.get('message','Done')}\n", GREEN)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _reset(self) -> None:
        user = self._get_user()
        if not user:
            return
        pw = simpledialog.askstring("New Password", f"New password for {user}:",
                                    show="*", parent=self)
        if not pw:
            return
        from modules import ad_reset_password
        def _go(): return ad_reset_password(self.cfg, user, pw)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, f"✓  {res.get('message','Done')}\n", GREEN)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))


# ── Azure AD ──────────────────────────────────────────────────────────────────

class AzurePanel(BasePanel):
    def _build(self) -> None:
        from sysknife import az_configured
        if not az_configured(self.cfg):
            tk.Label(self, text="Azure AD not configured. Go to Settings → Azure.",
                     bg=BG, fg=YELLOW, font=("Segoe UI", 10)).pack(pady=20)
            return

        self._section("Azure AD")
        ab = tk.Frame(self, bg=BG)
        ab.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(ab, "List Users",   self._list_users,   MAUVE)
        self._btn(ab, "List Groups",  self._list_groups,  BLUE)
        self._btn(ab, "List Devices", self._list_devices, CYAN)
        self._btn(ab, "List Apps",    self._list_apps,    TEAL)

        ab2 = tk.Frame(self, bg=BG)
        ab2.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(ab2, "Enable User",  lambda: self._set_enabled(True),  GREEN)
        self._btn(ab2, "Disable User", lambda: self._set_enabled(False), RED)
        self._btn(ab2, "MFA Status",   self._mfa,                        YELLOW)

        self.out = self._output(18)

    def _list_users(self) -> None:
        flt = simpledialog.askstring("Filter", "Name/UPN filter (blank=all):", parent=self) or None
        from modules import az_list_users
        self._write(self.out, "Fetching users…\n", CYAN, clear=True)

        def _go(): return az_list_users(self.cfg, flt)
        def _done(res):
            self.out.config(state="normal")
            self.out.delete("1.0", "end")
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                for u in res.get("users", []):
                    line = (f"  {u.get('displayName',''):<28} "
                            f"{u.get('userPrincipalName',''):<40} "
                            f"{'Enabled' if u.get('accountEnabled') else 'Disabled'}\n")
                    self._append(self.out, line, TEXT)
            self.out.config(state="disabled")
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _list_groups(self) -> None:
        from modules import az_list_groups
        self._write(self.out, "Fetching groups…\n", CYAN, clear=True)
        def _go(): return az_list_groups(self.cfg, None)
        def _done(res):
            self.out.config(state="normal")
            self.out.delete("1.0", "end")
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                for g in res.get("groups", []):
                    self._append(self.out, f"  {g.get('displayName','')}\n", TEXT)
            self.out.config(state="disabled")
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _list_devices(self) -> None:
        from modules import az_list_devices
        self._write(self.out, "Fetching devices…\n", CYAN, clear=True)
        def _go(): return az_list_devices(self.cfg)
        def _done(res):
            self.out.config(state="normal")
            self.out.delete("1.0", "end")
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                for d in res.get("devices", []):
                    self._append(self.out,
                        f"  {d.get('displayName',''):<30} "
                        f"{d.get('operatingSystem','')}\n", TEXT)
            self.out.config(state="disabled")
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _list_apps(self) -> None:
        from modules import az_list_apps
        self._write(self.out, "Fetching apps…\n", CYAN, clear=True)
        def _go(): return az_list_apps(self.cfg)
        def _done(res):
            self.out.config(state="normal")
            self.out.delete("1.0", "end")
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                for a in res.get("apps", []):
                    self._append(self.out, f"  {a.get('displayName','')}\n", TEXT)
            self.out.config(state="disabled")
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _set_enabled(self, enabled: bool) -> None:
        label = "Enable" if enabled else "Disable"
        upn = simpledialog.askstring(label, f"UPN or object ID to {label.lower()}:", parent=self)
        if not upn:
            return
        from modules import az_set_user_enabled
        def _go(): return az_set_user_enabled(self.cfg, upn, enabled)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, f"✓  {res.get('message','Done')}\n", GREEN)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _mfa(self) -> None:
        upn = simpledialog.askstring("MFA Status", "UPN or object ID:", parent=self)
        if not upn:
            return
        from modules import az_user_mfa_status
        def _go(): return az_user_mfa_status(self.cfg, upn)
        def _done(res):
            self.out.config(state="normal")
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                for k, v in res.items():
                    self._append(self.out, f"  {k:<30} {v}\n", TEXT)
            self.out.config(state="disabled")
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))


# ── System Health ─────────────────────────────────────────────────────────────

class HealthPanel(BasePanel):
    def _build(self) -> None:
        self._section("System Health")
        ab = tk.Frame(self, bg=BG)
        ab.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(ab, "CPU",      self._cpu,      GREEN)
        self._btn(ab, "Memory",   self._mem,      CYAN)
        self._btn(ab, "Disk",     self._disk,     BLUE)
        self._btn(ab, "Procs",    self._procs,    YELLOW)
        self._btn(ab, "Net I/O",  self._netio,    MAUVE)
        self._btn(ab, "Services", self._services, TEAL)
        self._btn(ab, "All",      self._all,      ORANGE)
        self.out = self._output(20)

    def _show_dict(self, title: str, d: dict) -> None:
        self._write(self.out, f"── {title} ──\n", MAUVE, clear=True)
        for k, v in d.items():
            self._append(self.out, f"  {k:<26} {v}\n", TEXT)

    def _cpu(self) -> None:
        from modules import health_cpu
        def _go(): return health_cpu()
        def _done(r): self.after(0, self._show_dict, "CPU", r)
        _run_bg(_go, on_done=_done)

    def _mem(self) -> None:
        from modules import health_memory
        def _go(): return health_memory()
        def _done(r): self.after(0, self._show_dict, "Memory", r)
        _run_bg(_go, on_done=_done)

    def _disk(self) -> None:
        from modules import health_disk
        self._write(self.out, "── Disk ──\n", MAUVE, clear=True)
        def _go(): return health_disk()
        def _done(rows):
            for row in rows:
                self._append(self.out,
                    f"  {row.get('mountpoint',''):<18} {row.get('used',''):<10} "
                    f"/ {row.get('total',''):<10} ({row.get('percent','')}%)\n",
                    GREEN if float(str(row.get('percent',0)).rstrip('%') or 0) < 80 else YELLOW,
                )
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _procs(self) -> None:
        from modules import health_top_processes
        self._write(self.out, "── Top Processes ──\n", MAUVE, clear=True)
        def _go(): return health_top_processes(10)
        def _done(rows):
            self._append(self.out,
                f"  {'PID':<7} {'Name':<22} {'CPU%':<8} {'Mem%':<8}\n", SUBTEXT)
            for row in rows:
                self._append(self.out,
                    f"  {str(row.get('pid','')):<7} {row.get('name',''):<22} "
                    f"{str(row.get('cpu','')):<8} {str(row.get('mem','')):<8}\n", TEXT)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _netio(self) -> None:
        from modules import health_network_io
        self._write(self.out, "── Network I/O ──\n", MAUVE, clear=True)
        def _go(): return health_network_io()
        def _done(rows):
            for row in rows:
                self._append(self.out,
                    f"  {row.get('iface',''):<16} "
                    f"↓ {row.get('bytes_recv',''):<12} "
                    f"↑ {row.get('bytes_sent','')}\n", TEXT)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _services(self) -> None:
        from modules import health_services
        self._write(self.out, "── Services ──\n", MAUVE, clear=True)
        def _go(): return health_services()
        def _done(results):
            icons = {"ok": "✓", "warn": "⚠", "fail": "✗", "skip": "·"}
            for r in results:
                color = self._status_color(r.status)
                self._append(self.out,
                    f"  {icons.get(r.status,'?')}  {r.name:<24} {r.detail}\n", color)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _all(self) -> None:
        self._write(self.out, "Running all health checks…\n", CYAN, clear=True)
        self._cpu()
        self.after(500, self._mem)
        self.after(1000, self._disk)
        self.after(1500, self._services)


# ── Network ───────────────────────────────────────────────────────────────────

class NetworkPanel(BasePanel):
    def _build(self) -> None:
        self._section("Network")
        form = tk.Frame(self, bg=BG)
        form.pack(fill="x", padx=16, pady=(0, 8))
        _, self.host_ent = self._labeled_entry(form, "Host / IP:")
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(btn_row, "Ping",        self._ping,  YELLOW)
        self._btn(btn_row, "Ping All",    self._ping_all, ORANGE)
        self._btn(btn_row, "Port Check",  self._port,  CYAN)
        self._btn(btn_row, "DNS Lookup",  self._dns,   BLUE)
        self._btn(btn_row, "Traceroute",  self._trace, MAUVE)
        self.out = self._output(18)

    def _host(self) -> str:
        return self.host_ent.get().strip()

    def _ping(self) -> None:
        host = self._host()
        if not host:
            messagebox.showwarning("No host", "Enter a host first.")
            return
        from modules import net_ping
        self._write(self.out, f"Pinging {host}…\n", CYAN, clear=True)
        def _go(): return net_ping(host)
        def _done(r):
            color = GREEN if r.status == "ok" else RED
            self._append(self.out, f"{r.detail}\n", color)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _ping_all(self) -> None:
        hosts = self.cfg.get("morning", {}).get("ping_hosts", [])
        if not hosts:
            messagebox.showinfo("No hosts", "No morning ping hosts configured in Settings.")
            return
        from modules import net_ping
        self._write(self.out, "Pinging configured hosts…\n", CYAN, clear=True)
        for host in hosts:
            def _go(h=host): return net_ping(h)
            def _done(r):
                color = GREEN if r.status == "ok" else RED
                self._append(self.out, f"  {r.name}: {r.detail}\n", color)
            _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _port(self) -> None:
        host = self._host()
        if not host:
            messagebox.showwarning("No host", "Enter a host first.")
            return
        port_s = simpledialog.askstring("Port", "TCP port number:", parent=self)
        if not port_s:
            return
        try:
            port = int(port_s)
        except ValueError:
            messagebox.showerror("Bad port", "Port must be a number.")
            return
        from modules import net_port_check
        self._write(self.out, f"Checking {host}:{port}…\n", CYAN, clear=True)
        def _go(): return net_port_check(host, port)
        def _done(r):
            color = GREEN if r.status == "ok" else RED
            self._append(self.out, f"{r.detail}\n", color)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _dns(self) -> None:
        host = self._host()
        if not host:
            messagebox.showwarning("No host", "Enter a host first.")
            return
        from modules import net_dns_lookup
        self._write(self.out, f"DNS lookup: {host}…\n", CYAN, clear=True)
        def _go(): return net_dns_lookup(host, "A")
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                for rec in res.get("records", []):
                    self._append(self.out, f"  {rec}\n", TEXT)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _trace(self) -> None:
        host = self._host()
        if not host:
            messagebox.showwarning("No host", "Enter a host first.")
            return
        from modules import net_traceroute
        self._write(self.out, f"Tracerouting {host}…\n", CYAN, clear=True)
        def _go(): return net_traceroute(host)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._write(self.out, res.get("output", ""), TEXT, clear=True)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))


# ── Cleanup ───────────────────────────────────────────────────────────────────

class CleanupPanel(BasePanel):
    def _build(self) -> None:
        self._section("Cleanup")
        ab = tk.Frame(self, bg=BG)
        ab.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(ab, "Temp Files",  self._temp,    PINK)
        self._btn(ab, "Logs",        self._logs,    YELLOW)
        self._btn(ab, "Core Dumps",  self._cores,   RED)
        self._btn(ab, "Pkg Cache",   self._pkgcache, ORANGE)
        self._btn(ab, "Trash",       self._trash,   MAUVE)
        self._btn(ab, "Run All",     self._all,     CYAN)
        self.out = self._output(20)

    def _run_task(self, fn, title: str) -> None:
        self._write(self.out, f"Running {title}…\n", CYAN, clear=True)
        def _done(r):
            color = self._status_color(r.status)
            self._append(self.out, f"{r.detail}\n", color)
        _run_bg(fn, on_done=lambda r: self.after(0, _done, r))

    def _temp(self) -> None:
        from modules import cleanup_temp_files
        self._run_task(cleanup_temp_files, "temp cleanup")

    def _logs(self) -> None:
        from modules import cleanup_old_logs
        self._run_task(cleanup_old_logs, "log rotation")

    def _cores(self) -> None:
        from modules import cleanup_cores
        self._run_task(cleanup_cores, "core dump cleanup")

    def _pkgcache(self) -> None:
        from modules import cleanup_package_cache
        self._run_task(cleanup_package_cache, "package cache cleanup")

    def _trash(self) -> None:
        from modules import cleanup_trash
        if messagebox.askyesno("Empty Trash", "Empty Trash / Recycle Bin?"):
            self._run_task(cleanup_trash, "trash empty")

    def _all(self) -> None:
        from modules import (
            cleanup_temp_files, cleanup_old_logs, cleanup_cores,
            cleanup_package_cache, cleanup_trash,
        )
        self._write(self.out, "Running all cleanup tasks…\n", CYAN, clear=True)
        tasks = [cleanup_temp_files, cleanup_old_logs, cleanup_cores,
                 cleanup_package_cache, cleanup_trash]
        def _go():
            return [fn() for fn in tasks]
        def _done(results):
            for r in results:
                color = self._status_color(r.status)
                icon = {"ok": "✓", "warn": "⚠", "fail": "✗"}.get(r.status, "·")
                self._append(self.out, f"  {icon}  {r.name:<24} {r.detail}\n", color)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))


# ── SSH Manager ───────────────────────────────────────────────────────────────

class SSHPanel(BasePanel):
    def _build(self) -> None:
        self._section("SSH Manager")
        ab = tk.Frame(self, bg=BG)
        ab.pack(fill="x", padx=16, pady=(0, 8))
        self._btn(ab, "List",    self._list,    TEAL)
        self._btn(ab, "Connect", self._connect, CYAN)
        self._btn(ab, "Run Cmd", self._run_cmd, BLUE)
        self._btn(ab, "Add",     self._add,     GREEN)
        self._btn(ab, "Remove",  self._remove,  RED)
        self.out = self._output(20)

    def _list(self) -> None:
        hosts = self.cfg.get("ssh_hosts", [])
        self._write(self.out, "── Saved SSH Hosts ──\n", TEAL, clear=True)
        if not hosts:
            self._append(self.out, "  No hosts configured.\n", SUBTEXT)
        else:
            self._append(self.out,
                f"  {'Alias':<16} {'Host':<28} {'Port':<6} {'User'}\n", SUBTEXT)
            for h in hosts:
                self._append(self.out,
                    f"  {h.get('alias',''):<16} {h.get('hostname',''):<28} "
                    f"{str(h.get('port',22)):<6} {h.get('username','')}\n", TEXT)

    def _aliases(self) -> list[str]:
        return [h["alias"] for h in self.cfg.get("ssh_hosts", [])]

    def _pick_alias(self) -> str | None:
        aliases = self._aliases()
        if not aliases:
            messagebox.showinfo("No hosts", "No SSH hosts saved. Use Add first.")
            return None
        return simpledialog.askstring(
            "Alias", f"Alias (available: {', '.join(aliases)}):", parent=self)

    def _connect(self) -> None:
        alias = self._pick_alias()
        if not alias:
            return
        pw = simpledialog.askstring("Password", "Password (blank for key auth):",
                                    show="*", parent=self) or None
        from modules import ssh_connect
        self._write(self.out, f"Connecting to '{alias}'…\n", CYAN, clear=True)
        def _go(): return ssh_connect(self.cfg, alias, password=pw)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, f"✓  {res.get('message','Connected')}\n", GREEN)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _run_cmd(self) -> None:
        alias = self._pick_alias()
        if not alias:
            return
        cmd = simpledialog.askstring("Command", "Command to run:", parent=self)
        if not cmd:
            return
        pw = simpledialog.askstring("Password", "Password (blank for key auth):",
                                    show="*", parent=self) or None
        from modules import ssh_run_command
        self._write(self.out, f"Running on '{alias}': {cmd}\n", CYAN, clear=True)
        def _go(): return ssh_run_command(self.cfg, alias, cmd, password=pw)
        def _done(res):
            if res.get("error"):
                self._append(self.out, f"✗  {res['error']}\n", RED)
            else:
                self._append(self.out, res.get("stdout", ""), TEXT)
                if res.get("stderr"):
                    self._append(self.out, "\nstderr:\n" + res["stderr"], YELLOW)
        _run_bg(_go, on_done=lambda r: self.after(0, _done, r))

    def _add(self) -> None:
        alias    = simpledialog.askstring("Alias",    "Short alias:", parent=self)
        hostname = simpledialog.askstring("Host",     "Hostname or IP:", parent=self)
        port_s   = simpledialog.askstring("Port",     "Port [22]:", parent=self) or "22"
        username = simpledialog.askstring("Username", "Username:", parent=self)
        key_path = simpledialog.askstring("Key",      "SSH key path (blank=none):", parent=self) or ""
        if not alias or not hostname or not username:
            messagebox.showwarning("Missing", "Alias, hostname, and username are required.")
            return
        try:
            port = int(port_s)
        except ValueError:
            port = 22
        from modules import ssh_add_host
        self.cfg = ssh_add_host(self.cfg, alias, hostname, port, username, key_path)
        self._write(self.out, f"✓  Host '{alias}' saved.\n", GREEN, clear=True)

    def _remove(self) -> None:
        alias = self._pick_alias()
        if not alias:
            return
        if messagebox.askyesno("Remove", f"Remove host '{alias}'?"):
            from modules import ssh_remove_host
            self.cfg = ssh_remove_host(self.cfg, alias)
            self._write(self.out, f"✓  '{alias}' removed.\n", GREEN, clear=True)


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsPanel(BasePanel):
    def _build(self) -> None:
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=BG)
        self.inner.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._build_ad()
        self._build_azure()
        self._build_morning()
        self._build_save()

    def _entry_row(self, parent, label: str, default: str = "",
                   show: str = "") -> tk.Entry:
        tk.Label(parent, text=label, bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        ent = tk.Entry(parent, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                       relief="flat", font=("Segoe UI", 10), show=show)
        ent.insert(0, default)
        ent.pack(fill="x", pady=(0, 6))
        return ent

    def _build_ad(self) -> None:
        f = tk.LabelFrame(self.inner, text="  Active Directory  ",
                          bg=BG, fg=BLUE, font=("Segoe UI", 10, "bold"),
                          relief="flat", bd=1, highlightbackground=SURFACE,
                          highlightthickness=1)
        f.pack(fill="x", padx=16, pady=(16, 0))
        inner = tk.Frame(f, bg=BG, padx=12, pady=8)
        inner.pack(fill="x")
        ad = self.cfg["ad"]
        self.ad_server   = self._entry_row(inner, "Server (e.g. ldap://dc.corp.local):", ad.get("server", ""))
        self.ad_base_dn  = self._entry_row(inner, "Base DN (e.g. DC=corp,DC=local):", ad.get("base_dn", ""))
        self.ad_user     = self._entry_row(inner, "Bind User (e.g. CORP\\svc):", ad.get("user", ""))
        self.ad_password = self._entry_row(inner, "Password:", show="*")

    def _build_azure(self) -> None:
        f = tk.LabelFrame(self.inner, text="  Azure AD  ",
                          bg=BG, fg=MAUVE, font=("Segoe UI", 10, "bold"),
                          relief="flat", bd=1, highlightbackground=SURFACE,
                          highlightthickness=1)
        f.pack(fill="x", padx=16, pady=(16, 0))
        inner = tk.Frame(f, bg=BG, padx=12, pady=8)
        inner.pack(fill="x")
        az = self.cfg["azure"]
        self.az_tenant = self._entry_row(inner, "Tenant ID:", az.get("tenant_id", ""))
        self.az_client = self._entry_row(inner, "Client ID:", az.get("client_id", ""))
        self.az_secret = self._entry_row(inner, "Client Secret:", show="*")

    def _build_morning(self) -> None:
        f = tk.LabelFrame(self.inner, text="  Morning Checklist  ",
                          bg=BG, fg=CYAN, font=("Segoe UI", 10, "bold"),
                          relief="flat", bd=1, highlightbackground=SURFACE,
                          highlightthickness=1)
        f.pack(fill="x", padx=16, pady=(16, 0))
        inner = tk.Frame(f, bg=BG, padx=12, pady=8)
        inner.pack(fill="x")
        m = self.cfg.get("morning", {})
        ping_default = ", ".join(m.get("ping_hosts", []))
        self.ping_hosts  = self._entry_row(inner, "Ping hosts (comma-separated):", ping_default)
        self.disk_warn   = self._entry_row(inner, "Disk warn %:", str(m.get("disk_warn_pct", 85)))
        self.mem_warn    = self._entry_row(inner, "Memory warn %:", str(m.get("mem_warn_pct", 90)))
        self.cert_warn   = self._entry_row(inner, "Cert warn days:", str(m.get("cert_warn_days", 30)))

    def _build_save(self) -> None:
        bf = tk.Frame(self.inner, bg=BG)
        bf.pack(fill="x", padx=16, pady=16)
        tk.Button(
            bf, text="  Save Settings  ",
            command=self._save,
            bg=MAUVE, fg=BG, activebackground=PINK, activeforeground=BG,
            font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=8,
            cursor="hand2",
        ).pack(side="left")

    def _save(self) -> None:
        from sysknife import save_config, cfg_encode

        self.cfg["ad"]["server"]  = self.ad_server.get().strip()
        self.cfg["ad"]["base_dn"] = self.ad_base_dn.get().strip()
        self.cfg["ad"]["user"]    = self.ad_user.get().strip()
        pw = self.ad_password.get()
        if pw:
            self.cfg["ad"]["password_enc"] = cfg_encode(pw)

        self.cfg["azure"]["tenant_id"] = self.az_tenant.get().strip()
        self.cfg["azure"]["client_id"] = self.az_client.get().strip()
        secret = self.az_secret.get()
        if secret:
            self.cfg["azure"]["client_secret_enc"] = cfg_encode(secret)

        ping_raw = self.ping_hosts.get().strip()
        if ping_raw:
            self.cfg["morning"]["ping_hosts"] = [h.strip() for h in ping_raw.split(",") if h.strip()]
        try:
            self.cfg["morning"]["disk_warn_pct"] = int(self.disk_warn.get())
        except ValueError:
            pass
        try:
            self.cfg["morning"]["mem_warn_pct"] = int(self.mem_warn.get())
        except ValueError:
            pass
        try:
            self.cfg["morning"]["cert_warn_days"] = int(self.cert_warn.get())
        except ValueError:
            pass

        save_config(self.cfg)
        messagebox.showinfo("Saved", "Settings saved to ~/.sysknife/config.json")


# ── Main Application ──────────────────────────────────────────────────────────

PANELS = [
    ("Morning",   MorningPanel,  "☀"),
    ("AD",        ADPanel,       "🏢"),
    ("Azure",     AzurePanel,    "☁"),
    ("Health",    HealthPanel,   "💚"),
    ("Network",   NetworkPanel,  "🌐"),
    ("Cleanup",   CleanupPanel,  "🧹"),
    ("SSH",       SSHPanel,      "🔐"),
    ("Settings",  SettingsPanel, "⚙"),
]


class SysknifeApp(tk.Tk):
    def __init__(self, cfg: dict, args: argparse.Namespace):
        super().__init__()
        self.cfg  = cfg
        self.args = args
        self.title("Tony's Sysadmin Swiss Army Knife")
        self.configure(bg=BG2)
        self.geometry("1100x720")
        self.minsize(800, 560)

        self._apply_style()
        self._build_header()
        self._build_body()
        self._show_panel("Morning")

        if getattr(args, "module", None):
            name = args.module.strip().title()
            if name == "Ad":
                name = "AD"
            self._show_panel(name)

    def _apply_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar",
                        background=OVERLAY, troughcolor=BG2,
                        arrowcolor=SUBTEXT, bordercolor=BG2)

    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=BG2, height=HEADER_H)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        title_f = tk.Frame(hdr, bg=BG2)
        title_f.pack(side="left", padx=20, pady=12)
        tk.Label(title_f, text="Tony's Sysadmin Swiss Army Knife",
                 bg=BG2, fg=CYAN, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(title_f, text="v1.0.0  ·  Morning Checklist · AD · Azure · Health · Network · Cleanup · SSH",
                 bg=BG2, fg=SUBTEXT, font=("Segoe UI", 9)).pack(anchor="w")

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(hdr, textvariable=self.status_var,
                 bg=BG2, fg=SUBTEXT, font=("Segoe UI", 9)).pack(side="right", padx=20)

    def _build_body(self) -> None:
        body = tk.Frame(self, bg=BG2)
        body.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(body, bg=BG, width=SIDEBAR_W)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        sep = tk.Frame(body, bg=SURFACE, width=1)
        sep.pack(side="left", fill="y")

        self.content = tk.Frame(body, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self._active_btn: tk.Button | None = None
        self._panels: dict[str, BasePanel] = {}

        tk.Label(self.sidebar, text="MODULES", bg=BG, fg=OVERLAY,
                 font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(fill="x", padx=16, pady=(16, 8))

        for name, PanelClass, icon in PANELS:
            color = MODULE_COLORS.get(name, SUBTEXT)
            btn = tk.Button(
                self.sidebar,
                text=f"  {icon}  {name}",
                command=lambda n=name: self._show_panel(n),
                bg=BG, fg=color,
                activebackground=SURFACE, activeforeground=color,
                relief="flat", anchor="w",
                font=("Segoe UI", 10), padx=8, pady=8,
                cursor="hand2",
                bd=0,
            )
            btn.pack(fill="x", padx=4)
            btn._panel_name = name
            btn._color      = color

        # Create all panels (hidden until selected)
        for name, PanelClass, _ in PANELS:
            p = PanelClass(self.content, self.cfg, self)
            p.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._panels[name] = p

    def _show_panel(self, name: str) -> None:
        panel = self._panels.get(name)
        if panel:
            panel.lift()
        # Update sidebar highlight
        for widget in self.sidebar.winfo_children():
            if isinstance(widget, tk.Button) and hasattr(widget, "_panel_name"):
                if widget._panel_name == name:
                    widget.configure(bg=SURFACE)
                else:
                    widget.configure(bg=BG)
        self.set_status(f"{name}")

    def set_status(self, msg: str) -> None:
        self.status_var.set(msg)


# ── entry ──────────────────────────────────────────────────────────────────────

def run_gui(cfg: dict, args: argparse.Namespace) -> None:
    app = SysknifeApp(cfg, args)
    app.mainloop()
