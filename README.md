<div align="center">

# ⚔ Tony's Sysadmin Swiss Army Knife

### *Everything a sysadmin reaches for in the morning — in one keypress.*

[![Version](https://img.shields.io/badge/version-2.0.0-cba6f7?style=for-the-badge&labelColor=1e1e2e)](https://github.com/hardlygospel/tonys-sysknife/releases)
[![Python](https://img.shields.io/badge/Python-3.9%2B-89b4fa?style=for-the-badge&logo=python&logoColor=white&labelColor=1e1e2e)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-a6e3a1?style=for-the-badge&labelColor=1e1e2e)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform](https://img.shields.io/badge/Linux%20%7C%20macOS%20%7C%20Windows-89dceb?style=for-the-badge&labelColor=1e1e2e)](#installation)

[![Tab Autocomplete](https://img.shields.io/badge/Tab-Autocomplete-f9e2af?style=flat-square&labelColor=1e1e2e)](#navigation)
[![Live Watch](https://img.shields.io/badge/Live-Watch%20Mode-f38ba8?style=flat-square&labelColor=1e1e2e)](#system-health)
[![HTML Report](https://img.shields.io/badge/HTML-Report-fab387?style=flat-square&labelColor=1e1e2e)](#reports--automation)
[![Cron Friendly](https://img.shields.io/badge/Cron-Friendly-94e2d5?style=flat-square&labelColor=1e1e2e)](#reports--automation)
[![Zero Config](https://img.shields.io/badge/Zero-Config-cba6f7?style=flat-square&labelColor=1e1e2e)](#first-run)

**One terminal. Ten modules. Every sysadmin reflex covered.**

```
                    ⚔  TONY'S SYSADMIN SWISS ARMY KNIFE  ⚔
   ─────────────────────────────────────────────────────────────────────
     Morning · Active Directory · Azure AD · System Health · Network
              Cleanup · SSH · Processes · Logs · Settings
   ─────────────────────────────────────────────────────────────────────
                    Rich TUI · Dark GUI · Tab autocomplete
```

</div>

---

## Table of Contents

- [Why Sysknife?](#why-sysknife)
- [Quick Start](#quick-start)
- [Features at a Glance](#features-at-a-glance)
- [The 10 Modules](#the-10-modules)
- [CLI Flags](#cli-flags)
- [Reports & Automation](#reports--automation)
- [Configuration](#configuration)
- [Permissions](#permissions)
- [Troubleshooting](#troubleshooting)
- [Project Layout](#project-layout)
- [License](#license)

---

## Why Sysknife?

A sysadmin's morning is the same five-minute scramble across ten different tools:
disk space → service status → ping the gateway → unlock that AD account → check Azure
license assignments → empty `/tmp` → tail `journalctl` → SSH to the staging box → kill
that runaway Python process → see if backups ran.

**Sysknife is one keystroke away from all of it.** It speaks LDAP, Microsoft Graph,
SSH, systemd, launchd, Windows Event Log, psutil, and `ping` — and turns each into a
clean Rich-rendered table or a one-page HTML report.

It runs three ways:

- 🐧 **Linux / macOS** — Rich TUI with tab autocomplete and input history
- 🪟 **Windows** — dark Catppuccin Mocha tkinter GUI (auto-detected)
- 🤖 **Cron / CI** — `--check --report` saves an HTML morning report and exits with a non-zero code if anything failed

---

## Quick Start

### Linux / macOS

```bash
git clone https://github.com/hardlygospel/tonys-sysknife
cd tonys-sysknife
bash setup.sh
```

`setup.sh` checks for Python 3.9+, installs the four required deps, and launches Sysknife.

### Windows

```bat
git clone https://github.com/hardlygospel/tonys-sysknife
cd tonys-sysknife
setup.bat
```

The dark GUI launches automatically. Pass `--tui` to use the terminal interface instead.

### Or just run it

```bash
python3 sysknife.py            # auto-installs missing core deps on first run
```

---

## Features at a Glance

<table>
<tr>
<td width="50%" valign="top">

### 🩺 Always-on diagnostics
- **Live watch mode** — auto-refreshing CPU/RAM/swap bars + top procs (Ctrl+C exits)
- **Morning checklist** — disk, RAM, CPU, swap, services, updates, ping hosts, TLS expiry, backup age, listening ports, uptime
- **HTML report** — single self-contained file with a Catppuccin theme, opens in your browser
- **Battery, temps, load average** — laptop-aware
- **Top processes** sorted by CPU or memory
- **Process tree** for the whole system or a sub-tree

### 🔐 Identity & directory
- **Active Directory** (LDAP/NTLM) — search, unlock, password reset, enable/disable, group membership add/remove
- **Azure AD** (Microsoft Graph) — list & filter users, enable/disable, MFA registration status, list groups & members, devices, enterprise applications

</td>
<td width="50%" valign="top">

### 🌐 Network toolbox
- **Ping** any host or all configured morning hosts at once
- **Port check** & **port scan** of common services
- **DNS lookup** for A / AAAA / MX / TXT / NS / CNAME
- **Traceroute** to anywhere
- **HTTP check** — status, redirect chain, timing, server, content-type
- **SSL/TLS inspection** — issuer, expiry days, SANs, cipher, TLS version
- **WHOIS** for any domain
- **Public IP** (multi-provider failover) and **local interfaces** in one view

### 🧹 Cleanup & investigation
- **Dry-run scan** of temp / logs / cores / pkg cache / trash / old downloads
- **Big files finder** — top 25 largest files in any directory
- **APPLY mode** with confirmation — actually free disk space, never silently
- **SSH manager** — saved-host shortcuts with key-path or password auth
- **Process kill** — by PID or name, TERM or KILL
- **Logs viewer** — journalctl / unified log / Event Log with severity coloring

</td>
</tr>
</table>

---

## The 10 Modules

### 1. ☀ Morning Checklist

Runs every check the team does manually each morning, in one keystroke.

| Check     | Detail                                                                          |
|-----------|---------------------------------------------------------------------------------|
| Disk      | Per-partition usage; warns at 85%, fails at 95% (configurable)                  |
| Memory    | RAM + swap usage with thresholds                                                |
| CPU       | Current load and core count                                                     |
| Services  | systemd `--failed`, launchctl exit-code != 0, Windows non-running auto services |
| Updates   | `apt list --upgradable`, `softwareupdate -l`, Windows Update count              |
| Ping      | All hosts in `morning.ping_hosts`                                               |
| Certs     | TLS certificate expiry on local PEM files                                       |
| Backups   | Last-modified time of configured backup paths                                   |
| Ports     | Snapshot of LISTEN-state TCP ports                                              |
| Uptime    | Boot time + duration                                                            |

**Outputs:** terminal table · HTML report · JSON · plain text.

```text
[morning] › report
  ✓  Report saved to: ~/sysknife-report-20260504-091200.html
  Opened in browser.
```

### 2. 🏢 Active Directory

LDAP/NTLM-based AD operations against your DC.

| Command       | What it does                                       |
|---------------|----------------------------------------------------|
| `search`      | sAMAccountName / display name / mail substring     |
| `unlock`      | Clear `lockoutTime`                                |
| `reset`       | Set `unicodePwd`, optional must-change-at-logon    |
| `enable` /    | Toggle bit 2 in `userAccountControl`               |
| `disable`     |                                                    |
| `groups`      | List groups with member counts (filterable)        |
| `addgroup`    | Add user to group via `member` attribute           |
| `removegroup` | Remove user from group                             |

Requires `ldap3` (auto-prompted on first use).

### 3. ☁ Azure AD

Microsoft Graph API operations using a confidential-client app registration.

| Command   | Graph endpoint                                       |
|-----------|------------------------------------------------------|
| `users`   | `/users` with `startswith(displayName, ...)` filter  |
| `enable` /| `PATCH /users/{id}` with `accountEnabled`            |
| `disable` |                                                      |
| `mfa`     | `/users/{id}/authentication/methods`                 |
| `groups`  | `/groups`                                            |
| `members` | `/groups/{id}/members` (resolves names to GUIDs)     |
| `devices` | `/devices` — managed/compliant flags                 |
| `apps`    | `/servicePrincipals` — Enterprise Applications       |

Requires `msal` + `requests` (auto-prompted on first use).

### 4. 💚 System Health

Real-time look at the box — including a [btop](https://github.com/aristocratos/btop)-style live dashboard.

| Command   | What it shows                                       |
|-----------|-----------------------------------------------------|
| `watch`   | **Live auto-refreshing** CPU/RAM/swap bars + top procs (2× per second) |
| `cpu`     | Per-core utilization, frequency                     |
| `memory`  | RAM and swap with absolute and percent              |
| `disk`    | Per-partition mount/device/filesystem/usage         |
| `procs`   | Top 10 by CPU                                       |
| `netio`   | Per-interface bytes / packets / errors              |
| `services`| Failed / non-running auto services                  |
| `battery` | Charge %, plugged-in state, time remaining          |
| `temps`   | Temperature sensors (where available)               |
| `load`    | 1/5/15-minute load average + core count             |
| `all`     | Full snapshot (CPU + memory + load + disk + svcs)   |

### 5. 🌐 Network

Eleven network commands for the same prompt.

| Command   | What it does                                                          |
|-----------|-----------------------------------------------------------------------|
| `ping`    | Single host, or `all` for the morning ping list                       |
| `port`    | TCP connect test on one port                                          |
| `dns`     | A / AAAA / MX / TXT / NS / CNAME lookup                               |
| `trace`   | tracert / traceroute                                                  |
| `http`    | HTTPS GET — status, final URL, redirects, timing, server, content-type|
| `ssl`     | TLS cert: issuer, validity window, days left, SANs, cipher, version   |
| `whois`   | Domain WHOIS (registrar, expiry, name servers)                        |
| `pubip`   | Your public IP via ipify → ifconfig.me → icanhazip                    |
| `myips`   | All local interfaces with IPv4/IPv6/MAC + link state + speed          |
| `scan`    | TCP connect-scan of common ports (FTP, SSH, HTTP, SMTP, Postgres, …)  |

### 6. 🧹 Cleanup

Always **dry-run first** — never delete without your sign-off.

| Command     | Targets                                                        |
|-------------|----------------------------------------------------------------|
| `scan`      | All categories at once (summary report)                        |
| `temp`      | `/tmp`, `~/.cache`, `%TEMP%`, `%WINDIR%\Temp`                  |
| `logs`      | `*.gz`, `*.old`, `*.1` in `/var/log` (>7 days), Win logs       |
| `cores`     | `/var/lib/systemd/coredump`, `/var/crash`, `/cores`, minidumps |
| `pkgcache`  | `apt`/`dnf` archives, `pip` cache, Homebrew cache              |
| `trash`     | `~/.Trash`, `~/.local/share/Trash`, Recycle Bin                |
| `downloads` | `~/Downloads` files older than N days                          |
| `big`       | Top 25 files ≥ 50 MB in any directory                          |
| `apply`     | **Confirm-then-delete** the most recent dry-run result         |

### 7. 🔐 SSH Manager

Saved-host shortcuts. Keys preferred; passwords supported.

```text
[SSH] › list
┌─────────────────────────────────────────────────────────────────┐
│ Saved SSH Hosts                                                 │
├──────────┬──────────────────┬──────┬───────────┬────────────────┤
│ Alias    │ Host             │ Port │ User      │ Key            │
│ prod-web │ web1.corp.local  │ 22   │ deploy    │ ~/.ssh/prod_ed │
│ db       │ 10.0.4.21        │ 22   │ dba       │                │
└──────────┴──────────────────┴──────┴───────────┴────────────────┘

[SSH] › run
  Alias › prod-web
  Command › systemctl status nginx
```

### 8. ⚙ Processes

Find, sort, search, kill — the essentials.

| Command  | What it does                                              |
|----------|-----------------------------------------------------------|
| `list`   | Top 30 by CPU                                             |
| `mem`    | Top 30 by memory                                          |
| `search` | Filter by name or cmdline substring                       |
| `tree`   | ASCII process tree (full, or a sub-tree by root PID)      |
| `port`   | Find process(es) listening on a port                      |
| `kill`   | Kill by PID or exact name; `force` sends SIGKILL          |

### 9. 📜 Logs

Cross-platform log viewer with error-line coloring.

| Source           | Backend                                                |
|------------------|--------------------------------------------------------|
| Linux            | `journalctl -n N -u UNIT -p LEVEL --since 1h`          |
| macOS            | `log show --last 30m --style compact`                  |
| Windows          | `Get-EventLog -LogName <System/Application/Security>`  |

| Command  | What it does                                  |
|----------|-----------------------------------------------|
| `recent` | Last 100 lines from the system log            |
| `errors` | Last 100 ERROR-level entries                  |
| `unit`   | Last 100 lines for a specific service/source  |
| `list`   | Show available active services / log sources  |

### 10. 🔧 Settings

Keep your config in `~/.sysknife/config.json` — passwords/secrets are base64-obfuscated.

| Section   | What you set                                                          |
|-----------|-----------------------------------------------------------------------|
| `ad`      | Server URI, base DN, bind user, password                              |
| `azure`   | Tenant ID, client ID, client secret                                   |
| `morning` | Ping hosts, cert paths, backup paths, disk/mem/cert thresholds        |
| `theme`   | dark / light                                                          |
| `show`    | Print current config (passwords masked)                               |

---

## CLI Flags

```text
python3 sysknife.py [options]

  --check              Run morning checklist non-interactively (exit 0=ok, 1=issues)
  --report [PATH]      With --check: save HTML (or .json by extension) report.
                       Use --report auto to pick the path automatically (~/).
  --module NAME        Open a module directly:
                         morning · ad · azure · health · network · cleanup
                         · ssh · procs · logs · settings
  --watch              With --module health: open the live dashboard
  --tui                Force TUI even on Windows (skip the GUI)
  --version            Print version
```

### Examples

```bash
# CI / cron — fail the build if anything is wrong, drop a report on disk
python3 sysknife.py --check --report auto

# Live system dashboard, btop-style
python3 sysknife.py --module health --watch

# Jump straight to network tools
python3 sysknife.py --module network

# Open settings to configure AD / Azure / hosts
python3 sysknife.py --module settings

# Force the terminal UI on Windows
python3 sysknife.py --tui
```

---

## Reports & Automation

### Cron (Linux / macOS)

```cron
# /etc/cron.d/sysknife — every weekday at 07:00, email if anything fails
0 7 * * 1-5 sysadmin python3 /opt/sysknife/sysknife.py --check --report auto \
  || mail -s "⚠ Sysknife morning issues" -a /home/sysadmin/sysknife-report-*.html \
       ops@corp.local
```

### systemd timer (Linux)

```ini
# /etc/systemd/system/sysknife.service
[Unit]
Description=Sysknife morning checklist
[Service]
Type=oneshot
User=sysadmin
ExecStart=/usr/bin/python3 /opt/sysknife/sysknife.py --check --report auto

# /etc/systemd/system/sysknife.timer
[Unit]
Description=Run Sysknife every weekday at 07:00
[Timer]
OnCalendar=Mon..Fri 07:00:00
Persistent=true
[Install]
WantedBy=timers.target
```

### Task Scheduler (Windows)

```powershell
# Create a scheduled task that runs the morning check every weekday at 07:00
$action = New-ScheduledTaskAction -Execute "python.exe" `
  -Argument "C:\Tools\sysknife\sysknife.py --check --report auto"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Mon,Tue,Wed,Thu,Fri -At 07:00
Register-ScheduledTask -TaskName "Sysknife Morning" -Action $action -Trigger $trigger
```

### JSON output for dashboards

`--report report.json` writes machine-readable output for ingestion into Grafana,
Datadog, Splunk, or any HTTP webhook:

```json
{
  "host": "web1.corp.local",
  "platform": "linux",
  "generated": "2026-05-04T07:00:00",
  "results": [
    { "name": "Disk /",   "status": "ok",   "detail": "32% used (24.1 GB free of 460.4 GB)", "value": 32 },
    { "name": "Services", "status": "fail", "detail": "2 failed", "items": ["nginx.service", "redis.service"] }
  ]
}
```

---

## Configuration

Settings live at `~/.sysknife/config.json`. The Settings panel writes it for you, or
edit it by hand. Defaults are merged in on every launch, so new keys appear automatically
when you upgrade.

### Active Directory

```json
"ad": {
  "server":       "ldap://dc.corp.local",
  "base_dn":      "DC=corp,DC=local",
  "user":         "CORP\\svc_sysknife",
  "password_enc": "base64-encoded-password"
}
```

### Azure AD — App Registration

In the Azure Portal create an **App Registration**, add a **Client Secret**, and grant
the following **Application** Graph permissions (admin-consented):

| Permission                              | Used for                              |
|-----------------------------------------|---------------------------------------|
| `User.Read.All`                         | List / search / inspect users         |
| `User.ReadWrite.All`                    | Enable / disable accounts             |
| `Group.Read.All`                        | List groups and members               |
| `Device.Read.All`                       | List devices                          |
| `Application.Read.All`                  | List Enterprise Applications          |
| `UserAuthenticationMethod.Read.All`     | MFA registration status               |

Then save the IDs in `~/.sysknife/config.json`:

```json
"azure": {
  "tenant_id":         "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_id":         "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_secret_enc": "base64-encoded-secret"
}
```

### Morning checklist

```json
"morning": {
  "ping_hosts":     ["8.8.8.8", "1.1.1.1", "gateway.corp.local"],
  "cert_paths":     ["/etc/ssl/certs/wildcard.pem"],
  "backup_paths":   ["/mnt/backups/latest"],
  "disk_warn_pct":  85,
  "mem_warn_pct":   90,
  "cert_warn_days": 30,
  "checks":         ["disk","memory","cpu","swap","services","updates",
                     "ping","certs","backups","ports","uptime"]
}
```

### SSH hosts

```json
"ssh_hosts": [
  { "alias": "prod-web", "hostname": "web1.corp.local",
    "port": 22, "username": "deploy", "key_path": "~/.ssh/prod_ed25519" },
  { "alias": "db",       "hostname": "10.0.4.21",
    "port": 22, "username": "dba",    "key_path": "" }
]
```

> **A note on secrets:** passwords and the Azure client secret are base64-encoded —
> this keeps them off-screen and out of casual `cat ~/.sysknife/config.json`, but is
> **not encryption**. For high-security environments, use a real secrets manager
> (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault) and wire it into the config
> via a small shim or environment variable.

---

## Permissions

Some operations need elevated privileges — Sysknife will tell you when, and how.

| Operation                                       | Linux / macOS | Windows                |
|-------------------------------------------------|---------------|------------------------|
| Reading `/var/log` / journalctl                 | usually fine  | n/a                    |
| Listing failed systemd units                    | fine          | n/a                    |
| Windows Update query                            | n/a           | runs as standard user  |
| `proc_find_by_port` (matching PID to listener)  | needs `sudo`  | needs **Administrator**|
| `proc_kill` for processes you don't own         | needs `sudo`  | needs Administrator    |
| Cleaning system temp / cache directories        | usually `sudo`| Administrator          |
| Reading other users' `~/Downloads`              | `sudo`        | Administrator          |
| AD / Azure modifications                        | requires bind user with appropriate AD/Graph rights |  |

For the morning check + reporting flow, **no elevated privileges are required**.

---

## Troubleshooting

### `pip install` complains about `--break-system-packages`

`setup.sh` already handles this — it tries `--user` first, then falls back to
`--user --break-system-packages`. If you're running outside `setup.sh`, install into
a venv:

```bash
python3 -m venv ~/.venv/sysknife
source ~/.venv/sysknife/bin/activate
pip install -r requirements.txt
python3 sysknife.py
```

### The TUI menu wraps oddly on a very wide terminal

The banner and menu are now constrained to 96 columns regardless of your terminal width.
If you're still seeing wrap issues, check that your terminal renders Unicode box-drawing
correctly (most modern terminals do; ancient PuTTY may not).

### Process tree shows nothing

Some kernel-level processes report themselves as their own parent, which used to break
the walker. v2.0.0 handles this — if you're seeing an empty tree, you're probably on
v1.0.0; pull the latest commit.

### "Optional package not installed" errors

Optional modules need extra deps:

```bash
pip install ldap3      # Active Directory
pip install msal       # Azure AD
pip install paramiko   # SSH manager
pip install requests   # already required, but listed for completeness
```

### Watch mode prints garbage after exit

The Live dashboard takes over the screen with `screen=True` so it can repaint cleanly.
Some terminals leave artifacts on exit — press `clear` or `Ctrl+L` to repaint.

---

## Project Layout

```
tonys-sysknife/
├── sysknife.py        Entry point — bootstrap, config, arg parsing
├── modules.py         All backend logic (1200+ lines, no UI)
├── tui.py             Rich + prompt_toolkit TUI (Linux/macOS/Windows --tui)
├── gui.py             tkinter dark GUI (Windows)
├── requirements.txt   Required + optional dependencies
├── setup.sh           Linux/macOS launcher
├── setup.bat          Windows launcher
├── LICENSE            GPL-3.0-or-later
└── README.md          You are here
```

### Architecture

```
                   ┌──────────────────────┐
                   │     sysknife.py      │  CLI flags · config load · OS detection
                   └──────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       ┌──────────────┐                ┌──────────────┐
       │   tui.py     │                │   gui.py     │
       │ Rich panels  │                │ tk panels    │
       └──────┬───────┘                └──────┬───────┘
              └───────────────┬───────────────┘
                              ▼
                       ┌──────────────┐
                       │  modules.py  │
                       │ Backend logic│
                       └──────┬───────┘
                              ▼
              ┌───────────────┴────────────────┐
              ▼                                ▼
       psutil · ldap3 · msal · paramiko · subprocess
```

`modules.py` is **UI-free**. Every public function returns a `dict`, `list[dict]`, or
`CheckResult` — both UIs (and any future one) render the same data.

---

## Changelog

### v2.0.0 (2026-05-04)
- New module: **Processes** — list, search, kill, find-by-port, ASCII tree
- New module: **Logs** — journalctl / Console / Event Log viewer with severity coloring
- **Watch mode** — live auto-refreshing system health dashboard
- Network expansions — HTTP check, SSL inspection, WHOIS, public IP, port scan, local IPs
- Cleanup expansions — `apply` mode (with confirmation), big-files finder, old downloads
- Health expansions — battery, temperatures, load average
- HTML / JSON / text reports for the morning checklist
- Cron-friendly `--report` flag
- Status bar shows hostname / uptime / load / time on the main menu
- Bug fixes: process-tree root detection, kernel self-parent loop

### v1.0.0
- Initial release: morning checklist, AD, Azure, system health, network, cleanup, SSH

---

## Contributing

PRs welcome — especially:

- Sensible defaults for more package managers in `cleanup_package_cache`
- Battery / temperature support on more platforms
- Additional Graph endpoints (sign-in logs, conditional-access policies)
- Localization

If you're filing a bug, please include `python3 sysknife.py --version` and the OS.

---

## License

```
Tony's Sysadmin Swiss Army Knife
Copyright (C) 2024-2026 Tony (hardlygospel)
GPL-3.0-or-later — https://www.gnu.org/licenses/gpl-3.0
```

<div align="center">

Built by Tony · [github.com/hardlygospel](https://github.com/hardlygospel)

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-a6e3a1?style=for-the-badge&labelColor=1e1e2e)](https://www.gnu.org/licenses/gpl-3.0)
[![Stars](https://img.shields.io/github/stars/hardlygospel/tonys-sysknife?style=for-the-badge&color=cba6f7&labelColor=1e1e2e)](https://github.com/hardlygospel/tonys-sysknife/stargazers)

</div>
