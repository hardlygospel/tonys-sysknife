#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2024-2026 Tony (hardlygospel)
"""
All sysadmin module logic — no UI, no console output.
Every function returns plain Python dicts/lists so both the TUI and GUI can render them.
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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MAC     = sys.platform == "darwin"


# ── shared helpers ────────────────────────────────────────────────────────────

def _fmt_bytes(n: int) -> str:
    for unit in ("B","KB","MB","GB","TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _optional(pkg: str, mod: str):
    """Import optional dependency or raise helpful RuntimeError."""
    try:
        return __import__(mod)
    except ImportError:
        raise RuntimeError(
            f"Optional package not installed. Run:  pip install {pkg}"
        )


# ── Morning Checklist ─────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name:   str
    status: str        # "ok" | "warn" | "fail" | "skip" | "info"
    detail: str
    value:  Any = None
    items:  list = field(default_factory=list)  # sub-items for multi-row results


def check_disk(cfg: dict) -> list[CheckResult]:
    import psutil
    warn_pct = cfg["morning"].get("disk_warn_pct", 85)
    results  = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue
        pct  = usage.percent
        stat = "fail" if pct >= 95 else ("warn" if pct >= warn_pct else "ok")
        results.append(CheckResult(
            name   = f"Disk {part.mountpoint}",
            status = stat,
            detail = f"{pct:.0f}% used  ({_fmt_bytes(usage.free)} free of {_fmt_bytes(usage.total)})",
            value  = pct,
        ))
    return results


def check_memory(cfg: dict) -> CheckResult:
    import psutil
    warn_pct = cfg["morning"].get("mem_warn_pct", 90)
    mem  = psutil.virtual_memory()
    pct  = mem.percent
    stat = "fail" if pct >= 95 else ("warn" if pct >= warn_pct else "ok")
    return CheckResult(
        name   = "Memory",
        status = stat,
        detail = f"{pct:.0f}% used  ({_fmt_bytes(mem.available)} free of {_fmt_bytes(mem.total)})",
        value  = pct,
    )


def check_cpu(cfg: dict) -> CheckResult:
    import psutil
    pct  = psutil.cpu_percent(interval=1)
    stat = "fail" if pct >= 95 else ("warn" if pct >= 80 else "ok")
    count = psutil.cpu_count()
    return CheckResult(
        name   = "CPU",
        status = stat,
        detail = f"{pct:.0f}% load  ({count} logical cores)",
        value  = pct,
    )


def check_swap(cfg: dict) -> CheckResult:
    import psutil
    swap = psutil.swap_memory()
    if swap.total == 0:
        return CheckResult(name="Swap", status="info", detail="No swap configured", value=0)
    pct  = swap.percent
    stat = "warn" if pct >= 50 else "ok"
    return CheckResult(
        name   = "Swap",
        status = stat,
        detail = f"{pct:.0f}% used  ({_fmt_bytes(swap.used)} / {_fmt_bytes(swap.total)})",
        value  = pct,
    )


def check_failed_services(cfg: dict) -> CheckResult:
    items = []
    try:
        if IS_LINUX:
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
            r = subprocess.run(
                ["launchctl", "list"], capture_output=True, text=True, timeout=10,
            )
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
            for cmd, parse in [
                (["apt", "list", "--upgradable", "-qq"],
                 lambda o: len([l for l in o.splitlines() if "/" in l])),
                (["dnf", "check-update", "-q", "--refresh"],
                 lambda o: len([l for l in o.splitlines() if l and not l.startswith("Last")])),
                (["zypper", "--non-interactive", "lu"],
                 lambda o: len([l for l in o.splitlines() if "v |" in l])),
            ]:
                if shutil.which(cmd[0]):
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    count = parse(r.stdout)
                    stat  = "warn" if count > 0 else "ok"
                    return CheckResult(
                        name="Updates", status=stat,
                        detail=f"{count} pending update(s)" if count else "System up to date",
                        value=count,
                    )
        elif IS_MAC:
            r = subprocess.run(["softwareupdate", "-l"], capture_output=True, text=True, timeout=30)
            items = [l for l in r.stdout.splitlines() if l.strip().startswith("*")]
            stat  = "warn" if items else "ok"
            return CheckResult(
                name="Updates", status=stat,
                detail=f"{len(items)} macOS update(s) available" if items else "macOS up to date",
                value=len(items),
            )
        elif IS_WINDOWS:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search('IsInstalled=0').Updates.Count"],
                capture_output=True, text=True, timeout=60,
            )
            count = int(r.stdout.strip() or "0")
            stat  = "warn" if count > 0 else "ok"
            return CheckResult(
                name="Updates", status=stat,
                detail=f"{count} Windows Update(s) pending" if count else "Windows up to date",
                value=count,
            )
    except Exception as e:
        return CheckResult(name="Updates", status="skip", detail=f"Could not check: {e}")
    return CheckResult(name="Updates", status="skip", detail="No package manager detected")


def check_ping_hosts(cfg: dict) -> list[CheckResult]:
    hosts = cfg["morning"].get("ping_hosts", [])
    if not hosts:
        return [CheckResult(name="Ping Hosts", status="skip",
                            detail="No hosts configured — add via Settings")]
    results = []
    for h in hosts:
        info = net_ping(h, count=2, timeout=2.0)
        stat = "ok" if info["alive"] else "fail"
        ms   = f"{info['avg_ms']:.0f}ms" if info["alive"] else "unreachable"
        results.append(CheckResult(name=f"Ping {h}", status=stat, detail=ms, value=info))
    return results


def check_cert_expiry(cfg: dict) -> list[CheckResult]:
    import ssl, datetime as dt
    paths = cfg["morning"].get("cert_paths", [])
    warn_days = cfg["morning"].get("cert_warn_days", 30)
    results = []
    for p in paths:
        try:
            cert_path = Path(p)
            if not cert_path.exists():
                results.append(CheckResult(name=f"Cert {p}", status="warn", detail="File not found"))
                continue
            ctx = ssl.create_default_context()
            ctx.load_verify_locations(p)
            # Parse expiry via openssl
            r = subprocess.run(
                ["openssl", "x509", "-noout", "-enddate", "-in", p],
                capture_output=True, text=True, timeout=5,
            )
            m = re.search(r"notAfter=(.*)", r.stdout)
            if m:
                expiry = dt.datetime.strptime(m.group(1).strip(), "%b %d %H:%M:%S %Y %Z")
                days   = (expiry - dt.datetime.utcnow()).days
                stat   = "fail" if days < 7 else ("warn" if days < warn_days else "ok")
                results.append(CheckResult(
                    name=f"Cert {cert_path.name}", status=stat,
                    detail=f"Expires in {days}d ({expiry.strftime('%Y-%m-%d')})",
                    value=days,
                ))
        except Exception as e:
            results.append(CheckResult(name=f"Cert {p}", status="skip", detail=str(e)))
    if not results:
        results.append(CheckResult(name="Certificates", status="skip",
                                   detail="No cert paths configured — add via Settings"))
    return results


def check_last_backup(cfg: dict) -> list[CheckResult]:
    paths = cfg["morning"].get("backup_paths", [])
    results = []
    for p in paths:
        try:
            bp   = Path(p)
            if not bp.exists():
                results.append(CheckResult(name=f"Backup {p}", status="fail", detail="Path not found"))
                continue
            mtime = datetime.fromtimestamp(bp.stat().st_mtime)
            age_h = (datetime.now() - mtime).total_seconds() / 3600
            stat  = "fail" if age_h > 48 else ("warn" if age_h > 25 else "ok")
            results.append(CheckResult(
                name=f"Backup {bp.name}", status=stat,
                detail=f"Last modified {age_h:.1f}h ago ({mtime.strftime('%Y-%m-%d %H:%M')})",
                value=age_h,
            ))
        except Exception as e:
            results.append(CheckResult(name=f"Backup {p}", status="skip", detail=str(e)))
    if not results:
        results.append(CheckResult(name="Backups", status="skip",
                                   detail="No backup paths configured — add via Settings"))
    return results


def check_open_ports(cfg: dict) -> CheckResult:
    import psutil
    try:
        conns = psutil.net_connections(kind="inet")
        ports = sorted({c.laddr.port for c in conns if c.status == "LISTEN" and c.laddr})
        return CheckResult(
            name="Listening Ports", status="info",
            detail=f"{len(ports)} ports listening: {', '.join(str(p) for p in ports[:15])}{'…' if len(ports)>15 else ''}",
            value=ports,
        )
    except Exception as e:
        return CheckResult(name="Listening Ports", status="skip", detail=str(e))


def check_uptime(cfg: dict) -> CheckResult:
    import psutil
    boot  = datetime.fromtimestamp(psutil.boot_time())
    delta = datetime.now() - boot
    h, m  = divmod(int(delta.total_seconds()) // 60, 60)
    d, h  = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    parts.append(f"{m}m")
    stat  = "warn" if delta.total_seconds() < 300 else "info"
    note  = " ← recent reboot" if stat == "warn" else ""
    return CheckResult(
        name="Uptime", status=stat,
        detail=f"Up {' '.join(parts)}{note}  (since {boot.strftime('%Y-%m-%d %H:%M')})",
    )


def run_morning_checklist(cfg: dict) -> list[CheckResult]:
    enabled = set(cfg["morning"].get("checks", []))
    all_results: list[CheckResult] = []

    def _add(*results):
        for r in results:
            all_results.append(r) if isinstance(r, CheckResult) else all_results.extend(r)

    if "disk"     in enabled: _add(check_disk(cfg))
    if "memory"   in enabled: _add(check_memory(cfg))
    if "cpu"      in enabled: _add(check_cpu(cfg))
    if "swap"     in enabled: _add(check_swap(cfg))
    if "services" in enabled: _add(check_failed_services(cfg))
    if "updates"  in enabled: _add(check_pending_updates(cfg))
    if "ping"     in enabled: _add(check_ping_hosts(cfg))
    if "certs"    in enabled: _add(check_cert_expiry(cfg))
    if "backups"  in enabled: _add(check_last_backup(cfg))
    if "ports"    in enabled: _add(check_open_ports(cfg))
    if "uptime"   in enabled: _add(check_uptime(cfg))
    return all_results


# ── Active Directory ──────────────────────────────────────────────────────────

def ad_connect(cfg: dict):
    from sysknife import cfg_decode
    ldap3 = _optional("ldap3>=2.9.1", "ldap3")
    srv = ldap3.Server(cfg["ad"]["server"], get_info=ldap3.ALL)
    conn = ldap3.Connection(
        srv,
        user     = cfg["ad"]["user"],
        password = cfg_decode(cfg["ad"].get("password_enc", "")),
        authentication = ldap3.NTLM,
        auto_bind = True,
    )
    return conn


def ad_search_users(conn, base_dn: str, query: str, limit: int = 50) -> list[dict]:
    attrs = ["sAMAccountName","displayName","mail","userAccountControl",
             "lockoutTime","pwdLastSet","lastLogon","memberOf","description"]
    f = (f"(&(objectClass=user)(objectCategory=person)"
         f"(|(sAMAccountName=*{query}*)(displayName=*{query}*)(mail=*{query}*)))")
    conn.search(base_dn, f, attributes=attrs, size_limit=limit)
    return [_ad_entry_to_dict(e) for e in conn.entries]


def _ad_entry_to_dict(entry) -> dict:
    def _val(a):
        v = getattr(entry, a, None)
        if v is None:
            return ""
        raw = v.value
        return str(raw) if raw is not None else ""

    uac = int(_val("userAccountControl") or 0)
    return {
        "dn":          str(entry.entry_dn),
        "sam":         _val("sAMAccountName"),
        "display":     _val("displayName"),
        "mail":        _val("mail"),
        "disabled":    bool(uac & 2),
        "locked":      _val("lockoutTime") not in ("", "0", None),
        "pwd_last_set":_val("pwdLastSet"),
        "last_logon":  _val("lastLogon"),
        "description": _val("description"),
        "groups":      [str(g) for g in (getattr(entry,"memberOf",[]).values or [])],
    }


def ad_list_locked(conn, base_dn: str) -> list[dict]:
    f = "(&(objectClass=user)(objectCategory=person)(lockoutTime>=1))"
    conn.search(base_dn, f,
                attributes=["sAMAccountName","displayName","mail","lockoutTime"])
    return [_ad_entry_to_dict(e) for e in conn.entries]


def ad_unlock_user(conn, user_dn: str) -> bool:
    ldap3 = _optional("ldap3>=2.9.1", "ldap3")
    conn.modify(user_dn, {"lockoutTime": [(ldap3.MODIFY_REPLACE, [0])]})
    return conn.result["result"] == 0


def ad_set_enabled(conn, user_dn: str, enabled: bool) -> bool:
    ldap3 = _optional("ldap3>=2.9.1", "ldap3")
    # Get current UAC first
    conn.search(user_dn, "(objectClass=*)", attributes=["userAccountControl"])
    uac = int(conn.entries[0].userAccountControl.value or 512)
    if enabled:
        uac = uac & ~2   # clear disabled bit
    else:
        uac = uac | 2    # set disabled bit
    conn.modify(user_dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, [uac])]})
    return conn.result["result"] == 0


def ad_reset_password(conn, user_dn: str, new_password: str) -> bool:
    ldap3 = _optional("ldap3>=2.9.1", "ldap3")
    encoded = (f'"{new_password}"').encode("utf-16-le")
    conn.modify(user_dn, {"unicodePwd": [(ldap3.MODIFY_REPLACE, [encoded])]})
    return conn.result["result"] == 0


def ad_list_groups(conn, base_dn: str, query: str = "") -> list[dict]:
    f = (f"(&(objectClass=group)(cn=*{query}*))" if query
         else "(objectClass=group)")
    conn.search(base_dn, f, attributes=["cn","description","member"])
    out = []
    for e in conn.entries:
        members = getattr(e, "member", None)
        count   = len(members.values) if members else 0
        out.append({
            "dn":     str(e.entry_dn),
            "cn":     str(e.cn),
            "desc":   str(getattr(e, "description", "") or ""),
            "count":  count,
        })
    return out


def ad_get_group_members(conn, group_dn: str) -> list[str]:
    conn.search(group_dn, "(objectClass=*)", attributes=["member"])
    members = getattr(conn.entries[0], "member", None) if conn.entries else None
    return [str(m) for m in (members.values if members else [])]


# ── Azure AD ──────────────────────────────────────────────────────────────────

_AZ_BASE = "https://graph.microsoft.com/v1.0"


def az_get_token(cfg: dict) -> str:
    from sysknife import cfg_decode
    msal = _optional("msal>=1.28.0", "msal")
    app  = msal.ConfidentialClientApplication(
        cfg["azure"]["client_id"],
        authority  = f"https://login.microsoftonline.com/{cfg['azure']['tenant_id']}",
        client_credential = cfg_decode(cfg["azure"].get("client_secret_enc", "")),
    )
    result = app.acquire_token_for_client(["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Azure token failed"))
    return result["access_token"]


def _az_get(token: str, path: str, params: dict | None = None) -> dict:
    import requests as req
    r = req.get(
        f"{_AZ_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _az_patch(token: str, path: str, payload: dict) -> bool:
    import requests as req
    r = req.patch(
        f"{_AZ_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload, timeout=15,
    )
    return r.status_code in (200, 204)


def az_list_users(token: str, query: str = "", top: int = 50) -> list[dict]:
    params: dict = {"$top": top, "$select": "id,displayName,userPrincipalName,accountEnabled,assignedLicenses,createdDateTime"}
    if query:
        params["$filter"] = (f"startswith(displayName,'{query}') or "
                             f"startswith(userPrincipalName,'{query}')")
    data = _az_get(token, "/users", params)
    out  = []
    for u in data.get("value", []):
        out.append({
            "id":      u.get("id",""),
            "display": u.get("displayName",""),
            "upn":     u.get("userPrincipalName",""),
            "enabled": u.get("accountEnabled", True),
            "licensed":bool(u.get("assignedLicenses",[])),
            "created": u.get("createdDateTime",""),
        })
    return out


def az_get_user(token: str, id_or_upn: str) -> dict:
    return _az_get(token, f"/users/{id_or_upn}")


def az_toggle_user(token: str, user_id: str, enabled: bool) -> bool:
    return _az_patch(token, f"/users/{user_id}", {"accountEnabled": enabled})


def az_list_groups(token: str, query: str = "") -> list[dict]:
    params: dict = {"$top": 50, "$select": "id,displayName,mail,groupTypes"}
    if query:
        params["$filter"] = f"startswith(displayName,'{query}')"
    data = _az_get(token, "/groups", params)
    return [{"id": g["id"], "display": g.get("displayName",""),
             "mail": g.get("mail",""), "type": ",".join(g.get("groupTypes",[]))}
            for g in data.get("value", [])]


def az_get_group_members(token: str, group_id: str) -> list[dict]:
    data = _az_get(token, f"/groups/{group_id}/members")
    return [{"id": m.get("id"), "display": m.get("displayName"),
             "upn": m.get("userPrincipalName")} for m in data.get("value", [])]


def az_list_devices(token: str) -> list[dict]:
    data = _az_get(token, "/devices", {"$top": 50})
    return [{"id": d.get("id"), "display": d.get("displayName"),
             "os": d.get("operatingSystem"), "version": d.get("operatingSystemVersion"),
             "compliant": d.get("isCompliant"), "enabled": d.get("accountEnabled")}
            for d in data.get("value", [])]


def az_list_service_principals(token: str, query: str = "") -> list[dict]:
    params: dict = {"$top": 50, "$select": "id,displayName,appId,accountEnabled"}
    if query:
        params["$filter"] = f"startswith(displayName,'{query}')"
    data = _az_get(token, "/servicePrincipals", params)
    return [{"id": s.get("id"), "display": s.get("displayName"),
             "app_id": s.get("appId"), "enabled": s.get("accountEnabled")}
            for s in data.get("value", [])]


# ── System Health ─────────────────────────────────────────────────────────────

def get_system_snapshot() -> dict:
    import psutil
    cpu   = psutil.cpu_percent(interval=0.5)
    cores = psutil.cpu_percent(interval=None, percpu=True)
    mem   = psutil.virtual_memory()
    swap  = psutil.swap_memory()
    disks = []
    for p in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(p.mountpoint)
            disks.append({"mount": p.mountpoint, "fstype": p.fstype,
                          "total": u.total, "used": u.used,
                          "free": u.free, "pct": u.percent})
        except PermissionError:
            pass
    net_io = {k: {"sent": v.bytes_sent, "recv": v.bytes_recv}
              for k, v in psutil.net_io_counters(pernic=True).items()}
    return {
        "cpu_pct":    cpu,
        "cpu_cores":  cores,
        "mem":        {"total": mem.total, "used": mem.used,
                       "free": mem.available, "pct": mem.percent},
        "swap":       {"total": swap.total, "used": swap.used, "pct": swap.percent},
        "disks":      disks,
        "net_io":     net_io,
        "uptime":     time.time() - psutil.boot_time(),
        "boot_time":  psutil.boot_time(),
        "hostname":   socket.gethostname(),
        "platform":   sys.platform,
    }


def get_top_processes(sort_by: str = "cpu", limit: int = 15) -> list[dict]:
    import psutil
    procs = []
    for p in psutil.process_iter(["pid","name","cpu_percent","memory_percent","status","username"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda x: x.get(key) or 0, reverse=True)
    return procs[:limit]


def get_net_interfaces() -> list[dict]:
    import psutil
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    out   = []
    for name, addr_list in addrs.items():
        st     = stats.get(name)
        ipv4   = [a.address for a in addr_list if a.family.name == "AF_INET"]
        ipv6   = [a.address for a in addr_list if a.family.name in ("AF_INET6","AddressFamily.AF_INET6")]
        mac    = next((a.address for a in addr_list if a.family.name in ("AF_LINK","AF_PACKET","AddressFamily.AF_LINK")), "")
        out.append({
            "name":    name,
            "ipv4":    ipv4,
            "ipv6":    ipv6,
            "mac":     mac,
            "is_up":   st.isup if st else False,
            "speed":   st.speed if st else 0,
            "mtu":     st.mtu if st else 0,
        })
    return out


def get_temps() -> list[dict]:
    import psutil
    try:
        temps = psutil.sensors_temperatures()
    except AttributeError:
        return []
    out = []
    for name, entries in temps.items():
        for e in entries:
            out.append({"sensor": name, "label": e.label or name,
                        "current": e.current, "high": e.high, "critical": e.critical})
    return out


# ── Network Monitor ───────────────────────────────────────────────────────────

def net_ping(host: str, count: int = 4, timeout: float = 2.0) -> dict:
    param  = ["-n", str(count)] if IS_WINDOWS else ["-c", str(count), "-W", str(int(timeout))]
    try:
        r = subprocess.run(
            ["ping"] + param + [host],
            capture_output=True, text=True, timeout=timeout * count + 5,
        )
        output = r.stdout + r.stderr
        alive  = r.returncode == 0
        # parse avg latency
        avg_ms = 0.0
        m = re.search(r"(?:avg|Average)[^=\d]*=?\s*[\d.]+/?([\d.]+)", output, re.IGNORECASE)
        if not m:
            m = re.search(r"time[<=]([\d.]+)\s*ms", output, re.IGNORECASE)
        if m:
            avg_ms = float(m.group(1))
        return {"host": host, "alive": alive, "avg_ms": avg_ms, "output": output}
    except Exception as e:
        return {"host": host, "alive": False, "avg_ms": 0.0, "output": str(e)}


def net_scan_ports(host: str, ports: list[int], timeout: float = 1.0) -> dict[int, bool]:
    results = {}
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                results[port] = True
        except Exception:
            results[port] = False
    return results


def net_dns_lookup(hostname: str) -> dict:
    import socket as _s
    result: dict = {"hostname": hostname, "a": [], "error": None}
    try:
        info = _s.getaddrinfo(hostname, None)
        result["a"] = list({i[4][0] for i in info})
        try:
            result["ptr"] = _s.gethostbyaddr(result["a"][0])[0]
        except Exception:
            result["ptr"] = ""
    except Exception as e:
        result["error"] = str(e)
    return result


def net_traceroute(host: str, max_hops: int = 20) -> list[dict]:
    cmd = ["tracert", "-h", str(max_hops), host] if IS_WINDOWS else \
          ["traceroute", "-m", str(max_hops), host]
    try:
        r    = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        hops = []
        for line in r.stdout.splitlines():
            m = re.match(r"\s*(\d+)\s+(?:([\d.]+)\s*ms.*?)([\w.\-]+|\*)", line)
            if m:
                hops.append({"ttl": int(m.group(1)), "ms": m.group(2), "host": m.group(3)})
        return hops
    except Exception as e:
        return [{"ttl": 0, "ms": "—", "host": str(e)}]


def net_list_connections(kind: str = "inet") -> list[dict]:
    import psutil
    conns = []
    try:
        for c in psutil.net_connections(kind=kind):
            conns.append({
                "fd":     c.fd,
                "type":   str(c.type),
                "laddr":  f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                "raddr":  f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                "status": c.status,
                "pid":    c.pid,
            })
    except Exception:
        pass
    return conns


def net_bandwidth_sample(interval: float = 1.0) -> dict:
    import psutil
    before = psutil.net_io_counters(pernic=True)
    time.sleep(interval)
    after  = psutil.net_io_counters(pernic=True)
    result = {}
    for nic in after:
        if nic in before:
            bw = after[nic].bytes_sent - before[nic].bytes_sent
            br = after[nic].bytes_recv - before[nic].bytes_recv
            result[nic] = {"tx_bps": bw / interval, "rx_bps": br / interval}
    return result


# ── Cleanup ───────────────────────────────────────────────────────────────────

def _scan_dir(directory: str, pattern: str = "*", older_than_days: float = 0) -> list[dict]:
    p     = Path(directory)
    items = []
    if not p.exists():
        return items
    cutoff = time.time() - older_than_days * 86400
    for child in p.rglob(pattern):
        try:
            if not child.is_file():
                continue
            st = child.stat()
            if older_than_days and st.st_mtime > cutoff:
                continue
            items.append({"path": str(child), "size": st.st_size,
                          "mtime": st.st_mtime, "action": "delete"})
        except Exception:
            pass
    return items


def cleanup_temp_files(cfg: dict, dry_run: bool = True) -> list[dict]:
    targets = []
    if IS_WINDOWS:
        targets += [os.environ.get("TEMP", ""), os.environ.get("TMP", ""),
                    os.path.join(os.environ.get("WINDIR","C:\\Windows"), "Temp")]
    else:
        targets += ["/tmp", str(Path.home() / ".cache")]
    items = []
    for t in filter(None, targets):
        items += _scan_dir(t, older_than_days=1)
    if not dry_run:
        cleanup_apply(items)
    return items


def cleanup_logs(cfg: dict, dry_run: bool = True) -> list[dict]:
    items = []
    if IS_LINUX:
        items += _scan_dir("/var/log", "*.gz")
        items += _scan_dir("/var/log", "*.old")
    elif IS_MAC:
        items += _scan_dir("/var/log", "*.gz")
        items += _scan_dir(str(Path.home() / "Library/Logs"), "*.log", older_than_days=7)
    elif IS_WINDOWS:
        items += _scan_dir(
            os.path.join(os.environ.get("WINDIR","C:\\Windows"), "Logs"),
            "*.log", older_than_days=30,
        )
    if not dry_run:
        cleanup_apply(items)
    return items


def cleanup_package_cache(cfg: dict, dry_run: bool = True) -> list[dict]:
    items = []
    cache_dirs = []
    if IS_LINUX:
        cache_dirs += ["/var/cache/apt/archives", "/var/cache/dnf",
                       str(Path.home() / ".cache/pip")]
    elif IS_MAC:
        cache_dirs += [str(Path.home() / "Library/Caches/pip"),
                       "/Library/Caches/Homebrew"]
    elif IS_WINDOWS:
        cache_dirs += [str(Path.home() / "AppData/Local/pip/Cache")]
    for d in cache_dirs:
        items += _scan_dir(d)
    if not dry_run:
        cleanup_apply(items)
    return items


def cleanup_downloads(cfg: dict, older_than_days: int = 30, dry_run: bool = True) -> list[dict]:
    dl   = Path.home() / "Downloads"
    items = _scan_dir(str(dl), older_than_days=older_than_days)
    if not dry_run:
        cleanup_apply(items)
    return items


def cleanup_apply(actions: list[dict]) -> dict:
    deleted, freed, errors = 0, 0, []
    for a in actions:
        if a.get("action") != "delete":
            continue
        try:
            p = Path(a["path"])
            if p.is_file():
                freed += p.stat().st_size
                p.unlink()
                deleted += 1
        except Exception as e:
            errors.append(str(e))
    return {"deleted": deleted, "freed_bytes": freed, "errors": errors}


def cleanup_summary(items: list[dict]) -> dict:
    return {"count": len(items), "total_bytes": sum(i.get("size", 0) for i in items)}


# ── SSH Manager ───────────────────────────────────────────────────────────────

def ssh_test_connection(host_cfg: dict) -> dict:
    host = host_cfg.get("host","")
    port = int(host_cfg.get("port", 22))
    t0   = time.time()
    try:
        with socket.create_connection((host, port), timeout=3):
            ms = (time.time() - t0) * 1000
        return {"reachable": True, "latency_ms": ms, "error": None}
    except Exception as e:
        return {"reachable": False, "latency_ms": 0.0, "error": str(e)}


def ssh_connect(host_cfg: dict, password: str | None = None):
    paramiko = _optional("paramiko>=3.4.0", "paramiko")
    client   = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw: dict = {
        "hostname": host_cfg["host"],
        "port":     int(host_cfg.get("port", 22)),
        "username": host_cfg.get("user", ""),
        "timeout":  10,
    }
    key_path = host_cfg.get("key_path","")
    if key_path and Path(key_path).exists():
        kw["key_filename"] = key_path
    elif password:
        kw["password"] = password
    client.connect(**kw)
    return client


def ssh_run(client, command: str, timeout: float = 30.0) -> dict:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    return {
        "stdout":    stdout.read().decode(errors="replace"),
        "stderr":    stderr.read().decode(errors="replace"),
        "exit_code": stdout.channel.recv_exit_status(),
    }


def ssh_list_hosts(cfg: dict) -> list[dict]:
    hosts = cfg.get("ssh_hosts", [])
    out   = []
    for h in hosts:
        info = ssh_test_connection(h)
        out.append({**h, "reachable": info["reachable"], "latency_ms": info["latency_ms"]})
    return out


def ssh_add_host(cfg: dict, alias: str, host: str, port: int,
                 user: str, key_path: str) -> dict:
    cfg["ssh_hosts"].append({"alias": alias, "host": host,
                             "port": port, "user": user, "key_path": key_path})
    from sysknife import save_config
    save_config(cfg)
    return cfg


def ssh_remove_host(cfg: dict, alias: str) -> dict:
    cfg["ssh_hosts"] = [h for h in cfg["ssh_hosts"] if h["alias"] != alias]
    from sysknife import save_config
    save_config(cfg)
    return cfg
