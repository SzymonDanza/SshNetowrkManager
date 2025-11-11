# ================================================
#  Network Manager – trasy Flask
# ================================================
from flask import render_template, request, redirect, url_for, session
from app.ssh_utils import (
    connect_router,
    exec_ssh_command,
    get_dhcp_data,
    update_dhcp_config,
    get_system_logs,
    get_device_status
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
    @app.route("/wireless")
    def wireless():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")
        wifi_info = exec_ssh_command(ip, username, password, "iwinfo")
        return render_template("wireless.html", wifi_info=wifi_info)

    # DHCP – podgląd i edycja ustawień
    @app.route("/dhcp", methods=["GET", "POST"])
    def dhcp():
        ip = session.get("ip")
        username = session.get("username")
        password = session.get("password")

        if request.method == "POST":
            start = request.form.get("start")
            limit = request.form.get("limit")
            leasetime = request.form.get("leasetime")

            # aktualizacja konfiguracji DHCP
            success, message = update_dhcp_config(ip, username, password, start, limit, leasetime)
            dhcp_data = get_dhcp_data(ip, username, password)
            return render_template("dhcp.html", data=dhcp_data, message=message, success=success)

        # domyślnie wyświetl dane DHCP
        dhcp_data = get_dhcp_data(ip, username, password)
        return render_template("dhcp.html", data=dhcp_data)

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
