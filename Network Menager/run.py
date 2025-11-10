# ================================================
#  Network Manager – Flask WebApp
#  Autor: Szymon D.
#  Opis: Aplikacja webowa do zarządzania routerem (np. Teltonika / OpenWRT)
#        przez SSH, z poziomu interfejsu WWW.
# ================================================

from flask import Flask, render_template, request, redirect, url_for, session
from ssh_utils import (
    connect_router,          # Funkcja do nawiązywania połączenia SSH
    exec_ssh_command,        # Wykonywanie komend przez SSH
    get_dhcp_data,           # Pobieranie ustawień DHCP z routera
    update_dhcp_config,      # Aktualizacja konfiguracji DHCP
    get_system_logs,         # Pobieranie logów systemowych z routera
    get_device_status        # Pobieranie statusu routera (uptime, interfejsy itp.)
)

# ================================================
#  Inicjalizacja aplikacji Flask
# ================================================
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Klucz sesji (wymagany do przechowywania danych logowania)

# ================================================
#  Główna strona – formularz logowania do routera
# ================================================
@app.route("/")
def index():
    return render_template("index.html")

# ================================================
#  Obsługa połączenia SSH z routerem
#  Po wpisaniu danych logowania, aplikacja łączy się z routerem
#  Jeśli połączenie się uda, zapisuje dane do sesji i przechodzi do dashboardu
# ================================================
@app.route("/connect", methods=["POST"])
def connect():
    ip = request.form.get("ip")
    username = request.form.get("username")
    password = request.form.get("password")

    success, message = connect_router(ip, username, password)

    if success:
        # Zapisujemy dane logowania w sesji (na czas działania aplikacji)
        session['ip'] = ip
        session['username'] = username
        session['password'] = password
        return redirect(url_for('dashboard'))
    else:
        # Jeśli połączenie nieudane – pokazujemy komunikat o błędzie
        return render_template("index.html", error=message)
    
# ================================================
#  Główny panel użytkownika po zalogowaniu
# ================================================
@app.route("/dashboard")
def dashboard():
    ip = session.get('ip')
    username = session.get('username')
    return render_template("dashboard.html", ip=ip, username=username)

# ================================================
#  Podstrona LAN – pobiera dane o interfejsie LAN
#  Używa komendy `ifconfig br-lan`
# ================================================
@app.route("/lan")
def lan():
    ip = session.get('ip')
    username = session.get('username')
    password = session.get('password')

    # Pobranie informacji o interfejsie LAN przez SSH
    lan_info = exec_ssh_command(ip, username, password, "ifconfig br-lan")
    return render_template("lan.html", lan_info=lan_info)

# ================================================
#  Podstrona Wireless – informacje o sieci Wi-Fi
#  Używa komendy `iwinfo`
# ================================================
@app.route("/wireless")
def wireless():
    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")

    wifi_info = exec_ssh_command(ip, username, password, "iwinfo")
    return render_template("wireless.html", wifi_info=wifi_info)

# ================================================
#  DHCP – podgląd i modyfikacja konfiguracji serwera DHCP
#  - GET -> pokazuje aktualne ustawienia
#  - POST -> zapisuje zmienione parametry przez SSH
# ================================================
@app.route("/dhcp", methods=["GET", "POST"])
def dhcp():
    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")

    # Aktualizacja konfiguracji DHCP po kliknięciu "Zapisz"
    if request.method == "POST":
        start = request.form.get("start")
        limit = request.form.get("limit")
        leasetime = request.form.get("leasetime")

        success, message = update_dhcp_config(ip, username, password, start, limit, leasetime)
        dhcp_data = get_dhcp_data(ip, username, password)
        return render_template("dhcp.html", data=dhcp_data, message=message, success=success)

    # Domyślnie – wyświetlenie bieżących ustawień DHCP
    dhcp_data = get_dhcp_data(ip, username, password)
    return render_template("dhcp.html", data=dhcp_data)

# ================================================
#  System Logs – pobieranie logów z routera
#  - logread (OpenWRT)
#  - jeśli brak -> dmesg (systemowe)
# ================================================
@app.route("/logs")
def logs():
    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")

    logs = get_system_logs(ip, username, password)
    return render_template("logs.html", logs=logs)

# ================================================
#  Status urządzenia – wyświetla:
#   - uptime
#   - obciążenie CPU
#   - pamięć RAM
#   - bramę domyślną
#   - interfejsy sieciowe (UP/DOWN)
# ================================================
@app.route("/status")
def status():
    ip = session.get("ip")
    username = session.get("username")
    password = session.get("password")

    status_data = get_device_status(ip, username, password)
    return render_template("status.html", status=status_data)

# ================================================
#  Uruchomienie aplikacji (tryb developerski)
# ================================================
if __name__ == "__main__":
    app.run(debug=True)
