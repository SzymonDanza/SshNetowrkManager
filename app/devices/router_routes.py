import re
import time
from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required
from app.db.base import SessionLocal
from app.models.device import Device
from app.ssh_utils import (
    exec_ssh_command,
    get_dhcp_data, update_dhcp_config,
    get_dhcp_reservations, add_dhcp_reservation, remove_dhcp_reservation,
    get_system_logs, get_device_status,
    get_lte_info,
    get_hostname, set_hostname,
    get_lan_config, set_lan_config, get_ports_info,
    get_devices, ping_device,
    get_port_forwarding, add_port_forwarding, delete_port_forwarding,
)
from app.ssh_utils import get_wifi_info, get_wifi_details, update_wifi_config

router_bp = Blueprint("router", __name__)


def _get_device(device_id):
    db = SessionLocal()
    device = db.get(Device, device_id)
    db.close()
    if not device:
        abort(404)
    return device


@router_bp.route("/devices/<int:device_id>/dashboard")
@login_required
def dashboard(device_id):
    d = _get_device(device_id)
    return render_template("dashboard.html", device=d)


@router_bp.route("/devices/<int:device_id>/status")
@login_required
def status(device_id):
    d = _get_device(device_id)
    status_data = get_device_status(d.host, d.ssh_user, d.ssh_password)
    return render_template("status.html", status=status_data, device=d)


@router_bp.route("/devices/<int:device_id>/device", methods=["GET", "POST"])
@login_required
def device(device_id):
    d = _get_device(device_id)
    message = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "reboot":
            exec_ssh_command(d.host, d.ssh_user, d.ssh_password, "reboot")
            message = "Router został zrestartowany."
        elif action.startswith("ifup_"):
            iface = action.split("_")[1]
            exec_ssh_command(d.host, d.ssh_user, d.ssh_password, f"ifup {iface}")
            message = f"Interfejs {iface} włączony."
        elif action.startswith("ifdown_"):
            iface = action.split("_")[1]
            exec_ssh_command(d.host, d.ssh_user, d.ssh_password, f"ifdown {iface}")
            message = f"Interfejs {iface} wyłączony."
        time.sleep(1.5)
    status_data = get_device_status(d.host, d.ssh_user, d.ssh_password)
    interfaces = status_data.get("interfaces", [])
    return render_template("device.html", interfaces=interfaces, message=message, device=d)


@router_bp.route("/devices/<int:device_id>/dhcp", methods=["GET", "POST"])
@login_required
def dhcp(device_id):
    d = _get_device(device_id)
    message = None
    success = None
    if request.method == "POST":
        if "add_reservation" in request.form:
            mac = request.form.get("mac", "").strip()
            ipaddr = request.form.get("ipaddr", "").strip()
            name = request.form.get("name", "").strip()
            mac_re = r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"
            ip_re = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
            if not re.match(mac_re, mac):
                success, message = False, f"Niepoprawny MAC: {mac}"
            elif not re.match(ip_re, ipaddr):
                success, message = False, f"Niepoprawny IP: {ipaddr}"
            elif not name:
                success, message = False, "Nazwa nie może być pusta."
            else:
                success, message = add_dhcp_reservation(d.host, d.ssh_user, d.ssh_password, mac, ipaddr, name)
        elif "delete_id" in request.form:
            host_id = request.form.get("delete_id")
            success, message = remove_dhcp_reservation(d.host, d.ssh_user, d.ssh_password, host_id)
        else:
            start = request.form.get("start")
            limit = request.form.get("limit")
            leasetime = request.form.get("leasetime")
            success, message = update_dhcp_config(d.host, d.ssh_user, d.ssh_password, start, limit, leasetime)
    dhcp_data = get_dhcp_data(d.host, d.ssh_user, d.ssh_password)
    reservations = get_dhcp_reservations(d.host, d.ssh_user, d.ssh_password)
    return render_template("dhcp.html", data=dhcp_data, reservations=reservations, message=message, success=success, device=d)


@router_bp.route("/devices/<int:device_id>/logs")
@login_required
def logs(device_id):
    d = _get_device(device_id)
    logs = get_system_logs(d.host, d.ssh_user, d.ssh_password)
    return render_template("logs.html", logs=logs, device=d)


@router_bp.route("/devices/<int:device_id>/lte")
@login_required
def lte_view(device_id):
    d = _get_device(device_id)
    data = get_lte_info(d.host, d.ssh_user, d.ssh_password)
    return render_template("lte.html", data=data, device=d)


