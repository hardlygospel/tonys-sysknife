<div align="center">

# ⚔️ Tony's Sysadmin Swiss Army Knife

[![Version](https://img.shields.io/badge/version-1.0.0-cba6f7?style=flat-square&labelColor=1e1e2e)](https://github.com/hardlygospel/tonys-sysknife)
[![Python](https://img.shields.io/badge/Python-3.9%2B-89b4fa?style=flat-square&logo=python&logoColor=white&labelColor=1e1e2e)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-a6e3a1?style=flat-square&labelColor=1e1e2e)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-89dceb?style=flat-square&labelColor=1e1e2e)](https://github.com/hardlygospel/tonys-sysknife)
[![Tab Autocomplete](https://img.shields.io/badge/Tab-Autocomplete-f9e2af?style=flat-square&labelColor=1e1e2e)](https://github.com/hardlygospel/tonys-sysknife)

**One tool for everything sysadmins deal with every morning.**  
Morning checklist · Active Directory · Azure AD · System Health · Network · Cleanup · SSH · Settings

*Rich TUI on Linux and macOS. Tkinter dark GUI on Windows. Tab autocomplete everywhere.*

</div>

---

## Features at a glance

<table>
<tr>
<td width="50%">

**☀ Morning Checklist**
- Disk, RAM, CPU, and swap usage with thresholds
- systemd / launchd service status
- Pending system updates check
- Ping configured hosts
- TLS certificate expiry (configurable warn days)
- Backup path age check
- Open port probing
- System uptime summary
- Non-interactive `--check` mode (exit 0=ok, 1=issues)

**🏢 Active Directory**
- Search users by name or sAMAccountName
- Unlock locked-out accounts
- Reset passwords (force change on next logon optional)
- Enable / disable accounts
- List groups with member counts
- Add / remove users from groups

</td>
<td width="50%">

**☁ Azure AD**
- List and filter users by name or UPN
- Enable / disable Azure AD accounts
- MFA registration status per user
- List Azure AD groups
- List group members
- List Azure AD joined / registered devices
- List Enterprise Applications

**💚 System Health · 🌐 Network · 🧹 Cleanup**
- CPU per-core, memory breakdown, disk per-partition
- Top 10 processes by CPU, network I/O counters
- Ping, port check, DNS (A/AAAA/MX/TXT), traceroute
- Temp files, log rotation, core dumps, package caches, trash

</td>
</tr>
</table>

---

## Quick Start

### Linux / macOS

```bash
git clone https://github.com/hardlygospel/tonys-sysknife
cd tonys-sysknife
bash setup.sh
```

Or run directly (auto-installs core deps):

```bash
python3 sysknife.py
```

### Windows

```bat
git clone https://github.com/hardlygospel/tonys-sysknife
cd tonys-sysknife
setup.bat
```

Or:

```bat
python sysknife.py
```

The GUI launches automatically on Windows. Use `--tui` to force the terminal interface instead.

---

## CLI flags

```
python3 sysknife.py [options]

  --check           Run morning checklist non-interactively (exit 0=all-ok, 1=issues)
  --module NAME     Open a module directly (morning/ad/azure/health/network/cleanup/ssh/settings)
  --tui             Force TUI even on Windows
  --version         Print version
```

**Examples:**

```bash
# Morning health check in CI/cron
python3 sysknife.py --check && echo "All clear" || echo "Issues detected"

# Jump straight to network tools
python3 sysknife.py --module network

# Open settings directly
python3 sysknife.py --module settings
```

---

## Navigation (TUI)

| Key / Command | Action |
|---|---|
| `1` – `8` | Select module |
| module name | e.g. type `morning`, `ad`, `health` |
| `h` / `help` | Show help screen |
| `q` / `quit` | Exit |
| `Tab` | Autocomplete current input |
| `↑` / `↓` | Scroll through input history |
| `Ctrl+C` | Cancel current operation |

---

## Optional Dependencies

Core features (Rich TUI, system health, ping, cleanup) need only the auto-installed packages.  
Some modules require extras:

| Module | Package | Install |
|---|---|---|
| Active Directory | `ldap3` | `pip install ldap3` |
| Azure AD | `msal` | `pip install msal` |
| SSH Manager | `paramiko` | `pip install paramiko` |

The tool prompts you to install these when you first open a module that needs them.

---

## Configuration

Settings are saved to `~/.sysknife/config.json`. Passwords and secrets are base64-encoded (light obfuscation, not encryption — use a secrets manager for high-security environments).

### Active Directory

```json
"ad": {
  "server":       "ldap://dc.corp.local",
  "base_dn":      "DC=corp,DC=local",
  "user":         "CORP\\svc_sysknife",
  "password_enc": "base64-encoded-password"
}
```

### Azure AD (App Registration)

Create an App Registration in Azure with these Graph API permissions (Application type, admin-consented):

| Permission | Used for |
|---|---|
| `User.Read.All` | List / search users |
| `User.ReadWrite.All` | Enable / disable users |
| `Group.Read.All` | List groups and members |
| `Device.Read.All` | List devices |
| `Application.Read.All` | List Enterprise Applications |
| `UserAuthenticationMethod.Read.All` | MFA status |

```json
"azure": {
  "tenant_id":          "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_id":          "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "client_secret_enc":  "base64-encoded-secret"
}
```

### Morning Checklist

```json
"morning": {
  "ping_hosts":     ["8.8.8.8", "1.1.1.1", "gateway.corp.local"],
  "cert_paths":     ["/etc/ssl/certs/mycert.pem"],
  "backup_paths":   ["/mnt/backups"],
  "disk_warn_pct":  85,
  "mem_warn_pct":   90,
  "cert_warn_days": 30
}
```

---

## Morning Checklist in Cron

```bash
# /etc/cron.d/sysknife — run at 07:00 Mon–Fri, email on failure
0 7 * * 1-5  sysadmin  python3 /opt/sysknife/sysknife.py --check \
  || mail -s "⚠ Sysknife morning issues" ops@corp.local
```

---

## Screenshots

```
╔══════════════════════════════════════════════════════════════╗
║   Tony's Sysadmin Swiss Army Knife                          ║
║   v1.0.0  · Morning Checklist · AD · Azure · Health · …    ║
╚══════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────┐
│  Main Menu                                                   │
│                                                              │
│  1  ☀  Morning Checklist   Disk · RAM · CPU · services …   │
│  2  🏢  Active Directory    Search · unlock · reset · groups │
│  3  ☁  Azure AD            Users · groups · devices · MFA  │
│  4  💚  System Health       CPU · memory · disk · processes  │
│  5  🌐  Network             Ping · port check · DNS · trace  │
│  6  🧹  Cleanup             Temp · logs · cores · pkg cache  │
│  7  🔐  SSH Manager         Connect · run · add · remove    │
│  8  ⚙  Settings            AD · Azure · morning thresholds │
└──────────────────────────────────────────────────────────────┘
  h  help  ·  q  quit  ·  Tab  complete  ·  ↑↓  history

  › _
```

---

## Project Structure

```
tonys-sysknife/
├── sysknife.py      Entry point — bootstrap, config, arg parsing
├── modules.py       All backend logic (checks, AD, Azure, SSH, cleanup)
├── tui.py           Rich + prompt_toolkit TUI (Linux / macOS / Windows --tui)
├── gui.py           tkinter dark GUI (Windows)
├── requirements.txt Dependencies
├── setup.sh         Linux / macOS launcher
├── setup.bat        Windows launcher
└── LICENSE          GPL-3.0-or-later
```

---

## License

```
Tony's Sysadmin Swiss Army Knife
Copyright (C) 2024-2026 Tony (hardlygospel)
GPL-3.0-or-later — https://www.gnu.org/licenses/gpl-3.0
```

<div align="center">

Built by Tony · [github.com/hardlygospel](https://github.com/hardlygospel)

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-a6e3a1?style=flat-square&labelColor=1e1e2e)](https://www.gnu.org/licenses/gpl-3.0)

</div>
