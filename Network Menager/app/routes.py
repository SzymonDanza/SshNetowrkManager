# ================================================
#  Network Manager – trasy Flask
# ================================================
from flask import render_template, request, redirect, url_for, session
import re
from app.ssh_utils import (
    connect_router,
    exec_ssh_command,
    get_dhcp_data,
    update_dhcp_config,
    get_system_logs,
    get_device_status,
    get_dhcp_reservations,     
    add_dhcp_reservation,      
    remove_dhcp_reservation
)

def register_routes(app):
    """Rejestruje wszystkie trasy aplikacji Flask."""

    # Strona logowania do routera
    @app.route("/")
    def index():
        return render_template("index.html")

    # Logowanie przez SSH
    @app.route("/connect", methods=["POST"])
    def connect():
        ip = request.form.get("ip")
        username = request.form.get("username")
        password = request.form.get("password")

        success, message = connect_router(ip, username, password)

        if success:
            # zapis danych do sesji po udanym połączeniu
            session['ip'] = ip
            session['username'] = username
            session['password'] = password
            return redirect(url_for('dashboard'))
        else:
            return render_template("index.html", error=message)

    # Główny panel użytkownika
    @app.route("/dashboard")
    def dashboard():
        ip = session.get('ip')
        username = session.get('username')
        return render_template("dashboard.html", ip=ip, username=username)

    # Informacje o interfejsie LAN
    @app.route("/lan")
    def lan():
        ip = session.get('ip')
        username = session.get('username')
        password = session.get('password')
        lan_info = exec_ssh_command(ip, username, password, "ifconfig br-lan")
        return render_template("lan.html", lan_info=lan_info)

    # Informacje o Wi-Fi
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



    @app.route("/dhcp", methods=["GET", "POST"])
    def dhcp():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        message = None
        success = None

        # 🧩 POST – obsługa formularzy (edycja konfiguracji / dodanie / usunięcie rezerwacji)
        if request.method == "POST":
            # 🔹 Dodanie rezerwacji
            if "add_reservation" in request.form:
                mac = request.form.get("mac", "").strip()
                ipaddr = request.form.get("ipaddr", "").strip()
                name = request.form.get("name", "").strip()

                # 🔍 Wzorce regex do walidacji
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
                    # ✅ Jeśli dane poprawne, dodaj rezerwację
                    success, message = add_dhcp_reservation(ip, username, password, mac, ipaddr, name)


            # 🔹 Usunięcie rezerwacji
            elif "delete_id" in request.form:
                host_id = request.form.get("delete_id")
                success, message = remove_dhcp_reservation(ip, username, password, host_id)

            # 🔹 Zmiana ustawień DHCP
            else:
                start = request.form.get("start")
                limit = request.form.get("limit")
                leasetime = request.form.get("leasetime")
                success, message = update_dhcp_config(ip, username, password, start, limit, leasetime)

        # 🧩 GET – pobranie danych
        dhcp_data = get_dhcp_data(ip, username, password)
        reservations = get_dhcp_reservations(ip, username, password)

        return render_template("dhcp.html", data=dhcp_data, reservations=reservations, message=message, success=success)


   

    # Logi systemowe routera
    @app.route("/logs")
    def logs():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")
        logs = get_system_logs(ip, username, password)
        return render_template("logs.html", logs=logs)

    # Status routera (uptime, CPU, RAM, interfejsy)
    @app.route("/status")
    def status():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")
        status_data = get_device_status(ip, username, password)
        return render_template("status.html", status=status_data)
    
    # Zarządzanie urządzeniem – restart i interfejsy
    # Zarządzanie urządzeniem – restart i interfejsy
    import time  # na górze pliku, jeśli nie ma

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
                message = f"✅ Interfejs {iface} został uruchomiony."

            elif action.startswith("ifdown_"):
                iface = action.split("_")[1]
                exec_ssh_command(ip, username, password, f"ifdown {iface}")
                message = f"🛑 Interfejs {iface} został wyłączony."

            # czekamy chwilę, aż system zaktualizuje stan interfejsów
            time.sleep(1.5)

        # po każdej akcji pobieramy nowy stan interfejsów
        status_data = get_device_status(ip, username, password)
        interfaces = status_data.get("interfaces", [])

        return render_template("device.html", interfaces=interfaces, message=message)
    # Konsola SSH - wpisz komendę, zobacz wynik
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
                # 🔓 Brak blokady – komenda idzie prosto do SSH
                output = exec_ssh_command(ip, username, password, command)

        return render_template("console.html", command=command, output=output)
    

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"))