@router_bp.route("/devices/<int:device_id>/hostname", methods=["GET", "POST"])
@login_required
def hostname(device_id):
    d = _get_device(device_id)
    current_hostname = get_hostname(d.host, d.ssh_user, d.ssh_password)
    message = None
    success = None
    if request.method == "POST":
        new_hostname = request.form.get("hostname", "").strip()
        pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,30}[a-zA-Z0-9])?$"
        if not new_hostname:
            success, message = False, "Hostname nie może być pusty."
        elif len(new_hostname) > 32:
            success, message = False, "Hostname max 32 znaki."
        elif not re.match(pattern, new_hostname):
            success, message = False, "Tylko litery, cyfry i myślniki."
        else:
            success, message = set_hostname(d.host, d.ssh_user, d.ssh_password, new_hostname)
            current_hostname = get_hostname(d.host, d.ssh_user, d.ssh_password)
    return render_template("hostname.html", current_hostname=current_hostname, message=message, success=success, device=d)


@router_bp.route("/devices/<int:device_id>/lan", methods=["GET", "POST"])
@login_required
def lan(device_id):
    d = _get_device(device_id)
    message = None
    success = None
    if request.method == "POST":
        ipaddr = request.form.get("ipaddr")
        netmask = request.form.get("netmask")
        gateway = request.form.get("gateway")
        dns = request.form.get("dns")
        success, message = set_lan_config(d.host, d.ssh_user, d.ssh_password, ipaddr, netmask, gateway, dns)
    lan_ifconfig = exec_ssh_command(d.host, d.ssh_user, d.ssh_password, "ifconfig br-lan")
    lan_config = get_lan_config(d.host, d.ssh_user, d.ssh_password)
    lan_ports = get_ports_info(d.host, d.ssh_user, d.ssh_password)
    return render_template("lan.html", lan_ifconfig=lan_ifconfig, lan_config=lan_config, lan_ports=lan_ports, message=message, success=success, device=d)


@router_bp.route("/devices/<int:device_id>/connected", methods=["GET", "POST"])
@login_required
def connected_devices(device_id):
    d = _get_device(device_id)
    message = None
    success = None
    if request.method == "POST":
        target_ip = request.form.get("ping_ip", "").strip()
        if target_ip:
            success, message = ping_device(d.host, d.ssh_user, d.ssh_password, target_ip)
        else:
            success, message = False, "Nie podano IP."
    devices_list = get_devices(d.host, d.ssh_user, d.ssh_password)
    return render_template("devices.html", devices=devices_list, message=message, success=success, device=d)


@router_bp.route("/devices/<int:device_id>/portforward", methods=["GET", "POST"])
@login_required
def portforward(device_id):
    d = _get_device(device_id)
    message = None
    success = None
    if request.method == "POST":
        if "delete_id" in request.form:
            rule_id = request.form.get("delete_id")
            success, message = delete_port_forwarding(d.host, d.ssh_user, d.ssh_password, rule_id)
        else:
            name = request.form.get("name")
            ipdest = request.form.get("ipdest")
            wanport = request.form.get("wanport")
            lanport = request.form.get("lanport")
            proto = request.form.get("proto")
            success, message = add_port_forwarding(d.host, d.ssh_user, d.ssh_password, name, ipdest, wanport, lanport, proto)
    rules = get_port_forwarding(d.host, d.ssh_user, d.ssh_password)
    return render_template("portforward.html", rules=rules, message=message, success=success, device=d)


@router_bp.route("/devices/<int:device_id>/wireless")
@login_required
def wireless(device_id):
    d = _get_device(device_id)
    wifi_info = get_wifi_info(d.host, d.ssh_user, d.ssh_password)
    return render_template("wireless.html", wifi_info=wifi_info, device=d)


@router_bp.route("/devices/<int:device_id>/wifi/<interface>", methods=["GET", "POST"])
@login_required
def wifi_details(device_id, interface):
    d = _get_device(device_id)
    message = None
    success = None
    if request.method == "POST":
        ssid = request.form.get("ssid")
        key = request.form.get("key")
        encryption = request.form.get("encryption")
        success, message = update_wifi_config(d.host, d.ssh_user, d.ssh_password, interface, ssid, key, encryption)
    details = get_wifi_details(d.host, d.ssh_user, d.ssh_password, interface)
    return render_template("wifi_details.html", interface=interface, details=details, message=message, success=success, device=d)


@router_bp.route("/devices/<int:device_id>/terminal", methods=["GET", "POST"])
@login_required
def terminal(device_id):
    d = _get_device(device_id)
    output = None
    command = ""
    if request.method == "POST":
        command = request.form.get("command", "").strip()
        output = exec_ssh_command(d.host, d.ssh_user, d.ssh_password, command) if command else "Nie podano komendy."
    return render_template("console.html", command=command, output=output, device=d)