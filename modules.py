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
