from flask import render_template, request, redirect, url_for, session
import re
import time

from app.ssh_utils import (
    connect_router,
    exec_ssh_command,
    get_dhcp_data,
    update_dhcp_config,
    get_system_logs,
    get_device_status,
    get_dhcp_reservations,
    add_dhcp_reservation,
    remove_dhcp_reservation,
    get_lte_info,
    set_hostname,
    get_hostname,
    get_lan_config,
    set_lan_config,
    get_ports_info,
   get_devices,
   ping_device,
    add_port_forwarding,
    get_port_forwarding,
    delete_port_forwarding
)


def register_routes(app):
    """Rejestruje wszystkie trasy aplikacji Flask."""

    # -----------------------------------------
    # STRONA GŁÓWNA / LOGOWANIE
    # -----------------------------------------
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))


    @app.route("/connect", methods=["POST"])
    def connect():
        ip = request.form.get("ip")
        username = request.form.get("username")
        password = request.form.get("password")

        success, message = connect_router(ip, username, password)

        if success:
            session["ip"] = ip
            session["username"] = username
            session["password"] = password
            return redirect(url_for("dashboard"))
        else:
            return render_template("index.html", error=message)

    # -----------------------------------------
    # DASHBOARD
    # -----------------------------------------
    @app.route("/dashboard")
    def dashboard():
        return redirect(url_for("devices.device_list"))

    # -----------------------------------------
    # WIFI – szczegóły interfejsu
    # -----------------------------------------
    @app.route("/wifi/<interface>", methods=["GET", "POST"])
    def wifi_details(interface):
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        from app.ssh_utils import get_wifi_details, update_wifi_config

        message = None
        success = None

        if request.method == "POST":
            ssid = request.form.get("ssid")
            key = request.form.get("key")
            encryption = request.form.get("encryption")

            success, message = update_wifi_config(ip, username, password, interface, ssid, key, encryption)

        details = get_wifi_details(ip, username, password, interface)
        return render_template("wifi_details.html", interface=interface, details=details, message=message, success=success)

    @app.route("/wireless")
    def wireless():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        from app.ssh_utils import get_wifi_info
        wifi_info = get_wifi_info(ip, username, password)

        return render_template("wireless.html", wifi_info=wifi_info)

    # -----------------------------------------
    # DHCP + rezerwacje
    # -----------------------------------------
    @app.route("/dhcp", methods=["GET", "POST"])
    def dhcp():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        message = None
        success = None

        if request.method == "POST":

            # Dodanie rezerwacji
            if "add_reservation" in request.form:
                mac = request.form.get("mac", "").strip()
                ipaddr = request.form.get("ipaddr", "").strip()
                name = request.form.get("name", "").strip()

                mac_pattern = r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"
                ip_pattern = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"

                if not re.match(mac_pattern, mac):
                    success = False
                    message = f"❌ Niepoprawny adres MAC: {mac}"

                elif not re.match(ip_pattern, ipaddr):
                    success = False
                    message = f"❌ Niepoprawny adres IP: {ipaddr}"

                elif not name:
                    success = False
                    message = "❌ Nazwa urządzenia nie może być pusta."

                else:
                    success, message = add_dhcp_reservation(ip, username, password, mac, ipaddr, name)

            # Usuwanie rezerwacji
            elif "delete_id" in request.form:
                host_id = request.form.get("delete_id")
                success, message = remove_dhcp_reservation(ip, username, password, host_id)

            # Edycja ustawień DHCP
            else:
                start = request.form.get("start")
                limit = request.form.get("limit")
                leasetime = request.form.get("leasetime")
                success, message = update_dhcp_config(ip, username, password, start, limit, leasetime)

        dhcp_data = get_dhcp_data(ip, username, password)
        reservations = get_dhcp_reservations(ip, username, password)

        return render_template("dhcp.html", data=dhcp_data, reservations=reservations, message=message, success=success)

    # -----------------------------------------
    # LOGI SYSTEMOWE
    # -----------------------------------------
    @app.route("/logs")
    def logs():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        logs = get_system_logs(ip, username, password)
        return render_template("logs.html", logs=logs)

    # -----------------------------------------
    # STATUS URZĄDZENIA
    # -----------------------------------------
    @app.route("/status")
    def status():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        status_data = get_device_status(ip, username, password)
        return render_template("status.html", status=status_data)

    # -----------------------------------------
    # ZARZĄDZANIE URZĄDZENIEM
    # -----------------------------------------
    @app.route("/device", methods=["GET", "POST"])
    def device():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        message = None

        if request.method == "POST":
            action = request.form.get("action")

            if action == "reboot":
                exec_ssh_command(ip, username, password, "reboot")
                message = "🔁 Router został zrestartowany."

            elif action.startswith("ifup_"):
                iface = action.split("_")[1]
                exec_ssh_command(ip, username, password, f"ifup {iface}")
                message = f"✅ Interfejs {iface} został włączony."

            elif action.startswith("ifdown_"):
                iface = action.split("_")[1]
                exec_ssh_command(ip, username, password, f"ifdown {iface}")
                message = f"🛑 Interfejs {iface} został wyłączony."

            time.sleep(1.5)

        status_data = get_device_status(ip, username, password)
        interfaces = status_data.get("interfaces", [])

        return render_template("device.html", interfaces=interfaces, message=message)

    # -----------------------------------------
    # KONSOLA SSH
    # -----------------------------------------
    @app.route("/terminal", methods=["GET", "POST"])
    def terminal():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        output = None
        command = ""

        if request.method == "POST":
            command = request.form.get("command", "").strip()
            if not command:
                output = "❌ Nie podano komendy."
            else:
                output = exec_ssh_command(ip, username, password, command)

        return render_template("console.html", command=command, output=output)

    # -----------------------------------------
    # WYLOGOWANIE
    # -----------------------------------------
    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

    # -----------------------------------------
    # LTE – Teltonika / OpenWrt
    # -----------------------------------------
    @app.route("/lte")
    def lte_view():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        data = get_lte_info(ip, username, password)
        return render_template("lte.html", data=data)

    # -----------------------------------------
    # HOSTNAME – pobieranie i zmiana
    # -----------------------------------------
    @app.route("/hostname", methods=["GET", "POST"])
    def hostname():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        current_hostname = get_hostname(ip, username, password)
        message = None
        success = None

        if request.method == "POST":
            new_hostname = request.form.get("hostname", "").strip()

            hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,30}[a-zA-Z0-9])?$"

            if not new_hostname:
                success = False
                message = "Hostname nie może być pusty."
            elif len(new_hostname) > 32:
                success = False
                message = "Hostname może mieć maksymalnie 32 znaki."
            elif not re.match(hostname_pattern, new_hostname):
                success = False
                message = "Hostname może zawierać tylko litery, cyfry i myślniki."
            else:
                success, message = set_hostname(ip, username, password, new_hostname)
                current_hostname = get_hostname(ip, username, password)

        return render_template("hostname.html", current_hostname=current_hostname, message=message, success=success)

    # -----------------------------------------
    # LAN – konfiguracja + porty (AUTODETEKCJA)
    # -----------------------------------------
    @app.route("/lan", methods=["GET", "POST"])
    def lan():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        message = None
        success = None

        if request.method == "POST":
            ipaddr = request.form.get("ipaddr")
            netmask = request.form.get("netmask")
            gateway = request.form.get("gateway")
            dns = request.form.get("dns")

            success, message = set_lan_config(ip, username, password, ipaddr, netmask, gateway, dns)

        lan_ifconfig = exec_ssh_command(ip, username, password, "ifconfig br-lan")
        lan_config = get_lan_config(ip, username, password)

        # >>> AUTOMATYCZNA DETEKCJA PORTÓW
        lan_ports = get_ports_info(ip, username, password)

        return render_template(
            "lan.html",
            lan_ifconfig=lan_ifconfig,
            lan_config=lan_config,
            lan_ports=lan_ports,
            message=message,
            success=success
        )

    @app.route("/devices", methods=["GET", "POST"])
    def devices():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        message = None
        success = None

        if request.method == "POST":
            target_ip = request.form.get("ping_ip", "").strip()
            if target_ip:
                success, message = ping_device(ip, username, password, target_ip)
            else:
                success = False
                message = "Nie podano IP."

        devices_list = get_devices(ip, username, password)

        return render_template(
            "devices.html",
            devices=devices_list,
            message=message,
            success=success
        )

        # -----------------------------------------
    # PORT FORWARDING
    # -----------------------------------------
    @app.route("/portforward", methods=["GET", "POST"])
    def portforward():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        message = None
        success = None

        if request.method == "POST":

            # Usuwanie reguły
            if "delete_id" in request.form:
                rule_id = request.form.get("delete_id")
                success, message = delete_port_forwarding(ip, username, password, rule_id)

            else:  # Dodawanie nowej reguły
                name = request.form.get("name")
                ipdest = request.form.get("ipdest")
                wanport = request.form.get("wanport")
                lanport = request.form.get("lanport")
                proto = request.form.get("proto")

                success, message = add_port_forwarding(ip, username, password, name, ipdest, wanport, lanport, proto)

        rules = get_port_forwarding(ip, username, password)

        return render_template("portforward.html", rules=rules, message=message, success=success)
