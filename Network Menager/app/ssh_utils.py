import paramiko
import json
import time

# Nawiązanie połączenia SSH z routerem
def connect_router(ip, username, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=22, timeout=10)
        ssh.close()
        return True, f"Połączono pomyślnie z routerem {ip}"
    except Exception as e:
        return False, f"Błąd połączenia: {e}"


# Wykonanie komendy przez SSH i zwrócenie wyniku
def exec_ssh_command(ip, username, password, command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, port=22, timeout=10)
        
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode(errors="ignore")
        ssh.close()
        return output or "Brak danych z routera."
    except Exception as e:
        return f"Błąd podczas wykonywania komendy: {e}"

# =======================================================
# DHCP (zakres/hosty/konfiguracja/rezerwacje)
# =======================================================



# Pobranie danych DHCP z routera
def get_dhcp_data(ip, username, password):
    try:
        # Dane z pliku /tmp/dhcp.leases
        leases_output = exec_ssh_command(ip, username, password, "cat /tmp/dhcp.leases")

        # Podstawowe parametry DHCP
        start = exec_ssh_command(ip, username, password, "uci get dhcp.lan.start").strip()
        limit = exec_ssh_command(ip, username, password, "uci get dhcp.lan.limit").strip()
        leasetime = exec_ssh_command(ip, username, password, "uci get dhcp.lan.leasetime").strip()

        # Pełna konfiguracja DHCP
        config_output = exec_ssh_command(ip, username, password, "cat /etc/config/dhcp")

        # Parsowanie danych dzierżaw
        leases = []
        for line in leases_output.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                leases.append({
                    "timestamp": parts[0],
                    "mac": parts[1],
                    "ip": parts[2],
                    "hostname": parts[3] if len(parts) > 3 else "-"
                })

        return {
            "leases": leases,
            "settings": {"start": start, "limit": limit, "leasetime": leasetime},
            "config_raw": config_output
        }

    except Exception as e:
        return {
            "leases": [],
            "settings": {"start": "-", "limit": "-", "leasetime": "-"},
            "config_raw": f"Błąd pobierania DHCP: {e}"
        }


# Aktualizacja konfiguracji DHCP
def update_dhcp_config(ip, username, password, start, limit, leasetime):
    try:
        commands = [
            f"uci set dhcp.lan.start='{start}'",
            f"uci set dhcp.lan.limit='{limit}'",
            f"uci set dhcp.lan.leasetime='{leasetime}'",
            "uci commit dhcp",
            "/etc/init.d/dnsmasq restart"
        ]
        full_command = " && ".join(commands)
        result = exec_ssh_command(ip, username, password, full_command)
        return True, f"Konfiguracja DHCP została zaktualizowana:\n{result}"
    except Exception as e:
        return False, f"Błąd aktualizacji konfiguracji DHCP: {e}"
    


def get_dhcp_reservations(ip, username, password):
    """
    Pobiera listę rezerwacji DHCP (static leases) z pliku /etc/config/dhcp.
    Każda rezerwacja to sekcja typu 'config host' w UCI.
    Zwraca listę słowników: [{"id": ..., "mac": ..., "ip": ..., "name": ...}, ...]
    """
    try:
        # Pobieramy listę sekcji host (czyli rezerwacji)
        output = exec_ssh_command(ip, username, password, "uci show dhcp | grep '=host' || true")
        lines = output.splitlines()
        reservations = []

        for line in lines:
            if "dhcp." in line:
                host_id = line.split(".")[1].split("=")[0]

                # Pobranie szczegółów każdej rezerwacji
                mac = exec_ssh_command(ip, username, password, f"uci get dhcp.{host_id}.mac || echo '-'").strip()
                ipaddr = exec_ssh_command(ip, username, password, f"uci get dhcp.{host_id}.ip || echo '-'").strip()
                name = exec_ssh_command(ip, username, password, f"uci get dhcp.{host_id}.name || echo '-'").strip()

                reservations.append({
                    "id": host_id,
                    "mac": mac,
                    "ip": ipaddr,
                    "name": name
                })

        return reservations

    except Exception as e:
        return [{"error": f"Błąd pobierania rezerwacji DHCP: {e}"}]


