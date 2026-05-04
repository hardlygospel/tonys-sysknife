#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 Tony (hardlygospel)
"""
All sysadmin module logic — no UI, no console output.
Public functions return plain dicts / lists / CheckResult so both the TUI
and GUI can render them. Private helpers are prefixed with _.
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MAC     = sys.platform == "darwin"


# ── shared ────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name:   str
    status: str        # "ok" | "warn" | "fail" | "skip" | "info"
    detail: str
    value:  Any = None
    items:  list = field(default_factory=list)


def _fmt_bytes(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _optional(pkg: str, mod: str):
    """Import optional dependency or raise helpful RuntimeError."""
    try:
        return __import__(mod)
    except ImportError:
        raise RuntimeError(f"Optional package not installed. Run:  pip install {pkg}")


# ── Morning Checklist ─────────────────────────────────────────────────────────

def check_disk(cfg: dict) -> list[CheckResult]:
    import psutil
    warn_pct = cfg.get("morning", {}).get("disk_warn_pct", 85)
    out: list[CheckResult] = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        pct = u.percent
        stat = "fail" if pct >= 95 else ("warn" if pct >= warn_pct else "ok")
        out.append(CheckResult(
            name=f"Disk {part.mountpoint}", status=stat,
            detail=f"{pct:.0f}% used ({_fmt_bytes(u.free)} free of {_fmt_bytes(u.total)})",
            value=pct,
        ))
    return out


def check_memory(cfg: dict) -> CheckResult:
    import psutil
    warn = cfg.get("morning", {}).get("mem_warn_pct", 90)
    m = psutil.virtual_memory()
    stat = "fail" if m.percent >= 95 else ("warn" if m.percent >= warn else "ok")
    return CheckResult(
        name="Memory", status=stat,
        detail=f"{m.percent:.0f}% used ({_fmt_bytes(m.available)} free of {_fmt_bytes(m.total)})",
        value=m.percent,
    )


def check_cpu(cfg: dict) -> CheckResult:
    import psutil
    pct = psutil.cpu_percent(interval=0.5)
    stat = "fail" if pct >= 95 else ("warn" if pct >= 80 else "ok")
    return CheckResult(
        name="CPU", status=stat,
        detail=f"{pct:.0f}% load ({psutil.cpu_count()} logical cores)",
        value=pct,
    )


def check_swap(cfg: dict) -> CheckResult:
    import psutil
    s = psutil.swap_memory()
    if s.total == 0:
        return CheckResult(name="Swap", status="info", detail="No swap configured", value=0)
    stat = "warn" if s.percent >= 50 else "ok"
    return CheckResult(
        name="Swap", status=stat,
        detail=f"{s.percent:.0f}% used ({_fmt_bytes(s.used)} / {_fmt_bytes(s.total)})",
        value=s.percent,
    )


def check_failed_services(cfg: dict) -> CheckResult:
    items: list[str] = []
    try:
        if IS_LINUX and shutil.which("systemctl"):
            r = subprocess.run(
                ["systemctl", "--failed", "--no-legend", "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.splitlines():
                parts = line.split()
                if parts:
                    items.append(parts[0])
        elif IS_WINDOWS:
            import psutil
            for svc in psutil.win_service_iter():
                try:
                    info = svc.as_dict()
                    if info["status"] != "running" and info["start_type"] == "automatic":
                        items.append(info["name"])
                except Exception:
                    pass
        elif IS_MAC:
            r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
            for line in r.stdout.splitlines()[1:]:
                parts = line.split("\t")
                if len(parts) == 3 and parts[1] not in ("0", "-"):
                    items.append(f"{parts[2]} (exit {parts[1]})")
    except Exception as e:
        return CheckResult(name="Services", status="skip", detail=str(e))
    stat = "fail" if items else "ok"
    detail = f"{len(items)} failed" if items else "All services running"
    return CheckResult(name="Services", status=stat, detail=detail, items=items[:10])


def check_pending_updates(cfg: dict) -> CheckResult:
    try:
        if IS_LINUX:
            for cmd, parser in [
                (["apt", "list", "--upgradable"],
                 lambda o: len([l for l in o.splitlines() if "/" in l and "Listing" not in l])),
                (["dnf", "check-update", "-q"],
                 lambda o: len([l for l in o.splitlines() if l and not l.startswith("Last")])),
            ]:
                if shutil.which(cmd[0]):
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    n = parser(r.stdout)
                    stat = "warn" if n > 0 else "ok"
                    return CheckResult(
                        name="Updates", status=stat,
                        detail=f"{n} pending" if n else "Up to date", value=n,
                    )
        elif IS_MAC:
            r = subprocess.run(["softwareupdate", "-l"], capture_output=True, text=True, timeout=30)
            items = [l for l in r.stdout.splitlines() if l.strip().startswith("*")]
            stat = "warn" if items else "ok"
            return CheckResult(
                name="Updates", status=stat,
                detail=f"{len(items)} macOS update(s)" if items else "macOS up to date",
                value=len(items),
            )
        elif IS_WINDOWS:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0').Updates.Count"],
                capture_output=True, text=True, timeout=60,
            )
            n = int(r.stdout.strip() or "0")
            stat = "warn" if n > 0 else "ok"
            return CheckResult(
                name="Updates", status=stat,
                detail=f"{n} Windows Update(s) pending" if n else "Windows up to date",
                value=n,
            )
    except Exception as e:
        return CheckResult(name="Updates", status="skip", detail=f"Could not check: {e}")
    return CheckResult(name="Updates", status="skip", detail="No package manager detected")


def check_ping_hosts(cfg: dict) -> list[CheckResult]:
    hosts = cfg.get("morning", {}).get("ping_hosts", [])
    if not hosts:
        return [CheckResult(name="Ping Hosts", status="skip",
                            detail="No hosts configured — add via Settings")]
    out = []
    for h in hosts:
        info = _net_ping_raw(h, count=2, timeout=2.0)
        stat = "ok" if info["alive"] else "fail"
        detail = f"{info['avg_ms']:.0f}ms" if info["alive"] else "unreachable"
        out.append(CheckResult(name=f"Ping {h}", status=stat, detail=detail, value=info))
    return out


def check_cert_expiry(cfg: dict) -> list[CheckResult]:
    paths = cfg.get("morning", {}).get("cert_paths", [])
    warn_days = cfg.get("morning", {}).get("cert_warn_days", 30)
    out: list[CheckResult] = []
    for p in paths:
        try:
            cp = Path(p)
            if not cp.exists():
                out.append(CheckResult(name=f"Cert {cp.name}", status="warn", detail="File not found"))
                continue
            r = subprocess.run(
                ["openssl", "x509", "-noout", "-enddate", "-in", p],
                capture_output=True, text=True, timeout=5,
            )
            m = re.search(r"notAfter=(.*)", r.stdout)
            if not m:
                out.append(CheckResult(name=f"Cert {cp.name}", status="skip", detail="Unable to parse"))
                continue
            expiry = datetime.strptime(m.group(1).strip(), "%b %d %H:%M:%S %Y %Z")
            days = (expiry - datetime.utcnow()).days
            stat = "fail" if days < 7 else ("warn" if days < warn_days else "ok")
            out.append(CheckResult(
                name=f"Cert {cp.name}", status=stat,
                detail=f"Expires in {days}d ({expiry.strftime('%Y-%m-%d')})", value=days,
            ))
        except Exception as e:
            out.append(CheckResult(name=f"Cert {p}", status="skip", detail=str(e)))
    if not out:
        out.append(CheckResult(name="Certificates", status="skip",
                               detail="No cert paths configured"))
    return out


def check_last_backup(cfg: dict) -> list[CheckResult]:
    paths = cfg.get("morning", {}).get("backup_paths", [])
    out: list[CheckResult] = []
    for p in paths:
        try:
            bp = Path(p)
            if not bp.exists():
                out.append(CheckResult(name=f"Backup {p}", status="fail", detail="Path not found"))
                continue
            mtime = datetime.fromtimestamp(bp.stat().st_mtime)
            age_h = (datetime.now() - mtime).total_seconds() / 3600
            stat = "fail" if age_h > 48 else ("warn" if age_h > 25 else "ok")
            out.append(CheckResult(
                name=f"Backup {bp.name}", status=stat,
                detail=f"{age_h:.1f}h ago ({mtime.strftime('%Y-%m-%d %H:%M')})", value=age_h,
            ))
        except Exception as e:
            out.append(CheckResult(name=f"Backup {p}", status="skip", detail=str(e)))
    if not out:
        out.append(CheckResult(name="Backups", status="skip",
                               detail="No backup paths configured"))
    return out


def check_open_ports(cfg: dict) -> CheckResult:
    import psutil
    try:
        conns = psutil.net_connections(kind="inet")
        ports = sorted({c.laddr.port for c in conns if c.status == "LISTEN" and c.laddr})
        sample = ", ".join(str(p) for p in ports[:15])
        more = "…" if len(ports) > 15 else ""
        return CheckResult(
            name="Listening Ports", status="info",
            detail=f"{len(ports)} listening: {sample}{more}", value=ports,
        )
    except Exception as e:
        return CheckResult(name="Listening Ports", status="skip", detail=str(e))


def check_uptime(cfg: dict) -> CheckResult:
    import psutil
    boot = datetime.fromtimestamp(psutil.boot_time())
    delta = datetime.now() - boot
    total_min = int(delta.total_seconds()) // 60
    h, m = divmod(total_min, 60)
    d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}m")
    stat = "warn" if delta.total_seconds() < 300 else "info"
    note = " ← recent reboot" if stat == "warn" else ""
    return CheckResult(
        name="Uptime", status=stat,
        detail=f"Up {' '.join(parts)}{note} (since {boot.strftime('%Y-%m-%d %H:%M')})",
    )


def run_morning_checks(cfg: dict) -> list[CheckResult]:
    enabled = set(cfg.get("morning", {}).get("checks", []))
    out: list[CheckResult] = []
    if "disk"     in enabled: out.extend(check_disk(cfg))
    if "memory"   in enabled: out.append(check_memory(cfg))
    if "cpu"      in enabled: out.append(check_cpu(cfg))
    if "swap"     in enabled: out.append(check_swap(cfg))
    if "services" in enabled: out.append(check_failed_services(cfg))
    if "updates"  in enabled: out.append(check_pending_updates(cfg))
    if "ping"     in enabled: out.extend(check_ping_hosts(cfg))
    if "certs"    in enabled: out.extend(check_cert_expiry(cfg))
    if "backups"  in enabled: out.extend(check_last_backup(cfg))
    if "ports"    in enabled: out.append(check_open_ports(cfg))
    if "uptime"   in enabled: out.append(check_uptime(cfg))
    return out


# alias for backward-compat
run_morning_checklist = run_morning_checks


# ── Active Directory ──────────────────────────────────────────────────────────

def _ad_connect(cfg: dict):
    from sysknife import cfg_decode
    ldap3 = _optional("ldap3>=2.9.1", "ldap3")
    srv = ldap3.Server(cfg["ad"]["server"], get_info=ldap3.ALL)
    conn = ldap3.Connection(
        srv,
        user=cfg["ad"]["user"],
        password=cfg_decode(cfg["ad"].get("password_enc", "")),
        authentication=ldap3.NTLM,
        auto_bind=True,
    )
    return conn


def _ad_find_user_dn(conn, base_dn: str, sam: str) -> str | None:
    conn.search(base_dn, f"(&(objectClass=user)(sAMAccountName={sam}))",
                attributes=["distinguishedName"])
    return str(conn.entries[0].entry_dn) if conn.entries else None


def _ad_find_group_dn(conn, base_dn: str, cn: str) -> str | None:
    conn.search(base_dn, f"(&(objectClass=group)(cn={cn}))",
                attributes=["distinguishedName"])
    return str(conn.entries[0].entry_dn) if conn.entries else None


def _ad_entry_to_dict(entry) -> dict:
    def _val(a):
        v = getattr(entry, a, None)
        if v is None:
            return ""
        raw = v.value
        return str(raw) if raw is not None else ""
    uac = int(_val("userAccountControl") or 0)
    return {
        "sAMAccountName": _val("sAMAccountName"),
        "displayName":    _val("displayName"),
        "mail":           _val("mail"),
        "enabled":        "Yes" if not (uac & 2) else "No",
        "locked":         "Yes" if _val("lockoutTime") not in ("", "0") else "No",
        "lastLogon":      _val("lastLogon") or "—",
        "description":    _val("description"),
    }


def ad_search_user(cfg: dict, query: str) -> dict:
    try:
        conn = _ad_connect(cfg)
        base = cfg["ad"]["base_dn"]
        attrs = ["sAMAccountName", "displayName", "mail",
                 "userAccountControl", "lockoutTime", "lastLogon", "description"]
        f = (f"(&(objectClass=user)(objectCategory=person)"
             f"(|(sAMAccountName=*{query}*)(displayName=*{query}*)(mail=*{query}*)))")
        conn.search(base, f, attributes=attrs, size_limit=50)
        return {"users": [_ad_entry_to_dict(e) for e in conn.entries]}
    except Exception as e:
        return {"users": [], "error": str(e)}


def ad_unlock_account(cfg: dict, user: str) -> dict:
    try:
        ldap3 = _optional("ldap3>=2.9.1", "ldap3")
        conn = _ad_connect(cfg)
        dn = _ad_find_user_dn(conn, cfg["ad"]["base_dn"], user)
        if not dn:
            return {"error": f"User '{user}' not found"}
        conn.modify(dn, {"lockoutTime": [(ldap3.MODIFY_REPLACE, [0])]})
        if conn.result["result"] == 0:
            return {"message": f"Unlocked {user}"}
        return {"error": f"Unlock failed: {conn.result.get('description')}"}
    except Exception as e:
        return {"error": str(e)}


def ad_reset_password(cfg: dict, user: str, new_password: str,
                      must_change: bool = False) -> dict:
    try:
        ldap3 = _optional("ldap3>=2.9.1", "ldap3")
        conn = _ad_connect(cfg)
        dn = _ad_find_user_dn(conn, cfg["ad"]["base_dn"], user)
        if not dn:
            return {"error": f"User '{user}' not found"}
        encoded = (f'"{new_password}"').encode("utf-16-le")
        conn.modify(dn, {"unicodePwd": [(ldap3.MODIFY_REPLACE, [encoded])]})
        if conn.result["result"] != 0:
            return {"error": f"Reset failed: {conn.result.get('description')}"}
        if must_change:
            conn.modify(dn, {"pwdLastSet": [(ldap3.MODIFY_REPLACE, [0])]})
        return {"message": f"Password reset for {user}"
                           + (" (must change at next logon)" if must_change else "")}
    except Exception as e:
        return {"error": str(e)}


def ad_set_account_enabled(cfg: dict, user: str, enabled: bool) -> dict:
    try:
        ldap3 = _optional("ldap3>=2.9.1", "ldap3")
        conn = _ad_connect(cfg)
        dn = _ad_find_user_dn(conn, cfg["ad"]["base_dn"], user)
        if not dn:
            return {"error": f"User '{user}' not found"}
        conn.search(dn, "(objectClass=*)", attributes=["userAccountControl"])
        uac = int(conn.entries[0].userAccountControl.value or 512)
        uac = (uac & ~2) if enabled else (uac | 2)
        conn.modify(dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, [uac])]})
        if conn.result["result"] == 0:
            return {"message": f"{'Enabled' if enabled else 'Disabled'} {user}"}
        return {"error": conn.result.get("description", "Failed")}
    except Exception as e:
        return {"error": str(e)}


def ad_list_groups(cfg: dict, query: str | None = None) -> dict:
    try:
        conn = _ad_connect(cfg)
        base = cfg["ad"]["base_dn"]
        f = f"(&(objectClass=group)(cn=*{query}*))" if query else "(objectClass=group)"
        conn.search(base, f, attributes=["cn", "description", "member"], size_limit=200)
        groups = []
        for e in conn.entries:
            members = getattr(e, "member", None)
            count = len(members.values) if members else 0
            groups.append({
                "name":        str(e.cn),
                "description": str(getattr(e, "description", "") or "—"),
                "members":     count,
            })
        return {"groups": groups}
    except Exception as e:
        return {"groups": [], "error": str(e)}


def ad_add_to_group(cfg: dict, user: str, group: str) -> dict:
    try:
        ldap3 = _optional("ldap3>=2.9.1", "ldap3")
        conn = _ad_connect(cfg)
        base = cfg["ad"]["base_dn"]
        user_dn = _ad_find_user_dn(conn, base, user)
        if not user_dn:
            return {"error": f"User '{user}' not found"}
        group_dn = _ad_find_group_dn(conn, base, group)
        if not group_dn:
            return {"error": f"Group '{group}' not found"}
        conn.modify(group_dn, {"member": [(ldap3.MODIFY_ADD, [user_dn])]})
        if conn.result["result"] == 0:
            return {"message": f"Added {user} to {group}"}
        return {"error": conn.result.get("description", "Add failed")}
    except Exception as e:
        return {"error": str(e)}


def ad_remove_from_group(cfg: dict, user: str, group: str) -> dict:
    try:
        ldap3 = _optional("ldap3>=2.9.1", "ldap3")
        conn = _ad_connect(cfg)
        base = cfg["ad"]["base_dn"]
        user_dn = _ad_find_user_dn(conn, base, user)
        if not user_dn:
            return {"error": f"User '{user}' not found"}
        group_dn = _ad_find_group_dn(conn, base, group)
        if not group_dn:
            return {"error": f"Group '{group}' not found"}
        conn.modify(group_dn, {"member": [(ldap3.MODIFY_DELETE, [user_dn])]})
        if conn.result["result"] == 0:
            return {"message": f"Removed {user} from {group}"}
        return {"error": conn.result.get("description", "Remove failed")}
    except Exception as e:
        return {"error": str(e)}


# ── Azure AD ──────────────────────────────────────────────────────────────────

_AZ_BASE = "https://graph.microsoft.com/v1.0"
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                      re.IGNORECASE)


def _az_token(cfg: dict) -> str:
    from sysknife import cfg_decode
    msal = _optional("msal>=1.28.0", "msal")
    app = msal.ConfidentialClientApplication(
        cfg["azure"]["client_id"],
        authority=f"https://login.microsoftonline.com/{cfg['azure']['tenant_id']}",
        client_credential=cfg_decode(cfg["azure"].get("client_secret_enc", "")),
    )
    result = app.acquire_token_for_client(["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Azure token acquisition failed"))
    return result["access_token"]


def _az_get(token: str, path: str, params: dict | None = None) -> dict:
    import requests as req
    r = req.get(f"{_AZ_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


def _az_patch(token: str, path: str, payload: dict) -> bool:
    import requests as req
    r = req.patch(f"{_AZ_BASE}{path}",
                  headers={"Authorization": f"Bearer {token}",
                           "Content-Type": "application/json"},
                  json=payload, timeout=15)
    return r.status_code in (200, 204)


def az_list_users(cfg: dict, query: str | None = None) -> dict:
    try:
        token = _az_token(cfg)
        params = {"$top": 100,
                  "$select": "id,displayName,userPrincipalName,accountEnabled,jobTitle,department"}
        if query:
            q = query.replace("'", "''")
            params["$filter"] = (f"startswith(displayName,'{q}') or "
                                 f"startswith(userPrincipalName,'{q}')")
        data = _az_get(token, "/users", params)
        users = [{
            "displayName":       u.get("displayName", ""),
            "userPrincipalName": u.get("userPrincipalName", ""),
            "accountEnabled":    "Yes" if u.get("accountEnabled") else "No",
            "jobTitle":          u.get("jobTitle") or "—",
            "department":        u.get("department") or "—",
        } for u in data.get("value", [])]
        return {"users": users}
    except Exception as e:
        return {"users": [], "error": str(e)}


def az_set_user_enabled(cfg: dict, upn_or_id: str, enabled: bool) -> dict:
    try:
        token = _az_token(cfg)
        ok = _az_patch(token, f"/users/{upn_or_id}", {"accountEnabled": enabled})
        if ok:
            return {"message": f"{'Enabled' if enabled else 'Disabled'} {upn_or_id}"}
        return {"error": "Patch returned non-success status"}
    except Exception as e:
        return {"error": str(e)}


def az_list_groups(cfg: dict, query: str | None = None) -> dict:
    try:
        token = _az_token(cfg)
        params = {"$top": 100, "$select": "id,displayName,description,mail"}
        if query:
            q = query.replace("'", "''")
            params["$filter"] = f"startswith(displayName,'{q}')"
        data = _az_get(token, "/groups", params)
        groups = [{
            "displayName": g.get("displayName", ""),
            "description": g.get("description") or "—",
            "id":          g.get("id", ""),
        } for g in data.get("value", [])]
        return {"groups": groups}
    except Exception as e:
        return {"groups": [], "error": str(e)}


def az_list_group_members(cfg: dict, group_ref: str) -> dict:
    try:
        token = _az_token(cfg)
        gid = group_ref
        if not _UUID_RE.match(group_ref):
            q = group_ref.replace("'", "''")
            r = _az_get(token, "/groups",
                        {"$filter": f"displayName eq '{q}'", "$top": 1})
            if not r.get("value"):
                return {"members": [], "error": f"Group '{group_ref}' not found"}
            gid = r["value"][0]["id"]
        data = _az_get(token, f"/groups/{gid}/members", {"$top": 200})
        members = [{
            "displayName":       m.get("displayName", ""),
            "userPrincipalName": m.get("userPrincipalName", "") or "—",
            "accountEnabled":    "Yes" if m.get("accountEnabled") else "No",
        } for m in data.get("value", [])]
        return {"members": members}
    except Exception as e:
        return {"members": [], "error": str(e)}


def az_list_devices(cfg: dict) -> dict:
    try:
        token = _az_token(cfg)
        data = _az_get(token, "/devices", {"$top": 100})
        devices = [{
            "displayName":            d.get("displayName", ""),
            "operatingSystem":        d.get("operatingSystem", ""),
            "operatingSystemVersion": d.get("operatingSystemVersion", ""),
            "isManaged":              "Yes" if d.get("isManaged") else "No",
            "isCompliant":            "Yes" if d.get("isCompliant") else "—",
        } for d in data.get("value", [])]
        return {"devices": devices}
    except Exception as e:
        return {"devices": [], "error": str(e)}


def az_list_apps(cfg: dict) -> dict:
    try:
        token = _az_token(cfg)
        data = _az_get(token, "/servicePrincipals",
                       {"$top": 100, "$select": "id,displayName,appId,accountEnabled"})
        apps = [{
            "displayName": s.get("displayName", ""),
            "appId":       s.get("appId", ""),
            "enabled":     "Yes" if s.get("accountEnabled") else "No",
        } for s in data.get("value", [])]
        return {"apps": apps}
    except Exception as e:
        return {"apps": [], "error": str(e)}


def az_user_mfa_status(cfg: dict, upn_or_id: str) -> dict:
    try:
        token = _az_token(cfg)
        data = _az_get(token, f"/users/{upn_or_id}/authentication/methods")
        methods = data.get("value", [])
        types: list[str] = []
        for m in methods:
            t = m.get("@odata.type", "").rsplit(".", 1)[-1]
            t = t.replace("AuthenticationMethod", "")
            if t and t.lower() != "password":
                types.append(t)
        return {
            "User":           upn_or_id,
            "MFA Registered": "Yes" if types else "No",
            "Methods":        ", ".join(types) if types else "Password only",
            "Method Count":   str(len(methods)),
        }
    except Exception as e:
        return {"error": str(e)}


# ── System Health ─────────────────────────────────────────────────────────────

def health_cpu() -> dict:
    import psutil
    pct = psutil.cpu_percent(interval=0.5)
    cores = psutil.cpu_percent(percpu=True)
    freq = psutil.cpu_freq()
    return {
        "Total CPU%":     f"{pct:.1f}%",
        "Logical Cores":  psutil.cpu_count(),
        "Physical Cores": psutil.cpu_count(logical=False) or "—",
        "Per-core%":      ", ".join(f"{c:.0f}" for c in cores),
        "Frequency":      f"{freq.current:.0f} MHz" if freq else "—",
    }


def health_memory() -> dict:
    import psutil
    m = psutil.virtual_memory()
    s = psutil.swap_memory()
    return {
        "Total RAM": _fmt_bytes(m.total),
        "Used RAM":  f"{_fmt_bytes(m.used)} ({m.percent:.0f}%)",
        "Available": _fmt_bytes(m.available),
        "Swap Total": _fmt_bytes(s.total) if s.total else "—",
        "Swap Used":  f"{_fmt_bytes(s.used)} ({s.percent:.0f}%)" if s.total else "—",
    }


def health_disk() -> list[dict]:
    import psutil
    out = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
        except (PermissionError, OSError):
            continue
        out.append({
            "mountpoint": p.mountpoint,
            "device":     p.device,
            "fstype":     p.fstype or "—",
            "total":      _fmt_bytes(u.total),
            "used":       _fmt_bytes(u.used),
            "free":       _fmt_bytes(u.free),
            "percent":    f"{u.percent:.0f}",
        })
    return out


def health_top_processes(n: int = 10) -> list[dict]:
    import psutil
    # First sample to prime cpu_percent
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.4)
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "status"]):
        try:
            cpu = p.cpu_percent(None)
            i = p.info
            procs.append({
                "pid":    i.get("pid", ""),
                "name":   (i.get("name") or "?")[:24],
                "cpu":    f"{cpu:.1f}",
                "mem":    f"{(i.get('memory_percent') or 0):.1f}",
                "status": i.get("status", ""),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: float(x["cpu"]), reverse=True)
    return procs[:n]


def health_network_io() -> list[dict]:
    import psutil
    out = []
    for nic, c in psutil.net_io_counters(pernic=True).items():
        out.append({
            "iface":        nic,
            "bytes_sent":   _fmt_bytes(c.bytes_sent),
            "bytes_recv":   _fmt_bytes(c.bytes_recv),
            "packets_sent": c.packets_sent,
            "packets_recv": c.packets_recv,
            "errin":        c.errin,
            "errout":       c.errout,
        })
    return out


def health_services() -> list[CheckResult]:
    return [check_failed_services({})]


# ── Network ───────────────────────────────────────────────────────────────────

def _net_ping_raw(host: str, count: int = 4, timeout: float = 2.0) -> dict:
    if IS_WINDOWS:
        param = ["-n", str(count), "-w", str(int(timeout * 1000))]
    else:
        param = ["-c", str(count), "-W", str(int(timeout))]
    try:
        r = subprocess.run(
            ["ping", *param, host],
            capture_output=True, text=True, timeout=timeout * count + 5,
        )
        output = r.stdout + r.stderr
        alive = r.returncode == 0
        avg_ms = 0.0
        m = re.search(r"avg[^=\d]*=?\s*[\d.]+/([\d.]+)", output, re.IGNORECASE)
        if not m:
            m = re.search(r"Average\s*=\s*(\d+)\s*ms", output, re.IGNORECASE)
        if not m:
            m = re.search(r"time[<=]([\d.]+)\s*ms", output, re.IGNORECASE)
        if m:
            avg_ms = float(m.group(1))
        return {"host": host, "alive": alive, "avg_ms": avg_ms, "output": output}
    except Exception as e:
        return {"host": host, "alive": False, "avg_ms": 0.0, "output": str(e)}


def net_ping(host: str) -> CheckResult:
    info = _net_ping_raw(host, count=2, timeout=2.0)
    if info["alive"]:
        return CheckResult(
            name=f"Ping {host}", status="ok",
            detail=f"alive — {info['avg_ms']:.0f}ms", value=info,
        )
    return CheckResult(
        name=f"Ping {host}", status="fail",
        detail="unreachable", value=info,
    )


def net_port_check(host: str, port: int) -> CheckResult:
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return CheckResult(
                name=f"{host}:{port}", status="ok",
                detail=f"port {port} OPEN on {host}",
            )
    except Exception as e:
        return CheckResult(
            name=f"{host}:{port}", status="fail",
            detail=f"port {port} closed/filtered ({e.__class__.__name__})",
        )


def net_dns_lookup(host: str, rtype: str = "A") -> dict:
    rtype = (rtype or "A").upper()
    try:
        if rtype in ("A", "AAAA"):
            family = socket.AF_INET if rtype == "A" else socket.AF_INET6
            ips = sorted({i[4][0] for i in socket.getaddrinfo(host, None, family=family)})
            if not ips:
                return {"records": [], "error": f"No {rtype} records"}
            return {"records": ips}
        # MX / TXT — fall back to system tools
        if shutil.which("dig"):
            r = subprocess.run(["dig", "+short", host, rtype],
                               capture_output=True, text=True, timeout=5)
            recs = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            return {"records": recs} if recs else {"records": [], "error": "No records"}
        if shutil.which("nslookup"):
            r = subprocess.run(["nslookup", f"-type={rtype}", host],
                               capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            return {"records": lines}
        return {"records": [], "error": f"{rtype} lookup needs 'dig' or 'nslookup' on PATH"}
    except Exception as e:
        return {"records": [], "error": str(e)}


def net_traceroute(host: str) -> dict:
    cmd = (["tracert", "-h", "20", host] if IS_WINDOWS
           else ["traceroute", "-m", "20", host])
    if not shutil.which(cmd[0]):
        return {"error": f"'{cmd[0]}' not found on PATH"}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {"output": r.stdout or r.stderr or "(no output)"}
    except Exception as e:
        return {"error": str(e)}


# ── Cleanup ───────────────────────────────────────────────────────────────────

def _scan_dir(directory: str, pattern: str = "*", older_than_days: float = 0) -> list[dict]:
    p = Path(directory)
    items: list[dict] = []
    if not p.exists():
        return items
    cutoff = time.time() - older_than_days * 86400 if older_than_days else None
    try:
        for child in p.rglob(pattern):
            try:
                if not child.is_file():
                    continue
                st = child.stat()
                if cutoff is not None and st.st_mtime > cutoff:
                    continue
                items.append({"path": str(child), "size": st.st_size, "mtime": st.st_mtime})
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return items


def _summary_status(items: list[dict], label: str) -> CheckResult:
    total = sum(i.get("size", 0) for i in items)
    if not items:
        return CheckResult(name=label, status="ok",
                           detail=f"Nothing to clean — {label.lower()} is tidy")
    return CheckResult(
        name=label, status="info",
        detail=f"Found {len(items)} files, {_fmt_bytes(total)} (dry-run — not deleted)",
        value=total, items=items[:50],
    )


def cleanup_temp_files() -> CheckResult:
    targets: list[str] = []
    if IS_WINDOWS:
        targets += [os.environ.get("TEMP", ""), os.environ.get("TMP", ""),
                    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Temp")]
    else:
        targets += ["/tmp", str(Path.home() / ".cache")]
    items: list[dict] = []
    for t in filter(None, targets):
        items += _scan_dir(t, older_than_days=1)
    return _summary_status(items, "Temp Files")


def cleanup_old_logs() -> CheckResult:
    items: list[dict] = []
    if IS_LINUX:
        items += _scan_dir("/var/log", "*.gz", older_than_days=7)
        items += _scan_dir("/var/log", "*.old", older_than_days=7)
        items += _scan_dir("/var/log", "*.1", older_than_days=7)
    elif IS_MAC:
        items += _scan_dir("/var/log", "*.gz", older_than_days=7)
        items += _scan_dir(str(Path.home() / "Library/Logs"), "*.log", older_than_days=7)
    elif IS_WINDOWS:
        items += _scan_dir(
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Logs"),
            "*.log", older_than_days=30,
        )
    return _summary_status(items, "Old Logs")


def cleanup_cores() -> CheckResult:
    items: list[dict] = []
    if IS_LINUX:
        items += _scan_dir("/var/lib/systemd/coredump", "*")
        items += _scan_dir("/var/crash", "*")
    elif IS_MAC:
        items += _scan_dir("/cores", "*")
        items += _scan_dir(str(Path.home() / "Library/Logs/DiagnosticReports"), "*.crash")
    elif IS_WINDOWS:
        items += _scan_dir(
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Minidump"), "*.dmp",
        )
    return _summary_status(items, "Core Dumps")


def cleanup_package_cache() -> CheckResult:
    cache_dirs: list[str] = []
    if IS_LINUX:
        cache_dirs += ["/var/cache/apt/archives", "/var/cache/dnf",
                       str(Path.home() / ".cache/pip")]
    elif IS_MAC:
        cache_dirs += [str(Path.home() / "Library/Caches/pip"),
                       "/Library/Caches/Homebrew"]
    elif IS_WINDOWS:
        cache_dirs += [str(Path.home() / "AppData/Local/pip/Cache")]
    items: list[dict] = []
    for d in cache_dirs:
        items += _scan_dir(d)
    return _summary_status(items, "Package Cache")


def cleanup_trash() -> CheckResult:
    paths: list[str] = []
    if IS_MAC:
        paths += [str(Path.home() / ".Trash")]
    elif IS_LINUX:
        paths += [str(Path.home() / ".local/share/Trash/files"),
                  str(Path.home() / ".local/share/Trash/info")]
    elif IS_WINDOWS:
        # Recycle Bin requires Shell API; fall back to direct path attempt
        paths += ["C:\\$Recycle.Bin"]
    items: list[dict] = []
    for d in paths:
        items += _scan_dir(d)
    return _summary_status(items, "Trash / Recycle Bin")


# ── SSH Manager ───────────────────────────────────────────────────────────────

def _ssh_find_host(cfg: dict, alias: str) -> dict | None:
    return next((h for h in cfg.get("ssh_hosts", []) if h.get("alias") == alias), None)


def _ssh_open(host: dict, password: str | None):
    paramiko = _optional("paramiko>=3.4.0", "paramiko")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw: dict = {
        "hostname": host.get("hostname") or host.get("host", ""),
        "port":     int(host.get("port", 22)),
        "username": host.get("username") or host.get("user", ""),
        "timeout":  10,
    }
    kp = host.get("key_path", "")
    if kp and Path(kp).expanduser().exists():
        kw["key_filename"] = str(Path(kp).expanduser())
    elif password:
        kw["password"] = password
    cli.connect(**kw)
    return cli


def ssh_connect(cfg: dict, alias: str, password: str | None = None) -> dict:
    host = _ssh_find_host(cfg, alias)
    if not host:
        return {"error": f"Alias '{alias}' not found"}
    try:
        cli = _ssh_open(host, password)
        try:
            _, stdout, _ = cli.exec_command("uname -a 2>/dev/null || ver", timeout=10)
            banner = stdout.read().decode(errors="replace").strip()
        finally:
            cli.close()
        hostname = host.get("hostname") or host.get("host")
        user = host.get("username") or host.get("user")
        port = host.get("port", 22)
        msg = f"Connected to {alias} ({user}@{hostname}:{port})"
        if banner:
            msg += f"\n  remote: {banner}"
        return {"message": msg}
    except Exception as e:
        return {"error": str(e)}


def ssh_run_command(cfg: dict, alias: str, command: str,
                    password: str | None = None) -> dict:
    host = _ssh_find_host(cfg, alias)
    if not host:
        return {"error": f"Alias '{alias}' not found"}
    try:
        cli = _ssh_open(host, password)
        try:
            _, stdout, stderr = cli.exec_command(command, timeout=60)
            return {
                "stdout":    stdout.read().decode(errors="replace"),
                "stderr":    stderr.read().decode(errors="replace"),
                "exit_code": stdout.channel.recv_exit_status(),
            }
        finally:
            cli.close()
    except Exception as e:
        return {"error": str(e)}


def ssh_add_host(cfg: dict, alias: str, hostname: str, port: int,
                 username: str, key_path: str = "") -> dict:
    cfg.setdefault("ssh_hosts", [])
    # Replace existing alias if present
    cfg["ssh_hosts"] = [h for h in cfg["ssh_hosts"] if h.get("alias") != alias]
    cfg["ssh_hosts"].append({
        "alias":    alias,
        "hostname": hostname,
        "port":     int(port),
        "username": username,
        "key_path": key_path,
    })
    from sysknife import save_config
    save_config(cfg)
    return cfg


def ssh_remove_host(cfg: dict, alias: str) -> dict:
    cfg["ssh_hosts"] = [h for h in cfg.get("ssh_hosts", []) if h.get("alias") != alias]
    from sysknife import save_config
    save_config(cfg)
    return cfg


# ── Processes ─────────────────────────────────────────────────────────────────

def proc_list(query: str | None = None, sort_by: str = "cpu",
              limit: int = 50) -> list[dict]:
    """Return processes optionally filtered by name/cmdline, sorted by CPU or memory."""
    import psutil
    # First pass primes psutil's CPU sampler
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.4)

    out: list[dict] = []
    q = (query or "").lower()
    for p in psutil.process_iter(
        ["pid", "name", "username", "memory_percent", "status",
         "cmdline", "create_time"]
    ):
        try:
            i = p.info
            name = i.get("name") or "?"
            cmd  = " ".join(i.get("cmdline") or [])
            if q and q not in name.lower() and q not in cmd.lower():
                continue
            cpu = p.cpu_percent(None)
            out.append({
                "pid":     i["pid"],
                "name":    name[:24],
                "user":    (i.get("username") or "")[:14],
                "cpu":     float(cpu),
                "mem":     float(i.get("memory_percent") or 0),
                "status":  i.get("status", ""),
                "started": datetime.fromtimestamp(i.get("create_time") or 0)
                                   .strftime("%H:%M:%S"),
                "cmd":     cmd[:120],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    key = "mem" if sort_by == "mem" else "cpu"
    out.sort(key=lambda x: x[key], reverse=True)
    return out[:limit]


def proc_tree(root_pid: int | None = None, max_depth: int = 12) -> str:
    """ASCII process tree. Pass root_pid to limit to a subtree."""
    import psutil
    procs: dict[int, "psutil.Process"] = {}
    for p in psutil.process_iter():
        try:
            procs[p.pid] = p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    children: dict[int, list[int]] = {}
    for pid, p in procs.items():
        try:
            ppid = p.ppid()
            if ppid != pid:           # skip kernel-style self-parents
                children.setdefault(ppid, []).append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    lines: list[str] = []

    def _walk(pid: int, depth: int) -> None:
        if depth > max_depth:
            return
        p = procs.get(pid)
        if not p:
            return
        try:
            name = p.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
        prefix = "  " * depth + ("└─ " if depth else "")
        lines.append(f"{prefix}{pid:>7}  {name}")
        for child in sorted(children.get(pid, [])):
            _walk(child, depth + 1)

    if root_pid:
        _walk(root_pid, 0)
    else:
        roots: list[int] = []
        for pid, p in procs.items():
            try:
                ppid = p.ppid()
                # A root has either no parent in our dict, OR is its own parent (kernel)
                if ppid == pid or ppid not in procs:
                    roots.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                roots.append(pid)
        for r in sorted(roots):
            _walk(r, 0)
    return "\n".join(lines) or "(no processes found)"


def proc_find_by_port(port: int) -> list[dict]:
    """Find process(es) listening on a TCP port."""
    import psutil
    out: list[dict] = []
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.laddr and c.laddr.port == int(port) and c.status == "LISTEN":
                if not c.pid:
                    continue
                try:
                    p = psutil.Process(c.pid)
                    out.append({
                        "pid":  c.pid,
                        "name": p.name(),
                        "user": p.username(),
                        "addr": f"{c.laddr.ip}:{c.laddr.port}",
                        "cmd":  " ".join(p.cmdline())[:120],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except (psutil.AccessDenied, PermissionError):
        return [{"error": "Permission denied — try running with sudo / admin"}]
    except Exception as e:
        return [{"error": str(e)}]
    return out


def proc_kill(target: str | int, force: bool = False) -> dict:
    """Kill by PID (int/numeric str) or by exact process name (str)."""
    import psutil
    import signal as _sig
    sig = _sig.SIGKILL if (force and not IS_WINDOWS) else _sig.SIGTERM
    killed: list[dict] = []
    errors: list[str] = []

    target_str = str(target)
    if target_str.isdigit():
        pid = int(target_str)
        try:
            p = psutil.Process(pid)
            p.send_signal(sig)
            killed.append({"pid": pid, "name": p.name()})
        except psutil.NoSuchProcess:
            errors.append(f"PID {pid} not found")
        except psutil.AccessDenied:
            errors.append(f"Access denied for PID {pid} (try sudo / admin)")
        except Exception as e:
            errors.append(str(e))
    else:
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if p.info.get("name", "").lower() == target_str.lower():
                    p.send_signal(sig)
                    killed.append({"pid": p.info["pid"], "name": p.info["name"]})
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                errors.append(f"Access denied for PID {p.info.get('pid')}")
            except Exception as e:
                errors.append(str(e))
        if not killed and not errors:
            errors.append(f"No processes named '{target_str}'")
    return {"killed": killed, "errors": errors,
            "signal": "SIGKILL" if force and not IS_WINDOWS else "SIGTERM"}


# ── Logs ──────────────────────────────────────────────────────────────────────

def log_recent(unit: str | None = None, level: str | None = None,
               lines: int = 100, since: str | None = None) -> dict:
    """Return recent log entries from the system log.
    unit/level are platform-specific; since is journalctl-style ('1h', '10min')."""
    try:
        if IS_LINUX and shutil.which("journalctl"):
            cmd = ["journalctl", "-n", str(lines), "--no-pager", "-o", "short-iso"]
            if unit:
                cmd += ["-u", unit]
            if level:
                cmd += ["-p", level]
            if since:
                cmd += ["--since", since]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            return {"lines": [l for l in r.stdout.splitlines() if l.strip()][-lines:]}
        elif IS_MAC:
            cmd = ["log", "show", "--last", since or "30m", "--style", "compact"]
            if unit:
                cmd += ["--predicate", f"subsystem == '{unit}'"]
            if level == "err" or level == "error":
                cmd += ["--predicate", "messageType == error"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            output = [l for l in r.stdout.splitlines() if l.strip()]
            return {"lines": output[-lines:]}
        elif IS_WINDOWS:
            log_name = unit or "System"
            cmd = ["powershell", "-NoProfile", "-Command",
                   f"Get-EventLog -LogName '{log_name}' -Newest {lines} | "
                   f"Format-Table TimeGenerated,EntryType,Source,Message "
                   f"-AutoSize -Wrap | Out-String -Width 200"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {"lines": [l for l in r.stdout.splitlines() if l.strip()][-lines:]}
        return {"lines": [], "error": "No log source available on this OS"}
    except Exception as e:
        return {"lines": [], "error": str(e)}


def log_list_units() -> list[str]:
    """List recently-active systemd units / Windows event logs."""
    try:
        if IS_LINUX and shutil.which("systemctl"):
            r = subprocess.run(
                ["systemctl", "list-units", "--type=service",
                 "--no-legend", "--no-pager", "--state=active"],
                capture_output=True, text=True, timeout=10,
            )
            return sorted({l.split()[0] for l in r.stdout.splitlines() if l.strip()})
        elif IS_WINDOWS:
            return ["System", "Application", "Security", "Setup"]
        elif IS_MAC:
            # Common subsystems users may filter by
            return ["com.apple.kernel", "com.apple.sharedfilelist",
                    "com.apple.WindowServer", "com.apple.network",
                    "com.apple.security"]
    except Exception:
        pass
    return []


# ── Network (additional tools) ────────────────────────────────────────────────

def net_whois(domain: str) -> dict:
    if not shutil.which("whois"):
        return {"error": "'whois' command not on PATH (apt install whois / brew install whois)"}
    try:
        r = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=15)
        text = r.stdout
        keys = ("Registrar:", "Creation Date:", "Registry Expiry Date:",
                "Updated Date:", "Domain Status:", "Name Server:",
                "Registrant Organization:", "Registrant Country:")
        fields: dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            for key in keys:
                if stripped.startswith(key):
                    val = stripped.split(":", 1)[1].strip()
                    if not val:
                        continue
                    label = key.rstrip(":")
                    fields[label] = (fields[label] + ", " + val) if label in fields else val
        return {"summary": fields, "raw": text[:6000]}
    except Exception as e:
        return {"error": str(e)}


def net_http_check(url: str, timeout: float = 10.0) -> dict:
    import requests as req
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        t0 = time.time()
        r = req.get(url, timeout=timeout, allow_redirects=True,
                    headers={"User-Agent": "sysknife/2.0"})
        elapsed_ms = (time.time() - t0) * 1000
        return {
            "url":          url,
            "final_url":    r.url,
            "status":       r.status_code,
            "reason":       r.reason,
            "elapsed_ms":   round(elapsed_ms, 1),
            "redirects":    len(r.history),
            "size":         _fmt_bytes(len(r.content)),
            "server":       r.headers.get("Server", "—"),
            "content_type": r.headers.get("Content-Type", "—"),
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def net_ssl_check(host: str, port: int = 443, timeout: float = 10.0) -> dict:
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()
        not_after = cert.get("notAfter", "")
        days = None
        if not_after:
            try:
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                days = (expiry - datetime.utcnow()).days
            except Exception:
                pass
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer  = dict(x[0] for x in cert.get("issuer", []))
        sans = [v for k, v in cert.get("subjectAltName", []) if k == "DNS"]
        return {
            "Host":            f"{host}:{port}",
            "TLS Version":     version,
            "Cipher":          cipher[0] if cipher else "—",
            "Subject (CN)":    subject.get("commonName", "—"),
            "Issuer":          issuer.get("organizationName",
                                          issuer.get("commonName", "—")),
            "Valid From":      cert.get("notBefore", "—"),
            "Valid To":        not_after or "—",
            "Days Remaining":  str(days) if days is not None else "—",
            "SAN Count":       str(len(sans)),
            "SANs":            ", ".join(sans[:8]) + (" …" if len(sans) > 8 else ""),
        }
    except Exception as e:
        return {"Host": f"{host}:{port}", "error": str(e)}


def net_public_ip() -> dict:
    """Resolve public IP via several providers (first one to answer wins)."""
    import requests as req
    providers = [
        ("ipify",     "https://api.ipify.org?format=json"),
        ("ifconfig",  "https://ifconfig.me/ip"),
        ("icanhazip", "https://icanhazip.com"),
    ]
    for name, url in providers:
        try:
            r = req.get(url, timeout=5,
                        headers={"User-Agent": "sysknife/2.0"})
            if r.status_code != 200:
                continue
            ip = (r.json().get("ip") if "json" in r.headers.get("Content-Type", "")
                  else r.text.strip())
            if ip:
                return {"ip": ip, "provider": name}
        except Exception:
            continue
    return {"error": "All public-IP providers unreachable"}


def net_my_ips() -> list[dict]:
    """Local network interfaces with IPv4/IPv6/MAC and link state."""
    import psutil
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    out: list[dict] = []
    for name, addr_list in addrs.items():
        ipv4 = next((a.address for a in addr_list
                      if a.family.name == "AF_INET"), "")
        ipv6 = next((a.address for a in addr_list
                      if a.family.name in ("AF_INET6", "AddressFamily.AF_INET6")), "")
        mac  = next((a.address for a in addr_list
                      if a.family.name in ("AF_LINK", "AF_PACKET", "AddressFamily.AF_LINK")), "")
        st = stats.get(name)
        out.append({
            "iface":  name,
            "ipv4":   ipv4 or "—",
            "ipv6":   (ipv6.split("%")[0] if ipv6 else "—"),
            "mac":    mac or "—",
            "is_up":  "Yes" if st and st.isup else "No",
            "speed":  f"{st.speed} Mbps" if st and st.speed else "—",
        })
    return out


def net_port_scan(host: str, ports: list[int], timeout: float = 1.0) -> list[dict]:
    """Sequential TCP connect-scan. Returns one row per port."""
    out: list[dict] = []
    for port in ports:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                out.append({"port": port, "status": "open"})
        except (socket.timeout, ConnectionRefusedError):
            out.append({"port": port, "status": "closed"})
        except Exception as e:
            out.append({"port": port, "status": f"error ({e.__class__.__name__})"})
    return out


COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 465, 587, 631,
                993, 995, 1433, 1521, 2049, 3306, 3389, 5432, 5900, 5984,
                6379, 8000, 8080, 8443, 9000, 9090, 9200, 11211, 27017]


# ── Cleanup (additional) ──────────────────────────────────────────────────────

def cleanup_apply(items: list[dict]) -> dict:
    """Actually delete items from a cleanup_* dry-run result."""
    deleted, freed = 0, 0
    errors: list[str] = []
    for it in items:
        path = it.get("path")
        if not path:
            continue
        try:
            p = Path(path)
            if p.is_file():
                size = p.stat().st_size
                p.unlink()
                deleted += 1
                freed += size
        except Exception as e:
            errors.append(f"{path}: {e}")
    return {"deleted": deleted, "freed": freed,
            "freed_human": _fmt_bytes(freed),
            "errors": errors[:10]}


def cleanup_big_files(directory: str, top_n: int = 25,
                      min_size_mb: int = 50) -> list[dict]:
    """Find largest files under a directory."""
    p = Path(directory).expanduser()
    if not p.exists():
        return [{"error": f"Path not found: {p}"}]
    min_size = min_size_mb * 1024 * 1024
    items: list[dict] = []
    for child in p.rglob("*"):
        try:
            if not child.is_file():
                continue
            size = child.stat().st_size
            if size < min_size:
                continue
            items.append({
                "path":  str(child),
                "size":  size,
                "size_human": _fmt_bytes(size),
                "mtime": datetime.fromtimestamp(child.stat().st_mtime)
                                 .strftime("%Y-%m-%d"),
            })
        except (PermissionError, OSError):
            pass
    items.sort(key=lambda x: x.get("size", 0), reverse=True)
    return items[:top_n]


def cleanup_old_downloads(days: int = 30) -> CheckResult:
    items = _scan_dir(str(Path.home() / "Downloads"), older_than_days=days)
    return _summary_status(items, f"Old Downloads (>{days}d)")


# ── Health (additional) ───────────────────────────────────────────────────────

def health_battery() -> dict:
    import psutil
    try:
        b = psutil.sensors_battery()
    except (AttributeError, NotImplementedError):
        return {"available": "No"}
    if b is None:
        return {"available": "No"}
    secs = b.secsleft
    if secs == psutil.POWER_TIME_UNLIMITED:
        time_left = "Unlimited (plugged in)"
    elif secs == psutil.POWER_TIME_UNKNOWN:
        time_left = "Unknown"
    else:
        h, m = divmod(secs // 60, 60)
        time_left = f"{h}h {m}m"
    return {
        "available":  "Yes",
        "Charge":     f"{b.percent:.0f}%",
        "Plugged In": "Yes" if b.power_plugged else "No",
        "Time Left":  time_left,
    }


def health_load_avg() -> dict:
    if not hasattr(os, "getloadavg"):
        return {"available": "No (Windows — see CPU panel for usage%)"}
    try:
        l1, l5, l15 = os.getloadavg()
        import psutil
        cores = psutil.cpu_count() or 1
        def _state(v):
            return "ok" if v < cores else ("warn" if v < cores * 2 else "fail")
        return {
            "1 min":    f"{l1:.2f}",
            "5 min":    f"{l5:.2f}",
            "15 min":   f"{l15:.2f}",
            "Cores":    str(cores),
            "Status":   _state(l5),
        }
    except OSError as e:
        return {"available": "No", "error": str(e)}


def health_temperatures() -> list[dict]:
    import psutil
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, NotImplementedError):
        return []
    out: list[dict] = []
    for sensor, entries in temps.items():
        for e in entries:
            out.append({
                "sensor":  sensor,
                "label":   e.label or sensor,
                "current": f"{e.current:.1f}°C",
                "high":    f"{e.high:.1f}°C" if e.high else "—",
                "critical": f"{e.critical:.1f}°C" if e.critical else "—",
            })
    return out


# ── Reports ───────────────────────────────────────────────────────────────────

_HTML_REPORT_CSS = """
:root { color-scheme: dark; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       background: #1e1e2e; color: #cdd6f4; margin: 0; padding: 2.5rem; line-height: 1.5; }
.wrap { max-width: 960px; margin: 0 auto; }
h1 { color: #cba6f7; font-weight: 500; margin: 0 0 0.4rem; font-size: 28px; letter-spacing: -0.3px; }
.sub { color: #a6adc8; font-size: 14px; margin-bottom: 2rem; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.stats { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 2rem; }
.stat { background: #313244; padding: 0.6rem 1.1rem; border-radius: 8px;
        font-family: ui-monospace, monospace; font-size: 13px; font-weight: 500; }
.stat.ok   { color: #a6e3a1; }
.stat.warn { color: #f9e2af; }
.stat.fail { color: #f38ba8; }
.stat.info { color: #89dceb; }
.stat.skip { color: #6c7086; }
.card { background: #313244; border-radius: 12px; padding: 1.1rem 1.25rem;
        margin-bottom: 0.8rem; border-left: 4px solid #6c7086; }
.card.ok   { border-left-color: #a6e3a1; }
.card.warn { border-left-color: #f9e2af; }
.card.fail { border-left-color: #f38ba8; }
.card.skip { border-left-color: #6c7086; }
.card.info { border-left-color: #89dceb; }
.card .name   { font-weight: 600; font-size: 14px; }
.card .pill   { float: right; font-family: ui-monospace, monospace;
                padding: 2px 10px; border-radius: 99px; font-size: 11px; font-weight: 600; }
.pill.ok   { background: #a6e3a1; color: #1e1e2e; }
.pill.warn { background: #f9e2af; color: #1e1e2e; }
.pill.fail { background: #f38ba8; color: #1e1e2e; }
.pill.skip { background: #6c7086; color: #1e1e2e; }
.pill.info { background: #89dceb; color: #1e1e2e; }
.card .detail { color: #bac2de; font-family: ui-monospace, monospace;
                font-size: 13px; margin-top: 6px; }
.card ul { margin: 6px 0 0 18px; color: #a6adc8; font-family: ui-monospace, monospace;
           font-size: 12px; }
footer { color: #6c7086; font-size: 12px; margin-top: 3rem;
         padding-top: 1rem; border-top: 1px solid #45475a; }
footer a { color: #89b4fa; text-decoration: none; }
"""


def report_morning_html(cfg: dict, results: list[CheckResult]) -> str:
    from html import escape as _esc
    import socket as _s
    counts = {"ok": 0, "warn": 0, "fail": 0, "skip": 0, "info": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    cards = []
    for r in results:
        items_html = ""
        if r.items:
            items_html = "<ul>" + "".join(
                f"<li>{_esc(str(i))}</li>" for i in r.items[:10]
            ) + "</ul>"
        cards.append(
            f'<div class="card {r.status}">'
            f'<span class="pill {r.status}">{r.status.upper()}</span>'
            f'<span class="name">{_esc(r.name)}</span>'
            f'<div class="detail">{_esc(r.detail)}{items_html}</div>'
            f'</div>'
        )
    stats_html = "".join(
        f'<div class="stat {k}">{v} {k}</div>'
        for k, v in counts.items() if v > 0
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = _s.gethostname()
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Sysknife Report — {_esc(hostname)} — {now}</title>"
        f"<style>{_HTML_REPORT_CSS}</style></head>"
        f"<body><div class='wrap'>"
        f"<h1>⚔ Sysknife Morning Report</h1>"
        f"<p class='sub'>{_esc(hostname)} · {now} · {_esc(sys.platform)}</p>"
        f"<div class='stats'>{stats_html}</div>"
        f"{''.join(cards)}"
        f"<footer>Generated by Tony's Sysadmin Swiss Army Knife · "
        f"<a href='https://github.com/hardlygospel/tonys-sysknife'>"
        f"github.com/hardlygospel/tonys-sysknife</a></footer>"
        f"</div></body></html>"
    )


def report_morning_text(cfg: dict, results: list[CheckResult]) -> str:
    import socket as _s
    icons = {"ok": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]",
             "skip": "[SKIP]", "info": "[INFO]"}
    lines = [
        "Sysknife Morning Report",
        "=" * 60,
        f"Host:      {_s.gethostname()}",
        f"Platform:  {sys.platform}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for r in results:
        lines.append(f"{icons.get(r.status, '[? ]')} {r.name:<26}  {r.detail}")
    lines.append("")
    lines.append("-" * 60)
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    summary = "  ".join(f"{v} {k}" for k, v in counts.items() if v)
    lines.append(f"Summary: {summary}")
    return "\n".join(lines)


def report_morning_json(cfg: dict, results: list[CheckResult]) -> str:
    import json as _json
    import socket as _s
    return _json.dumps({
        "host":      _s.gethostname(),
        "platform":  sys.platform,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "results": [
            {"name": r.name, "status": r.status, "detail": r.detail,
             "value": r.value, "items": r.items}
            for r in results
        ],
    }, indent=2, default=str)


def save_report(content: str, fmt: str = "html",
                path: str | Path | None = None) -> str:
    """Write a report to disk and return the resolved path."""
    if path is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path.home() / f"sysknife-report-{ts}.{fmt}"
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)
