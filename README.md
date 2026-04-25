# SSH Network Manager

SSH Network Manager is a web-based management platform designed for network administrators to configure and monitor OpenWrt and Teltonika routers without using the command line.

The system focuses on providing a clear graphical interface for daily router operations such as DHCP configuration, WiFi management, port forwarding, and device monitoring, while keeping all communication with the router over SSH.

---

# Project Goals

The main goals of the system are:

- replace manual SSH command entry with a clean web interface
- centralize router configuration in one place
- reduce time needed for routine network operations
- make OpenWrt and Teltonika routers accessible to less technical users
- provide live status and diagnostic information about connected devices

---

# Core Concepts

The system is built around several key ideas.

## SSH As The Single Source Of Truth

The application does not store router configuration locally.

Every operation is executed live on the router through SSH using paramiko.

This means:

- the interface always shows the current router state
- changes made through the CLI by other administrators are immediately visible
- there is no synchronization layer that can go out of date

---

## Form Validation Before SSH Execution

Sending invalid data over SSH can break router configuration.

The application validates every input before any command is executed.

Validation includes:

- MAC address format
- IP address format
- hostname rules
- port number ranges

---

## Auto Detection Of Network Topology

Different router models expose ports and interfaces differently.

The application detects the topology automatically by parsing:

- swconfig output
- UCI VLAN definitions
- WAN device configuration

This allows the same code to work on both OpenWrt and Teltonika devices without per-model configuration.

---

## Protocol Specific Parsers

Each part of the router speaks a different language.

The application includes dedicated parsers for:

- DHCP leases from /tmp/dhcp.leases
- LTE signal data from AT+QENG, AT+CSQ and AT+QNWINFO
- WiFi info from iwinfo
- ARP table from /proc/net/arp
- system status from /proc/stat and /proc/loadavg

---

# Technology Stack

Backend

- Python 3
- Flask
- paramiko (SSH client)

Frontend

- Jinja2 templates
- HTML
- CSS

Target devices

- OpenWrt routers
- Teltonika routers (RUT955 and similar)

Planned additions

- PostgreSQL (multi-device management)
- FastAPI (REST API layer)
- Redis (status caching)
- Docker (deployment)

---

# System Architecture

High level architecture:

Browser (HTML form)

↓

Flask routes (app/routes.py)

↓

SSH utility layer (app/ssh_utils.py)

↓

paramiko SSH session

↓

Router (OpenWrt or Teltonika)


---

# Key Features

## Connection Features

- SSH login with IP, username and password
- session-based credential storage during the user session
- logout that clears the session

## Configuration Features

- DHCP range, limit and lease time
- DHCP static reservations (add and remove)
- WiFi SSID, password and encryption per radio
- LAN IP, netmask, gateway and DNS
- hostname change
- port forwarding rules (add and remove)

## Monitoring Features

- live device status (CPU usage, RAM, uptime, load average)
- network interface state (up or down)
- LTE signal information for Teltonika devices (RSRP, RSRQ, SINR, operator)
- system logs from logread or dmesg
- list of connected devices from ARP table with hostnames from DHCP leases
- ping from the router to a target IP
- automatic detection of LAN, WAN and CPU ports

## Operational Features

- direct SSH terminal in the browser
- interface up and down
- router reboot

---

# Project Structure

## Backend Development

The backend application lives in `Network Menager/` and is built with Flask and paramiko.

Run it locally with:

```bash
cd "Network Menager"
python -m venv venv
source venv/bin/activate
pip install flask paramiko
python run.py
```

On Windows the activation command is:

```bash
venv\Scripts\activate
```

To run on a different host or port, set:

```bash
FLASK_RUN_HOST=0.0.0.0
FLASK_RUN_PORT=8000
```

## Authentication

The application uses session-based authentication.

The user logs in by providing the router IP, SSH username and SSH password.

Available routes:

```text
GET  /
POST /connect
GET  /logout
```

The credentials are stored in the Flask session and used for every subsequent SSH command during the session.

## Code Layout

```
Network Menager/
├── app/
│   ├── __init__.py
│   ├── routes.py           # Flask routes for every page
│   ├── ssh_utils.py        # SSH command wrappers and parsers
│   └── templates/          # Jinja2 templates
│       ├── index.html
│       ├── dashboard.html
│       ├── dhcp.html
│       ├── wireless.html
│       ├── lte.html
│       ├── lan.html
│       ├── devices.html
│       ├── portforward.html
│       ├── status.html
│       ├── logs.html
│       └── console.html
└── run.py
```

## Backend TODO (Hardening)

TODO(backend): replace inline f-string command construction with shlex.quote escaping for every user-provided argument.

Affected functions in ssh_utils.py:

- add_dhcp_reservation
- update_wifi_config
- set_hostname
- set_lan_config
- add_port_forwarding

## Backend TODO (Performance)

TODO(backend): introduce a single SSH session per request instead of opening a new connection for every command.

Currently get_dhcp_reservations opens 1 + 3N SSH connections for N reservations, which significantly slows down page loads.

## Backend TODO (Multi Device)

Aktualna lista braków funkcjonalnych dla wieloadminowego panelu:

- docs/TODO.md