def add_dhcp_reservation(ip, username, password, mac, ipaddr, name):
    """
    Dodaje nową rezerwację DHCP (static lease).
    Tworzy sekcję 'config host' w UCI, ustawia MAC, IP i nazwę hosta.
    """
    try:
        # Dodaj nową sekcję host i uzupełnij pola
        cmd = (
            "uci add dhcp host && "
            f"uci set dhcp.@host[-1].mac='{mac}' && "
            f"uci set dhcp.@host[-1].ip='{ipaddr}' && "
            f"uci set dhcp.@host[-1].name='{name}' && "
            "uci commit dhcp && "
            "/etc/init.d/dnsmasq restart"
        )

        exec_ssh_command(ip, username, password, cmd)
        return True, f"Rezerwacja dla {mac} → {ipaddr} została dodana."

    except Exception as e:
        return False, f"Błąd dodawania rezerwacji: {e}"


def remove_dhcp_reservation(ip, username, password, host_id):
    """
    Usuwa istniejącą rezerwację DHCP po identyfikatorze sekcji (np. host[0], host1 itp.)
    """
    try:
        cmd = f"uci delete dhcp.{host_id} && uci commit dhcp && /etc/init.d/dnsmasq restart"
        exec_ssh_command(ip, username, password, cmd)
        return True, f"Rezerwacja {host_id} została usunięta."
    except Exception as e:
        return False, f"Błąd usuwania rezerwacji: {e}"    




# =======================================================
# LOGI SYSTEMOWE
# =======================================================

# Pobranie logów systemowych (logread lub dmesg)
def get_system_logs(ip, username, password):
    try:
        logs = exec_ssh_command(ip, username, password, "logread | tail -n 200")
        if "not found" in logs.lower() or logs.strip() == "":
            logs = exec_ssh_command(ip, username, password, "dmesg | tail -n 200")
        return logs or "Brak logów systemowych."
    except Exception as e:
        return f"Błąd podczas pobierania logów: {e}"




def get_device_status(ip, username, password):
    """
    Pobiera status routera:
    - czas działania (uptime)
    - zużycie CPU (%)
    - średnie obciążenie (load average)
    - pamięć RAM
    - bramę domyślną
    - interfejsy logiczne (LAN, WAN, itp.)
    """
    try:
        interfaces = []

        # ======================
        # INTERFEJSY LOGICZNE
        # ======================
        uci_interfaces = exec_ssh_command(ip, username, password, "uci show network | grep '=interface' || true").splitlines()

        for line in uci_interfaces:
            if "network." in line:
                iface = line.split(".")[1].split("=")[0]
                raw_status = exec_ssh_command(ip, username, password, f"ifstatus {iface} || true").strip()

                state = "DOWN"
                if raw_status:
                    try:
                        data = json.loads(raw_status)
                        if data.get("up") is True:
                            state = "UP"
                    except json.JSONDecodeError:
                        pass

                interfaces.append({"name": iface, "state": state})

        # ======================
        # SYSTEM: UPTIME, CPU, RAM, GATEWAY
        # ======================

        # 1️⃣ Uptime – wersja kompatybilna z BusyBox
        raw_uptime = exec_ssh_command(ip, username, password, "uptime || echo 'brak danych'").strip()
        uptime_clean = "brak danych"
        if "up" in raw_uptime:
    # przykład:  16:27:55 up 1 day,  3:12,  load average: 0.00, 0.01, 0.00
            try:
        # Wyciągamy wszystko między "up" a "load average"
                uptime_clean = raw_uptime.split("up", 1)[1].split("load average")[0].strip().rstrip(",")
            except Exception:
                uptime_clean = raw_uptime.strip()

        # 2️⃣ Load average (średnie obciążenie)
        load_avg = exec_ssh_command(ip, username, password, "awk '{print $1,$2,$3}' /proc/loadavg || echo 'brak danych'").strip()

        # 3️⃣ CPU usage (%)
        cpu1 = exec_ssh_command(ip, username, password, "cat /proc/stat | grep '^cpu '").strip()
        time.sleep(0.3)
        cpu2 = exec_ssh_command(ip, username, password, "cat /proc/stat | grep '^cpu '").strip()

        def parse_cpu(line):
            parts = line.split()
            return list(map(int, parts[1:])) if len(parts) > 7 else [0] * 7

        c1, c2 = parse_cpu(cpu1), parse_cpu(cpu2)
        idle1, idle2 = c1[3], c2[3]
        total1, total2 = sum(c1), sum(c2)
        diff_total = total2 - total1
        diff_idle = idle2 - idle1
        cpu_usage = 0.0
        if diff_total > 0:
            cpu_usage = (1 - diff_idle / diff_total) * 100

        # 4️⃣ RAM i brama
        memory = exec_ssh_command(ip, username, password, "free -m | awk '/Mem/ {print $3\"/\"$2\" MB\"}' || echo 'brak danych'").strip()
        gateway = exec_ssh_command(ip, username, password, "ip route | grep default | awk '{print $3}' || echo '-'").strip()

        return {
            "uptime": uptime_clean,
            "cpu_usage": f"{cpu_usage:.1f}%",
            "cpu_load": load_avg,
            "memory": memory,
            "gateway": gateway,
            "interfaces": interfaces
        }

    except Exception as e:
        return {"error": f"❌ Błąd pobierania statusu urządzenia: {e}"}
    
import re




def get_wifi_info(ip, username, password):
    """
    Pobiera listę interfejsów Wi-Fi z routera OpenWrt
    za pomocą komendy 'iwinfo'.
    """
    output = exec_ssh_command(ip, username, password, "iwinfo")
    wifi_list = []
    blocks = output.split("\n\n")  # każdy interfejs osobno

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        info = {
            "interface": lines[0].split()[0],
            "ssid": "-",
            "channel": "-",
            "frequency": "-",
            "txpower": "-",
            "encryption": "-",
        }

        for line in lines:
            # ESSID
            if "ESSID:" in line:
                info["ssid"] = line.split("ESSID:")[1].strip().strip('"')

            # Kanał + częstotliwość np. "Channel: 36 (5.180 GHz)"
            elif "Channel:" in line:
                match = re.search(r"Channel:\s*([0-9]+)\s*\(([\d\.]+)\s*GHz\)", line)
                if match:
                    info["channel"] = match.group(1)
                    info["frequency"] = f"{match.group(2)} GHz"

            # Moc nadawania
            elif "Tx-Power:" in line:
                power = line.split("Tx-Power:")[1].split()[0]
                info["txpower"] = f"{power} dBm"

            # Szyfrowanie
            elif "Encryption:" in line:
                info["encryption"] = line.split("Encryption:")[1].strip()

        wifi_list.append(info)

    return wifi_list


def get_wifi_details(ip, username, password, interface):
    """
    Pobiera szczegółowe dane o jednym interfejsie Wi-Fi z routera OpenWrt.
    Komenda: iwinfo <interface> info
    """
    output = exec_ssh_command(ip, username, password, f"iwinfo {interface} info")

    if not output.strip():
        return {"Błąd": "Brak odpowiedzi z routera (iwinfo zwrócił pusty wynik)."}

    if "Usage:" in output:
        return {"Błąd": f"Polecenie iwinfo {interface} info nie działa na tym interfejsie."}

    details = {}
    last_key = None

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            details[key.strip()] = val.strip()
            last_key = key.strip()
        else:
            # obsługa linii bez dwukropka (kontynuacja wartości)
            if last_key:
                details[last_key] += " " + line

    return details

def update_wifi_config(ip, username, password, interface, ssid=None, key=None, encryption=None):
    """
    Aktualizuje konfigurację Wi-Fi (SSID, hasło, szyfrowanie) dla interfejsu w OpenWrt.
    Działa z sekcjami default_radio0 i default_radio1.
    """
    try:
        # Mapowanie interfejsów iwinfo → sekcje UCI
        if "phy0" in interface or "wlan0" in interface:
            section_name = "wireless.default_radio0"
        elif "phy1" in interface or "wlan1" in interface:
            section_name = "wireless.default_radio1"
        else:
            return False, f"Nie rozpoznano interfejsu ({interface}) — nie znaleziono odpowiadającej sekcji UCI."

        commands = []
        if ssid:
            commands.append(f"uci set {section_name}.ssid='{ssid}'")
        if key:
            commands.append(f"uci set {section_name}.key='{key}'")
        if encryption:
            commands.append(f"uci set {section_name}.encryption='{encryption}'")

        # Zapis i restart Wi-Fi
        commands.append("uci commit wireless")
        commands.append("wifi reload")

        full_command = " && ".join(commands)
        result = exec_ssh_command(ip, username, password, full_command)

        return True, f"✅ Zaktualizowano konfigurację dla {section_name}.\n{result}"

    except Exception as e:
        return False, f"❌ Błąd podczas aktualizacji Wi-Fi: {e}"
    



